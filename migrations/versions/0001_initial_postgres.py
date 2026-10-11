"""Initial PostgreSQL schema."""

from alembic import op

from backend.database import Base
from backend import models  # noqa: F401

revision = "0001_initial_postgres"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
