from enum import Enum

from pydantic import BaseModel, EmailStr, field_validator, model_validator


class SubmerchantType(str, Enum):
    personal = "PERSONAL"
    private_company = "PRIVATE_COMPANY"
    limited_or_joint_stock_company = "LIMITED_OR_JOINT_STOCK_COMPANY"


class SubmerchantStatus(str, Enum):
    draft = "draft"
    active = "active"
    rejected = "rejected"
    update_failed = "update_failed"


class ProviderSubmerchantUpsert(BaseModel):
    submerchant_type: SubmerchantType
    name: str
    email: EmailStr
    gsm_number: str
    address: str
    iban: str
    contact_name: str | None = None
    contact_surname: str | None = None
    identity_number: str | None = None
    tax_office: str | None = None
    tax_number: str | None = None
    legal_company_title: str | None = None
    currency: str = "TRY"

    @field_validator(
        "contact_name",
        "contact_surname",
        "identity_number",
        "tax_office",
        "tax_number",
        "legal_company_title",
    )
    @classmethod
    def strip_optional_text(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("name", "gsm_number", "address", "iban")
    @classmethod
    def validate_required_text(cls, value):
        if not value.strip():
            raise ValueError("This field cannot be empty")
        return value.strip()

    @field_validator("iban")
    @classmethod
    def validate_turkish_iban(cls, value):
        value = value.replace(" ", "").strip().upper()
        if len(value) != 26 or not value.startswith("TR") or not value[2:].isdigit():
            raise ValueError("IBAN must be a valid Turkish IBAN")

        rearranged = value[4:] + value[:4]
        remainder = 0
        for character in rearranged:
            digits = str(ord(character) - ord("A") + 10) if character.isalpha() else character
            for digit in digits:
                remainder = (remainder * 10 + int(digit)) % 97
        if remainder != 1:
            raise ValueError("IBAN checksum is invalid")
        return value

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value):
        value = value.upper().strip()
        if value != "TRY":
            raise ValueError("Only TRY is supported for the current payment flow")
        return value

    @model_validator(mode="after")
    def validate_type_fields(self):
        if self.submerchant_type == SubmerchantType.personal:
            required = {
                "contact_name": self.contact_name,
                "contact_surname": self.contact_surname,
                "identity_number": self.identity_number,
            }
        else:
            required = {
                "tax_office": self.tax_office,
                "legal_company_title": self.legal_company_title,
            }
            if self.submerchant_type == SubmerchantType.limited_or_joint_stock_company:
                required["tax_number"] = self.tax_number

        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"Missing required fields for {self.submerchant_type.value}: {', '.join(missing)}"
            )
        return self


class ProviderSubmerchantResponse(BaseModel):
    id: int
    provider_profile_id: int
    submerchant_type: SubmerchantType
    submerchant_external_id: str
    name: str
    email: EmailStr
    gsm_number: str
    address: str
    iban: str
    contact_name: str | None = None
    contact_surname: str | None = None
    identity_number: str | None = None
    tax_office: str | None = None
    tax_number: str | None = None
    legal_company_title: str | None = None
    currency: str
    status: SubmerchantStatus
    iyzico_error_code: str | None = None
    iyzico_error_message: str | None = None
    last_synced_at: str | None = None
    created_at: str
    updated_at: str


class SettlementStatus(str, Enum):
    pending = "pending"
    approve_requested = "approve_requested"
    approved = "approved"
    approval_failed = "approval_failed"
    disapproved = "disapproved"
