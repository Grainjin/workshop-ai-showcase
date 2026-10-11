from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.clock import utc_now
from backend.database import Base


class ProviderProfile(Base):
    __tablename__ = "provider_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False)
    phone_number: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    address: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    service_province: Mapped[str] = mapped_column(String(128), nullable=False)
    service_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    business_place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unique_enterprise_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True, index=True
    )
    qualification_application_id: Mapped[int | None] = mapped_column(
        ForeignKey("qualification_verification_applications.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    tags: Mapped[str] = mapped_column(String(512), nullable=False)
    certificate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    certificate_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    hourly_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, default="personal")
    identity_verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    qualification_verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    verification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProviderCertificateFile(Base):
    __tablename__ = "provider_certificate_files"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider_profile_id: Mapped[int] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    media_type: Mapped[str] = mapped_column(String(32), nullable=False, default="document")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ProviderAvailability(Base):
    __tablename__ = "provider_availabilities"
    __table_args__ = (
        UniqueConstraint(
            "provider_profile_id",
            "weekday",
            name="uq_provider_availability_weekday",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider_profile_id: Mapped[int] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[str] = mapped_column(String(8), nullable=False)
    end_time: Mapped[str] = mapped_column(String(8), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProviderAvailabilityOverride(Base):
    __tablename__ = "provider_availability_overrides"
    __table_args__ = (
        UniqueConstraint(
            "provider_profile_id",
            "override_date",
            name="uq_provider_availability_override_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider_profile_id: Mapped[int] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    override_date: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    start_time: Mapped[str] = mapped_column(String(8), nullable=False)
    end_time: Mapped[str] = mapped_column(String(8), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ProviderPortfolio(Base):
    __tablename__ = "provider_portfolios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider_profile_id: Mapped[int] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    media_type: Mapped[str] = mapped_column(String(32), nullable=False, default="image")
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    verification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ProviderPortfolioMedia(Base):
    __tablename__ = "provider_portfolio_media"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("provider_portfolios.id", ondelete="CASCADE"), index=True, nullable=False
    )
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    media_type: Mapped[str] = mapped_column(String(32), nullable=False, default="image")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ProviderVerificationHistory(Base):
    __tablename__ = "provider_verification_histories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider_profile_id: Mapped[int] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    changed_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    old_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    verification_step: Mapped[str] = mapped_column(
        String(32), nullable=False, default="qualification"
    )
