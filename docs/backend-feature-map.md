# Workshop AI Backend Feature Map

This document describes backend structure, core features, how the frontend should call the API, and which functions are internal-only.

## Summary

The frontend uses the backend in two main ways:

- **HTTP API** — most business features.
- **WebSocket** — real-time chat; messages are still persisted.

The frontend must **not** call Python internals directly, for example:

- `create_customer_booking_action()`
- `quote_provider_booking_action()`
- `prepare_booking_draft_action_tool()`
- `create_notification()`
- `sync_review_embedding()`

Routers, WebSocket handlers, or Celery tasks invoke those internally.

## Directory layout

```text
backend/
  main.py                 FastAPI entry, registers routers
  config.py               Environment and settings
  database.py             Database connection
  models/                 SQLAlchemy models
  schemas.py              Pydantic request/response models

  routers/                HTTP API and WebSocket entry points
  utils/                  Business actions, formatting, auth helpers
  services/               External services: Qwen, Redis, Milvus
  ai/                     Prompts, LangChain tools, tool-calling flow
  tasks/                  Celery background tasks
  uploads/                Local upload directory
  private_uploads/        Non-public identity and qualification documents
```

## Router layer

Routers are what the frontend calls.

| File | Responsibility | Typical caller |
|---|---|---|
| `routers/auth.py` | Register, login, social login, refresh, logout, current user, mock verify, change password/email | Web/mobile |
| `routers/public.py` | Public providers, reviews, portfolios, ratings | Guest / customer |
| `routers/customer.py` | Customer profile, favorites, chat, bookings, pay, refund, complaints, reviews | customer |
| `routers/provider.py` | Provider profile, verification, availability, portfolio, bookings, refunds | provider |
| `routers/provider_verification.py` | Identity/qualification applications, operation settings, service areas, protected files | provider |
| `routers/admin.py` | Users, provider verification, bookings/payments/refunds/complaints/reviews | admin |
| `routers/admin_verification.py` | Separate identity and qualification review queues and decisions | admin |
| `routers/shared.py` | Chat messages, notifications, booking details, attachments, status history | Authenticated users |
| `routers/ai.py` | AI chat, tools, pending actions, async tasks, Milvus sync | Users / admin |
| `routers/websocket.py` | Real-time chat WebSocket | customer / provider |

## Utils layer

Utils contain real business actions. Routers mostly validate input, enforce auth, and wrap responses.

| File | Role |
|---|---|
| `utils/customer_booking_actions.py` | Customer booking: create, cancel, pay, refund, reject quote, accept/reject completion |
| `utils/provider_booking_actions.py` | Provider booking: quote, reject, complete, approve/reject refund |
| `utils/booking.py` | Booking queries, formatting, status checks |
| `utils/payment.py` | Mock payment formatting |
| `utils/refund.py` | Refund formatting and status history |
| `utils/complaint.py` | Complaint formatting and status history |
| `utils/review.py` | Review formatting, rating stats, visibility |
| `utils/chat.py` | Chat rooms, messages, booking/system messages |
| `utils/websocket_manager.py` | WebSocket connections and push |
| `utils/notification.py` | Notifications and unread counts |
| `utils/notification_queue.py` | Notification delivery queue |
| `utils/review_embedding.py` | Single-review embedding sync |
| `utils/review_embedding_queue.py` | Review embedding job queue |
| `utils/upload.py` | File save, extension checks, URLs |
| `utils/location.py` | Distance and service-area checks |
| `utils/availability.py` | Provider availability |
| `utils/provider.py` | Provider profile queries and formatting |
| `utils/ai_chat_handler.py` | AI chat orchestration: tools, drafts, multi-turn, confirmation cards |
| `utils/ai_chat.py` | AI chat persistence and history |
| `utils/ai_context.py` | Actionable bookings/refunds for AI |
| `utils/ai_pending_action.py` | Pending AI actions: create, preview, confirm, cancel, expire |
| `utils/ai_tool_log.py` | AI tool call logs |
| `utils/response.py` | Unified success/error responses |
| `utils/router.py` | Default response models |

## Services layer

External integrations — not called directly by the frontend.

| File | Role |
|---|---|
| `services/ai_service.py` | Qwen chat, intent, need extraction, review summary, embeddings |
| `services/redis_service.py` | Redis presence, notification cache, AI recommendation context |
| `services/milvus_service.py` | Milvus collections, review vector CRUD/search |
| `services/social_auth_service.py` | Google/Apple id_token verification |

## AI layer

AI is chat + tool calling + user confirmation.

