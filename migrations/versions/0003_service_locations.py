"""Add hierarchical service locations and profile references."""

import sqlalchemy as sa
from alembic import op

revision = "0003_service_locations"
down_revision = "0002_user_verification_flags"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _add_profile_location_column(table_name: str) -> None:
    inspector = _inspector()
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if "service_location_id" not in columns:
        op.add_column(
            table_name,
            sa.Column(
                "service_location_id",
                sa.Integer(),
                sa.ForeignKey(
                    "service_locations.id",
                    name=f"fk_{table_name}_service_location",
                    ondelete="SET NULL",
                ),
                nullable=True,
            ),
        )

    index_name = f"ix_{table_name}_service_location_id"
    indexes = {index["name"] for index in _inspector().get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, ["service_location_id"])


def upgrade() -> None:
    if not _inspector().has_table("service_locations"):
        op.create_table(
            "service_locations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("level", sa.String(length=16), nullable=False),
            sa.ForeignKeyConstraint(
                ["parent_id"],
                ["service_locations.id"],
                name="fk_service_locations_parent_id",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint("code", name="uq_service_locations_code"),
            sa.UniqueConstraint(
                "parent_id",
                "level",
                "name",
                name="uq_service_locations_parent_level_name",
            ),
        )
        op.create_index(
            "ix_service_locations_id", "service_locations", ["id"], unique=False
        )
        op.create_index(
            "ix_service_locations_parent_id", "service_locations", ["parent_id"]
        )
        op.create_index(
            "ix_service_locations_level", "service_locations", ["level"]
        )
        op.create_index(
            "ix_service_locations_parent_level",
            "service_locations",
            ["parent_id", "level"],
        )

    _add_profile_location_column("provider_profiles")
    _add_profile_location_column("customer_profiles")


def downgrade() -> None:
    inspector = _inspector()
    for table_name in ("provider_profiles", "customer_profiles"):
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        index_name = f"ix_{table_name}_service_location_id"
        indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        if index_name in indexes:
            op.drop_index(index_name, table_name=table_name)
        if "service_location_id" in columns:
            op.drop_column(table_name, "service_location_id")

    if inspector.has_table("service_locations"):
        op.drop_table("service_locations")
