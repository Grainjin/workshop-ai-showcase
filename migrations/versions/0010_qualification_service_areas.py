"""Add service area snapshots to qualification applications."""

import sqlalchemy as sa
from alembic import op

from backend.models.provider_verification import QualificationVerificationServiceArea


revision = "0010_qualification_areas"
down_revision = "0009_provider_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    QualificationVerificationServiceArea.__table__.create(bind=bind, checkfirst=True)
    # Preserve the best available snapshot for applications approved before this
    # field existed. Pending legacy applications must be rejected and resubmitted.
    bind.execute(
        sa.text(
            "INSERT INTO qualification_verification_service_areas "
            "(application_id, service_location_id) "
            "SELECT profiles.qualification_application_id, areas.service_location_id "
            "FROM provider_profiles AS profiles "
            "JOIN provider_service_areas AS areas "
            "ON areas.provider_profile_id = profiles.id "
            "WHERE profiles.qualification_application_id IS NOT NULL "
            "AND NOT EXISTS ("
            "SELECT 1 FROM qualification_verification_service_areas AS snapshots "
            "WHERE snapshots.application_id = profiles.qualification_application_id "
            "AND snapshots.service_location_id = areas.service_location_id)"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    QualificationVerificationServiceArea.__table__.drop(bind=bind, checkfirst=True)
