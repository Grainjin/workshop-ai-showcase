from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.clock import utc_now
from backend.database import Base


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    phone_number: Mapped[str] = mapped_column(String(64), nullable=False)
    address: Mapped[str] = mapped_column(String(512), nullable=False)
    service_province: Mapped[str] = mapped_column(String(128), nullable=False)
    service_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    current_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    default_service_address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    default_service_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    default_service_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class CustomerSearchHistory(Base):
    __tablename__ = "customer_search_histories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    last_provider_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    last_provider_tag: Mapped[str] = mapped_column(
        String(64), nullable=False, default="cleaning"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class FavoriteProvider(Base):
    __tablename__ = "favorite_providers"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "provider_profile_id",
            name="uq_customer_provider_favorite",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider_profile_id: Mapped[int] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