| File | Role |
|---|---|
| `ai/clients.py` | LangChain Qwen chat and embedding clients |
| `ai/prompts.py` | Prompt templates |
| `ai/parsers.py` | Pydantic parsers and fallbacks |
| `ai/tools.py` | Tool business implementations |
| `ai/langchain_tools.py` | StructuredTool wrappers |
| `ai/tool_calling.py` | Tool selection, execution, logging, final answers |

AI tool principles:

- Read-only tools (search, reviews, status) return results directly.
- DB-changing actions create `AIPendingAction` first.
- Frontend shows `confirmation_card`; user confirms via `/ai/actions/confirm`.
- Booking creation uses `booking_draft` until fields are complete.

## Tasks layer

Celery handles slow work off the request thread.

| File | Role |
|---|---|
| `tasks/celery_app.py` | Celery app, Redis broker/backend |
| `tasks/ai_tasks.py` | Async AI chat |
| `tasks/review_tasks.py` | Review embedding sync |
| `tasks/notification_tasks.py` | Notification delivery |

## Database models

Main tables (see `models/`):

| Model | Purpose |
|---|---|
| `User` | Account; role customer/provider/admin |
| `RefreshToken` | Refresh token storage |
| `SocialAccount` | Google/Apple linkage |
| `CustomerProfile` | Customer profile, address, location |
| `ProviderProfile` | Current approved provider display and operating data |
| `IdentityVerificationApplication` | Immutable real-name application snapshot and review result |
| `QualificationVerificationApplication` | Immutable business qualification snapshot and review result |
| `ProviderApprovedService` | Approved services and their current enabled state |
| `ProviderServiceArea` | Province/city/district coverage selected after approval |
| `ProviderAvailability` | Bookable hours |
| `ProviderPortfolio` | Portfolio items |
| `FavoriteProvider` | Customer favorites |
| `ChatRoom` | Customer–provider chat |
| `ChatMessage` | Chat messages |
| `ChatMessageAttachment` | Chat attachments |
| `Booking` | Bookings |
| `BookingAttachment` | Booking attachments |
| `BookingStatusHistory` | Booking status history |
| `Payment` | Mock payments |
| `RefundRequest` | Refund requests |
| `RefundRequestStatusHistory` | Refund status history |
| `Review` | Reviews |
| `Complaint` | Complaints |
| `ComplaintStatusHistory` | Complaint status history |
| `Notification` | In-app notifications |
| `AIChatMessage` | AI chat and draft context |
| `AIPendingAction` | Pending AI actions |
| `AIToolCallLog` | AI tool logs |
| `AsyncTask` | Celery task records |
| `ProviderVerificationHistory` | Provider verification history |

## Core flows

### Authentication

```text
POST /register -> User (email_verified and phone_verified start false)
POST /login -> access_token + refresh_token
POST /auth/verify-email or /auth/verify-phone -> any 6 digits, no SMTP/SMS
POST /auth/change-password -> current + new password
POST /auth/change-email -> new email + any 6 digits
POST /social-login -> verify id_token, upsert User/SocialAccount, tokens
POST /refresh-token -> new access_token
```

### Provider verification

```text
register provider -> identity not_submitted, qualification locked
POST /provider/identity-verification -> identity pending (name locked)
PUT /admin/identity-verifications/{id}/decision
-> approved unlocks qualification; rejected unlocks correction/resubmission
POST /provider/qualification-files/upload
POST /provider/qualification-verification -> qualification pending (application locked)
PUT /admin/qualification-verifications/{id}/decision
-> approved creates ProviderProfile + approved services and unlocks provider features
-> rejected unlocks a new qualification submission
PATCH /provider/operating-settings + PUT /provider/service-areas after approval
```

### Standard booking

```text
customer creates booking -> pending, chat room, notify provider
provider quotes -> quoted
customer pays -> accepted
provider completes -> awaiting_confirmation
customer accepts -> completed
```

### Refunds

```text
customer requests refund -> refunding, RefundRequest pending
provider approves -> refunded
provider rejects -> RefundRequest rejected, booking stays refunding
customer cancels refund -> prior booking status
```

### Complaints

```text
customer complains on accepted/awaiting_confirmation/completed
-> Complaint open, notify admin
admin resolves -> history + notify customer
```

### AI booking creation

```text
customer describes need to AI
-> search or booking_draft
-> booking_draft_missing_info if fields missing
-> frontend fills fields
-> AIPendingAction(create_booking) when complete
-> user confirms -> real booking
```

## Frontend reading list

- API usage: `docs/api-usage.md`
- Response conventions: `docs/backend-api-standard.md`
- Module map: this document
- Types: `backend/schemas.py` and OpenAPI
- Endpoints: `backend/routers/*.py`
- Booking status rules: `BookingStatus` in `schemas.py` and `BOOKING_STATUS_EXPLANATIONS` in `ai/tools.py`
