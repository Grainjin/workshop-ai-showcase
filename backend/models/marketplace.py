"""Marketplace onboarding and provider settlement models."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.clock import utc_now
from backend.database import Base


class ProviderSubmerchant(Base):
    __tablename__ = "provider_submerchants"
    __table_args__ = (
        UniqueConstraint(
            "provider_profile_id",
            name="uq_provider_submerchant_provider_profile",
        ),
        UniqueConstraint(
            "submerchant_external_id",
            name="uq_provider_submerchant_external_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider_profile_id: Mapped[int] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    submerchant_type: Mapped[str] = mapped_column(String(32), nullable=False)
    submerchant_external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    submerchant_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    gsm_number: Mapped[str] = mapped_column(String(64), nullable=False)
    address: Mapped[str] = mapped_column(String(512), nullable=False)
    iban: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_surname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    identity_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tax_office: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    legal_company_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="TRY")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    iyzico_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    iyzico_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class PaymentSettlement(Base):
    __tablename__ = "payment_settlements"
    __table_args__ = (
        UniqueConstraint("payment_id", name="uq_payment_settlement_payment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider_profile_id: Mapped[int] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    platform_commission_rate: Mapped[Decimal] = mapped_column(
        Numeric(6, 5), nullable=False
    )
    platform_commission_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    provider_share_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    payment_transaction_id: Mapped[str | None] = mapped_column(
        String(128), index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    approve_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    iyzico_commission_rate_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    iyzico_commission_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    blockage_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 8), nullable=True
    )
    blockage_resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider_payout_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    merchant_payout_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    provider_recovery_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    recovery_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
