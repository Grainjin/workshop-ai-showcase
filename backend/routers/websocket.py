"""Real-time chat WebSocket.

Connect to `/ws/chats/{chat_room_id}` or `/ws/me`, then send
`{"type": "auth", "token": "<access_token>"}` as the first message.
Messages are persisted; WebSocket handles presence, read state, and push.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.encoders import jsonable_encoder

from backend import models
from backend.auth import ensure_email_verified, get_user_from_token
from backend.database import SessionLocal
from backend.schemas import NotificationRelatedType, NotificationType
from backend.services.redis_service import set_user_offline, set_user_online
from backend.utils.chat import (
    build_chat_attachment_metadata,
    dump_chat_message_metadata,
    ensure_chat_room_member,
    format_chat_message_response,
    get_chat_message_recipient_user_id,
    get_chat_room_or_404,
    get_pending_chat_attachments_or_400,
    mark_chat_room_messages_as_read,
    register_chat_message_unread,
)
from backend.utils.notification import create_notification
from backend.utils.websocket_manager import websocket_manager
from backend.utils.router import ApiRouter
from backend.core.clock import utc_now

router = ApiRouter(tags=["WebSocket"])


async def close_websocket_with_error(
    websocket: WebSocket,
    message: str,
    *,
    accepted: bool = False,
):
    if not accepted:
        await websocket.accept()
    await websocket.send_json(
        {
            "type": "error",
            "message": message,
        }
    )
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


async def authenticate_websocket(websocket: WebSocket) -> str | None:
    await websocket.accept()
    try:
        payload = await websocket.receive_json()
    except WebSocketDisconnect:
        return None
    except ValueError:
        await close_websocket_with_error(
            websocket,
            "Authentication required",
            accepted=True,
        )
        return None

    if not isinstance(payload, dict) or payload.get("type") != "auth":
        await close_websocket_with_error(
            websocket,
            "Authentication required",
            accepted=True,
        )
        return None

    token = payload.get("token")
    if not token or not isinstance(token, str):
        await close_websocket_with_error(
            websocket,
            "Missing token",
            accepted=True,
        )
        return None

    return token


async def forward_chat_presence_event(
    event_type: str,
    chat_room: models.ChatRoom,
    current_user: models.User,
    db,
):
    recipient_user_id = get_chat_message_recipient_user_id(
        chat_room,
        current_user,
        db,
    )
    if not recipient_user_id:
        return

    await websocket_manager.send_to_user(
        recipient_user_id,
        {
            "type": event_type,
            "chat_room_id": chat_room.id,
            "user_id": current_user.id,
        },
    )


async def forward_user_presence_event_to_chat_rooms(
    event_type: str,
    current_user: models.User,
    db,
):
    chat_rooms = []

    if current_user.role == "customer":
        chat_rooms = (
            db.query(models.ChatRoom)
            .filter(models.ChatRoom.customer_id == current_user.id)
            .all()
        )

        for chat_room in chat_rooms:
            provider_profile = (
                db.query(models.ProviderProfile)
                .filter(models.ProviderProfile.id == chat_room.provider_profile_id)
                .first()
            )
            if not provider_profile:
                continue

            await websocket_manager.send_to_user(
                provider_profile.user_id,
                {
                    "type": event_type,
                    "chat_room_id": chat_room.id,
                    "user_id": current_user.id,
                },
            )

        return

    if current_user.role == "provider":
        provider_profile = (
            db.query(models.ProviderProfile)
            .filter(models.ProviderProfile.user_id == current_user.id)
            .first()
        )
        if not provider_profile:
            return

        chat_rooms = (
            db.query(models.ChatRoom)
            .filter(models.ChatRoom.provider_profile_id == provider_profile.id)
            .all()
        )

        for chat_room in chat_rooms:
            await websocket_manager.send_to_user(
                chat_room.customer_id,
                {
                    "type": event_type,
                    "chat_room_id": chat_room.id,
                    "user_id": current_user.id,
                },
            )


async def broadcast_user_presence_event(event_type: str, current_user: models.User):
    await websocket_manager.broadcast(
        {
            "type": event_type,
            "user_id": current_user.id,
            "role": current_user.role,
        }
    )


@router.websocket("/ws/chats/{chat_room_id}")
async def chat_websocket(
    websocket: WebSocket,
    chat_room_id: int,
):
    token = await authenticate_websocket(websocket)
    if not token:
        return

    db = SessionLocal()
    current_user = None
    chat_room = None
    is_connected = False

    try:
        try:
            current_user = ensure_email_verified(get_user_from_token(token, db))
            chat_room = get_chat_room_or_404(chat_room_id, db)
            ensure_chat_room_member(chat_room, current_user, db)
        except HTTPException as error:
            await close_websocket_with_error(
                websocket,
                str(error.detail),
                accepted=True,
            )
            return

        was_online = websocket_manager.is_online(current_user.id)
        await websocket_manager.connect(
            current_user.id,
            websocket,
            already_accepted=True,
        )
        is_connected = True
        set_user_online(current_user.id)

        await websocket.send_json(
            {
                "type": "connection_ready",
                "user_id": current_user.id,
                "chat_room_id": chat_room.id,
            }
        )
        await forward_chat_presence_event(
            "user_online",
            chat_room,
            current_user,
            db,
        )
        if not was_online:
            await broadcast_user_presence_event("user_online", current_user)

        while True:
            # Each WebSocket message should be a JSON object with a type field.
            try:
                data = await websocket.receive_json()
            except ValueError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Message must be valid JSON",
                    }
                )
                continue

            if not isinstance(data, dict):
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Message must be a JSON object",
                    }
                )
                continue

            event_type = data.get("type", "chat_message")

            if event_type == "ping":
                # ping/pong keeps presence alive; Redis online:user:{id} is renewed.
                set_user_online(current_user.id)
                await websocket.send_json({"type": "pong"})
                continue

            if event_type in ["typing_start", "typing_stop"]:
                # Typing indicators are forwarded only, not persisted.
                await forward_chat_presence_event(
                    event_type,
                    chat_room,
                    current_user,
                    db,
                )
                continue

            if event_type == "mark_read":
                # Read receipts are persisted and notify the other party.
                read_result = mark_chat_room_messages_as_read(
                    chat_room,
                    current_user,
                    db,
                )
                db.commit()

                read_at = jsonable_encoder(read_result["read_at"])

                await websocket.send_json(
                    {
                        "type": "chat_read_summary",
                        "chat_room_id": chat_room.id,
                        "updated_count": read_result["updated_count"],
                        "unread_count": read_result["unread_count"],
                        "message_ids": read_result["message_ids"],
                        "read_at": read_at,
                    }
                )

                if read_result["updated_count"] > 0:
                    recipient_user_id = get_chat_message_recipient_user_id(
                        chat_room,
                        current_user,
                        db,
                    )
                    if recipient_user_id:
                        await websocket_manager.send_to_user(
                            recipient_user_id,
                            {
                                "type": "chat_messages_read",
                                "chat_room_id": chat_room.id,
                                "reader_user_id": current_user.id,
                                "message_ids": read_result["message_ids"],
                                "read_at": read_at,
                            },
                        )
                continue

            if event_type != "chat_message":
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Unsupported websocket event type",
                    }
                )
                continue

            # Chat messages are saved first, then pushed over WebSocket.
            message_value = data.get("message")
            if message_value is None:
                message_text = ""
            elif isinstance(message_value, str):
                message_text = message_value.strip()
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Message must be a string",
                    }
                )
                continue

            raw_attachment_ids = data.get("attachment_ids", [])
            if raw_attachment_ids is None:
                raw_attachment_ids = []

            if not isinstance(raw_attachment_ids, list):
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "attachment_ids must be a list",
                    }
                )
                continue

            attachment_ids = []
            invalid_attachment_ids = False
            for attachment_id in raw_attachment_ids:
                if isinstance(attachment_id, bool):
                    invalid_attachment_ids = True
                    break
                try:
                    attachment_ids.append(int(attachment_id))
                except (TypeError, ValueError):
                    invalid_attachment_ids = True
                    break

            if invalid_attachment_ids:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "attachment_ids must contain integer ids",
                    }
                )
                continue

            if not message_text and not attachment_ids:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Message or attachment_ids is required",
                    }
                )
                continue

            try:
                attachments = get_pending_chat_attachments_or_400(
                    attachment_ids,
                    chat_room,
                    current_user,
                    db,
                )
            except HTTPException as error:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": str(error.detail),
                    }
                )
                continue

            now = utc_now()
            chat_message = models.ChatMessage(
                chat_room_id=chat_room.id,
                sender_id=current_user.id,
                message=message_text,
                message_type="attachment" if attachments else "text",
                related_type=None,
                related_id=None,
                metadata_json=(
                    dump_chat_message_metadata(
                        build_chat_attachment_metadata(attachments)
                    )
                    if attachments
                    else None
                ),
                created_at=now,
                read_at=None,
            )
            chat_room.last_message_at = now
            db.add(chat_message)
            db.flush()
            for attachment in attachments:
                attachment.chat_message_id = chat_message.id

            recipient_user_id = get_chat_message_recipient_user_id(
                chat_room,
                current_user,
                db,
            )

            if recipient_user_id:
                create_notification(
                    recipient_user_id,
                    "New chat message",
                    (
                        f"You received a new chat message with {len(attachments)} attachment(s)"
                        if attachments
                        else "You received a new chat message"
                    ),
                    NotificationType.chat_message_received,
                    NotificationRelatedType.chat_room,
                    chat_room.id,
                    db,
                )

            db.commit()
            db.refresh(chat_message)
            db.refresh(chat_room)

            payload = {
                "type": "chat_message",
                "chat_room_id": chat_room.id,
                "chat_message": format_chat_message_response(chat_message, db),
            }
            recipient_unread_count = register_chat_message_unread(
                chat_message,
                chat_room,
                recipient_user_id,
                db,
            )

            await websocket_manager.send_to_user(
                current_user.id,
                {**payload, "unread_count": 0},
            )

            if recipient_user_id:
                await websocket_manager.send_to_user(
                    recipient_user_id,
                    {**payload, "unread_count": recipient_unread_count},
                )

    except WebSocketDisconnect:
        pass
    finally:
        if current_user and is_connected:
            websocket_manager.disconnect(current_user.id, websocket)

            if not websocket_manager.is_online(current_user.id):
                set_user_offline(current_user.id)
                if chat_room:
                    await forward_chat_presence_event(
                        "user_offline",
                        chat_room,
                        current_user,
                        db,
                    )
                await broadcast_user_presence_event("user_offline", current_user)

        db.close()


@router.websocket("/ws/me")
async def user_websocket(websocket: WebSocket):
    token = await authenticate_websocket(websocket)
    if not token:
        return

    db = SessionLocal()
    current_user = None
    is_connected = False

    try:
        try:
            current_user = ensure_email_verified(get_user_from_token(token, db))
        except HTTPException as error:
            await close_websocket_with_error(
                websocket,
                str(error.detail),
                accepted=True,
            )
            return

        was_online = websocket_manager.is_online(current_user.id)
        await websocket_manager.connect(
            current_user.id,
            websocket,
            already_accepted=True,
        )
        is_connected = True
        set_user_online(current_user.id)

        await websocket.send_json(
            {
                "type": "connection_ready",
                "user_id": current_user.id,
            }
        )
        if not was_online:
            await forward_user_presence_event_to_chat_rooms(
                "user_online",
                current_user,
                db,
            )
            await broadcast_user_presence_event("user_online", current_user)

        while True:
            try:
                data = await websocket.receive_json()
            except ValueError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Message must be valid JSON",
                    }
                )
                continue

            if not isinstance(data, dict):
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Message must be a JSON object",
                    }
                )
                continue

            event_type = data.get("type")

            if event_type == "ping":
                set_user_online(current_user.id)
                await websocket.send_json({"type": "pong"})
                continue

            await websocket.send_json(
                {
                    "type": "error",
                    "message": "Unsupported websocket event type",
                }
            )

    except WebSocketDisconnect:
        pass
    finally:
        if current_user and is_connected:
            websocket_manager.disconnect(current_user.id, websocket)

            if not websocket_manager.is_online(current_user.id):
                set_user_offline(current_user.id)
                await forward_user_presence_event_to_chat_rooms(
                    "user_offline",
                    current_user,
                    db,
                )
                await broadcast_user_presence_event("user_offline", current_user)

        db.close()
