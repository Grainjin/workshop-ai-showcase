import re
from datetime import date, datetime, time
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from backend.constants import ALLOWED_PROVIDER_TAGS

from backend.schemas.common import *  # noqa: F403


class UserRole(str, Enum):
    customer = "customer"
    provider = "provider"
    admin = "admin"


class SocialAuthProvider(str, Enum):
    google = "google"
    apple = "apple"


def _validate_six_digit_code(value: str) -> str:
    # Shape check only. Email codes are checked against the mailed code;
    # phone verification is still a demo that accepts any six digits.
    if not re.fullmatch(r"\d{6}", value or ""):
        raise ValueError("Verification code must be exactly 6 digits")
    return value


class UserRegister(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str = Field(min_length=8)
    confirm_password: str
    tos_accepted: bool = Field(strict=True)
    role: UserRole
    # The code mailed by POST /register/email-code; proves the address first.
    email_code: str

    @field_validator("email_code")
    @classmethod
    def validate_email_code(cls, value):
        return _validate_six_digit_code(value)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Name cannot be empty")
        return value.strip()

    @model_validator(mode="after")
    def validate_confirmation_and_terms(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        if not self.tos_accepted:
            raise ValueError("Terms must be accepted")
        if len(f"{self.first_name} {self.last_name}") > 255:
            raise ValueError("Combined name is too long")
        return self


class UserResponse(BaseModel):
    id: int
    name: str
    first_name: str | None = None
    last_name: str | None = None
    tos_accepted_at: datetime | None = None
    email: str
    role: UserRole
    avatar_url: str | None = None
    is_active: bool = True
    is_banned: bool = False
    email_verified: bool = False
    phone_verified: bool = False
    identity_verification_status: str | None = None
    qualification_verification_status: str | None = None
    last_login_at: str | None = None
    created_at: str | None = None


class UserProfileUpdate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Name cannot be empty")

        return value.strip()


class UserProfilePatch(BaseModel):
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    @field_validator("name", "first_name", "last_name")
    @classmethod
    def validate_name_not_empty(cls, value):
        if value is None:
            return value

        if not value.strip():
            raise ValueError("Name cannot be empty")

        return value.strip()

    @model_validator(mode="after")
    def validate_name_source(self):
        if self.name is not None and (self.first_name is not None or self.last_name is not None):
            raise ValueError("Use name or split name fields, not both")
        if self.name is not None and len(self.name) > 255:
            raise ValueError("Name is too long")
        return self


class AvatarUploadResponse(BaseModel):
    original_file_name: str
    file_name: str
    file_url: str
    content_type: str
    size: int
    user: UserResponse


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class DemoLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["customer", "provider", "admin"]


class SocialLoginRequest(BaseModel):
    provider: SocialAuthProvider
    id_token: str
    # The raw nonce the app generated before sign-in. Apple tokens carry its
    # SHA-256 and must match; Google tokens carry it as is when one was sent.
    nonce: str | None = None
    # Role and Terms only matter when this sign-in creates the account.
    role: UserRole = UserRole.customer
    tos_accepted: bool = False
    # Apple returns the user's name to the app once, on first consent, and
    # never inside the token, so the app forwards it.
    first_name: str | None = None
    last_name: str | None = None
    name: str | None = None

    @field_validator("id_token")
    @classmethod
    def validate_id_token_not_empty(cls, value):
        if not value.strip():
            raise ValueError("ID token cannot be empty")

        return value

    @field_validator("name", "first_name", "last_name", "nonce")
    @classmethod
    def blank_to_none(cls, value):
        if value is None or not value.strip():
            return None

        return value.strip()


class SocialLoginResponseData(TokenResponse):
    provider: SocialAuthProvider
    is_new_user: bool
    linked_social_account: bool


class OAuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterResponseData(BaseModel):
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Refresh token cannot be empty")

        return value


class MockVerificationRequest(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def validate_demo_code(cls, value):
        return _validate_six_digit_code(value)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)

    @field_validator("current_password")
    @classmethod
    def validate_current_password_not_empty(cls, value):
        if not value:
            raise ValueError("Current password cannot be empty")
        return value

    @model_validator(mode="after")
    def validate_new_password_differs(self):
        if self.new_password == self.current_password:
            raise ValueError("New password must be different from the current password")
        return self


class EmailCodeVerifyRequest(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, value):
        return _validate_six_digit_code(value)


class RegisterEmailCodeRequest(BaseModel):
    email: EmailStr


class SendEmailCodeRequest(BaseModel):
    purpose: Literal["verify_email", "change_email"]
    new_email: EmailStr | None = None

    @model_validator(mode="after")
    def validate_new_email_for_change(self):
        if self.purpose == "change_email" and self.new_email is None:
            raise ValueError("new_email is required to change the email")
        return self


class SendEmailCodeResponse(BaseModel):
    sent_to: str
    expires_in_seconds: int
    resend_after_seconds: int


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr
    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, value):
        return _validate_six_digit_code(value)


class AdminUserStatusUpdate(BaseModel):
    is_active: bool | None = None
    is_banned: bool | None = None

    @model_validator(mode="after")
    def validate_at_least_one_field(self):
        if self.is_active is None and self.is_banned is None:
            raise ValueError("At least one status field is required")

        return self
