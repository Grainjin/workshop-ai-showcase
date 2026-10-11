from datetime import date, datetime, time
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from backend.constants import ALLOWED_PROVIDER_TAGS

from backend.schemas.auth import UserResponse
from backend.schemas.common import *  # noqa: F403
from backend.schemas.provider import ProviderProfileWithRatingResponse

class ChatMessageType(str, Enum):
    text = "text"
    attachment = "attachment"
    booking_created = "booking_created"
    booking_status = "booking_status"

class ChatMessageCreate(BaseModel):
    message: str | None = None
    attachment_ids: list[int] = Field(default_factory=list)

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Message cannot be empty")

        return value

    @model_validator(mode="after")
    def validate_message_or_attachment(self):
        if self.message is None and not self.attachment_ids:
            raise ValueError("Message or attachment_ids is required")

        return self

class ChatMessageAttachmentResponse(BaseModel):
    id: int
    chat_room_id: int
    chat_message_id: int | None = None
    uploaded_by_user_id: int
    original_file_name: str
    file_name: str
    file_url: str
    content_type: str
    size: int
    created_at: str

class ChatMessageResponse(BaseModel):
    id: int
    chat_room_id: int
    sender_id: int
    sender: UserResponse | None = None
    message: str
    message_type: ChatMessageType
    related_type: str | None = None
    related_id: int | None = None
    metadata: dict[str, Any] | None = None
    attachments: list[ChatMessageAttachmentResponse] = Field(default_factory=list)
    created_at: str
    read_at: str | None = None

class ChatRoomResponse(BaseModel):
    id: int
    customer_id: int
    provider_profile_id: int
    created_at: str
    last_message_at: str | None = None
    customer: UserResponse | None = None
    customer_online: bool
    provider: ProviderProfileWithRatingResponse | None = None
    provider_online: bool
    last_message: ChatMessageResponse | None = None
    unread_count: int | None = None

class ChatMessageSendResponseData(BaseModel):
    chat_message: ChatMessageResponse

