from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class ServiceLocation(Base):
    __tablename__ = "service_locations"
    __table_args__ = (
        UniqueConstraint("code", name="uq_service_locations_code"),
        UniqueConstraint(
            "parent_id",
            "level",
            "name",
            name="uq_service_locations_parent_level_name",
        ),
        Index("ix_service_locations_parent_level", "parent_id", "level"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_locations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
