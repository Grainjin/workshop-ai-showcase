from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.clock import utc_now
from backend.database import Base


class IdentityVerificationApplication(Base):
    __tablename__ = "identity_verification_applications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    submitted_first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    submitted_last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IdentityVerificationFile(Base):
    __tablename__ = "identity_verification_files"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("identity_verification_applications.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class QualificationVerificationApplication(Base):
    __tablename__ = "qualification_verification_applications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unique_enterprise_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(64), nullable=False)
    business_address: Mapped[str] = mapped_column(String(512), nullable=False)
    business_place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    business_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QualificationVerificationFile(Base):
    __tablename__ = "qualification_verification_files"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("qualification_verification_applications.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class QualificationVerificationService(Base):
    __tablename__ = "qualification_verification_services"
    __table_args__ = (
        UniqueConstraint("application_id", "service_category", name="uq_qualification_service"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("qualification_verification_applications.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    service_category: Mapped[str] = mapped_column(String(64), nullable=False)


class QualificationVerificationServiceArea(Base):
    __tablename__ = "qualification_verification_service_areas"
    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "service_location_id",
            name="uq_qualification_service_area",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("qualification_verification_applications.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    service_location_id: Mapped[int] = mapped_column(
        ForeignKey("service_locations.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )


class ProviderApprovedService(Base):
    __tablename__ = "provider_approved_services"
    __table_args__ = (
        UniqueConstraint("provider_profile_id", "service_category", name="uq_provider_service"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider_profile_id: Mapped[int] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    service_category: Mapped[str] = mapped_column(String(64), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)


class ProviderServiceArea(Base):
    __tablename__ = "provider_service_areas"
    __table_args__ = (
        UniqueConstraint("provider_profile_id", "service_location_id", name="uq_provider_area"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider_profile_id: Mapped[int] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    service_location_id: Mapped[int] = mapped_column(
        ForeignKey("service_locations.id", ondelete="CASCADE"), index=True, nullable=False
    )
