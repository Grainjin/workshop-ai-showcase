"""Add immutable provider identity and qualification applications."""

import sqlalchemy as sa
from alembic import op

from backend.models.provider_verification import (
    IdentityVerificationApplication,
    IdentityVerificationFile,
    ProviderApprovedService,
    ProviderServiceArea,
    QualificationVerificationApplication,
    QualificationVerificationFile,
    QualificationVerificationService,
)


revision = "0009_provider_verification"
down_revision = "0008_provider_two_step"
branch_labels = None
depends_on = None


def _columns(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _unique_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table_name)
        if constraint["name"]
    }


def _foreign_key_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in inspector.get_foreign_keys(table_name)
        if constraint["name"]
    }


def _has_unique_columns(
    inspector: sa.Inspector, table_name: str, column_names: set[str]
) -> bool:
    return any(
        set(constraint["column_names"]) == column_names
        for constraint in inspector.get_unique_constraints(table_name)
    )


def _has_foreign_key_columns(
    inspector: sa.Inspector, table_name: str, column_names: set[str]
) -> bool:
    return any(
        set(constraint["constrained_columns"]) == column_names
        for constraint in inspector.get_foreign_keys(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    user_columns = _columns(inspector, "users")
    if "identity_verification_status" not in user_columns:
        op.add_column(
            "users",
            sa.Column("identity_verification_status", sa.String(32), nullable=True),
        )
    if "qualification_verification_status" not in user_columns:
        op.add_column(
            "users",
            sa.Column("qualification_verification_status", sa.String(32), nullable=True),
        )

    # Migration 0001 builds from the current SQLAlchemy metadata. checkfirst=True
    # keeps fresh installs and upgrades from a historical 0008 database equivalent.
    for model in (
        IdentityVerificationApplication,
        IdentityVerificationFile,
        QualificationVerificationApplication,
        QualificationVerificationFile,
        QualificationVerificationService,
    ):
        model.__table__.create(bind=bind, checkfirst=True)

    inspector = sa.inspect(bind)
    profile_columns = _columns(inspector, "provider_profiles")
    additions = (
        sa.Column("business_place_id", sa.String(255), nullable=True),
        sa.Column("unique_enterprise_id", sa.String(128), nullable=True),
        sa.Column("qualification_application_id", sa.Integer(), nullable=True),
    )
    missing_profile_columns = [column for column in additions if column.name not in profile_columns]
    if missing_profile_columns:
        with op.batch_alter_table("provider_profiles") as batch_op:
            for column in missing_profile_columns:
                batch_op.add_column(column)

    inspector = sa.inspect(bind)
    missing_unique = not _has_unique_columns(
        inspector, "provider_profiles", {"qualification_application_id"}
    )
    missing_foreign_key = not _has_foreign_key_columns(
        inspector, "provider_profiles", {"qualification_application_id"}
    )
    if missing_unique or missing_foreign_key:
        with op.batch_alter_table("provider_profiles") as batch_op:
            if missing_foreign_key:
                batch_op.create_foreign_key(
                    "fk_provider_profile_qualification_application",
                    "qualification_verification_applications",
                    ["qualification_application_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            if missing_unique:
                batch_op.create_unique_constraint(
                    "uq_provider_profile_qualification_application",
                    ["qualification_application_id"],
                )

    inspector = sa.inspect(bind)
    if "ix_provider_profiles_unique_enterprise_id" not in _index_names(
        inspector, "provider_profiles"
    ):
        op.create_index(
            "ix_provider_profiles_unique_enterprise_id",
            "provider_profiles",
            ["unique_enterprise_id"],
            unique=True,
        )

    ProviderApprovedService.__table__.create(bind=bind, checkfirst=True)
    ProviderServiceArea.__table__.create(bind=bind, checkfirst=True)

    bind.execute(
        sa.text(
            "UPDATE users SET identity_verification_status = 'not_submitted', "
            "qualification_verification_status = 'locked' "
            "WHERE role = 'provider' AND identity_verification_status IS NULL"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE users SET identity_verification_status = 'approved', "
            "qualification_verification_status = 'approved' WHERE id IN "
            "(SELECT user_id FROM provider_profiles WHERE verification_status = 'approved')"
        )
    )

    profiles = bind.execute(
        sa.text(
            "SELECT id, tags, service_location_id FROM provider_profiles "
            "WHERE verification_status = 'approved'"
        )
    ).mappings()
    for profile in profiles:
        for service in filter(None, (profile["tags"] or "").split(",")):
            normalized_service = service.strip()
            exists = bind.execute(
                sa.text(
                    "SELECT 1 FROM provider_approved_services "
                    "WHERE provider_profile_id = :profile_id "
                    "AND service_category = :service"
                ),
                {"profile_id": profile["id"], "service": normalized_service},
            ).first()
            if not exists:
                bind.execute(
                    sa.text(
                        "INSERT INTO provider_approved_services "
                        "(provider_profile_id, service_category, is_enabled) "
                        "VALUES (:profile_id, :service, :enabled)"
                    ),
                    {
                        "profile_id": profile["id"],
                        "service": normalized_service,
                        "enabled": True,
                    },
                )
        if profile["service_location_id"] is not None:
            exists = bind.execute(
                sa.text(
                    "SELECT 1 FROM provider_service_areas "
                    "WHERE provider_profile_id = :profile_id "
                    "AND service_location_id = :location_id"
                ),
                {
                    "profile_id": profile["id"],
                    "location_id": profile["service_location_id"],
                },
            ).first()
            if not exists:
                bind.execute(
                    sa.text(
                        "INSERT INTO provider_service_areas "
                        "(provider_profile_id, service_location_id) "
                        "VALUES (:profile_id, :location_id)"
                    ),
                    {
                        "profile_id": profile["id"],
                        "location_id": profile["service_location_id"],
                    },
                )

    inspector = sa.inspect(bind)
    obsolete_columns = _columns(inspector, "provider_profiles") & {
        "service_radius_km",
        "experience_years",
    }
    if obsolete_columns:
        with op.batch_alter_table("provider_profiles") as batch_op:
            for column_name in sorted(obsolete_columns):
                batch_op.drop_column(column_name)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    profile_columns = _columns(inspector, "provider_profiles")
    with op.batch_alter_table("provider_profiles") as batch_op:
        if "service_radius_km" not in profile_columns:
            batch_op.add_column(
                sa.Column("service_radius_km", sa.Float(), nullable=False, server_default="10")
            )
        if "experience_years" not in profile_columns:
            batch_op.add_column(
                sa.Column("experience_years", sa.Integer(), nullable=False, server_default="0")
            )

    inspector = sa.inspect(bind)
    for table_name in ("provider_service_areas", "provider_approved_services"):
        if inspector.has_table(table_name):
            op.drop_table(table_name)

    inspector = sa.inspect(bind)
    if "ix_provider_profiles_unique_enterprise_id" in _index_names(
        inspector, "provider_profiles"
    ):
        op.drop_index(
            "ix_provider_profiles_unique_enterprise_id", table_name="provider_profiles"
        )
    profile_columns = _columns(inspector, "provider_profiles")
    if profile_columns & {
        "qualification_application_id",
        "unique_enterprise_id",
        "business_place_id",
    }:
        unique_names = _unique_names(inspector, "provider_profiles")
        foreign_key_names = _foreign_key_names(inspector, "provider_profiles")
        with op.batch_alter_table("provider_profiles") as batch_op:
            if "uq_provider_profile_qualification_application" in unique_names:
                batch_op.drop_constraint(
                    "uq_provider_profile_qualification_application", type_="unique"
                )
            if "fk_provider_profile_qualification_application" in foreign_key_names:
                batch_op.drop_constraint(
                    "fk_provider_profile_qualification_application", type_="foreignkey"
                )
            for column_name in (
                "qualification_application_id",
                "unique_enterprise_id",
                "business_place_id",
            ):
                if column_name in profile_columns:
                    batch_op.drop_column(column_name)

    inspector = sa.inspect(bind)
    for table_name in (
        "qualification_verification_services",
        "qualification_verification_files",
        "qualification_verification_applications",
        "identity_verification_files",
        "identity_verification_applications",
    ):
        if inspector.has_table(table_name):
            op.drop_table(table_name)

    inspector = sa.inspect(bind)
    user_columns = _columns(inspector, "users")
    if "qualification_verification_status" in user_columns:
        op.drop_column("users", "qualification_verification_status")
    if "identity_verification_status" in user_columns:
        op.drop_column("users", "identity_verification_status")
