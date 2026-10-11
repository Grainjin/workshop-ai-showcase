# Workshop AI Backend API Conventions

This document defines how Workshop AI backend endpoints should be structured. When adding new endpoints, follow these conventions for route placement, request parameters, response payloads, and error handling.

## 1. Route Groups

Endpoints are grouped by **who performs the action**, not by database table.

| Group | File | Purpose |
| --- | --- | --- |
| Auth | `backend/routers/auth.py` | Registration, login, social login, token refresh, logout, current user |
| Public | `backend/routers/public.py` | Queries available without authentication |
| Customer | `backend/routers/customer.py` | Actions only a customer can perform |
| Provider | `backend/routers/provider.py` | Actions only a provider can perform |
| Admin | `backend/routers/admin.py` | Actions only an admin can perform |
| Shared | `backend/routers/shared.py` | Resources viewable or usable by customers, providers, and admins |
| AI | `backend/routers/ai.py` | AI chat, recommendations, async tasks, Milvus/embedding maintenance |
| WebSocket | `backend/routers/websocket.py` | Real-time chat connections |

Placement rules:

- Put an endpoint in the router for the role that **initiates** the action.
- Admin review and moderation endpoints go in `admin.py` (e.g. list all users, reviews, complaints).
- Endpoints both customers and providers access the same way go in `shared.py` (e.g. booking details, chat messages, notifications).
- Public queries go in `public.py` and must not depend on a logged-in user.
- AI health checks, Milvus management, and full sync operations must be restricted to admin.

## 2. Path Naming

Paths use lowercase English and plural resource names.

Recommended patterns:

```text
GET    /providers
GET    /providers/{provider_id}
POST   /bookings
GET    /customer/bookings
PUT    /provider/bookings/{booking_id}/quote
PUT    /admin/complaints/{complaint_id}/status
```

Do not use verb-stacked paths:

```text
/getAllUsers
/createNewBooking
/providerAcceptBooking
```

HTTP method conventions:

| Method | Purpose |
| --- | --- |
| GET | Read data; must not modify the database |
| POST | Create a resource or trigger a non-idempotent action |
| PUT | Update full state or perform an explicit state transition |
| DELETE | Delete a resource or perform a delete-like operation |

Notes:

- Most booking state changes use `PUT` (quote, cancel, complete, reject acceptance).
- Operations that create new records (payments, complaints, reviews) use `POST`.

## 3. Authentication and Authorization

After login, send a Bearer token:

```http
Authorization: Bearer <access_token>
```

Import permission dependencies from `backend/auth.py`:

```python
Depends(get_current_user)
Depends(require_customer)
Depends(require_provider)
Depends(require_admin)
```

Usage:

| Dependency | Who can access |
| --- | --- |
| `get_current_user` | Any authenticated user |
| `require_customer` | Customers only |
| `require_provider` | Providers only |
| `require_admin` | Admins only |

Special endpoints:

- `POST /token` — OAuth2 password flow for Swagger **Authorize**; returns standard FastAPI OAuth format, not the unified wrapper.
- `POST /login` — Normal business login.
- `POST /social-login` — Google/Apple login. The frontend supplies a third-party `id_token`; the backend verifies it and issues platform `access_token` and `refresh_token`.
- `refresh_token` is only for refreshing login state, not for calling business APIs.

## 4. Unified Success Response

Except for `POST /token`, successful business responses use:

```json
{
  "success": true,
  "message": "Success",
  "data": {}
}
```

In code:

```python
from backend.utils.response import success_response

return success_response(data)
```

Custom message:

```python
return success_response(data, message="Profile updated successfully")
```

Empty data still uses the same structure:

```json
{
  "success": true,
  "message": "Logout successful",
  "data": null
}
```

OpenAPI response models have two layers:

- **Default layer:** All HTTP routers use `ApiRouter`. Endpoints without an explicit `response_model` show `ApiResponse[Any]` in Swagger.
- **Precise layer:** High-traffic frontend endpoints should gradually add concrete models, e.g. `ApiResponse[UserResponse]`, `ApiResponse[PaginatedData[ProviderProfileWithRatingResponse]]`.

When creating a new router, do not use FastAPI's `APIRouter` directly:

```python
from backend.utils.router import ApiRouter

router = ApiRouter(tags=["Customer"])
```

## 5. Pagination

List endpoints default to pagination.

Query parameters:

```text
page=1
page_size=20
```

Limits:

- `page` minimum: 1
- `page_size` minimum: 1
- `page_size` maximum: 100

Paginated response format:

```json
{
  "success": true,
  "message": "Success",
  "data": {
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 20,
    "total_pages": 0,
    "has_next": false,
    "has_previous": false
  }
}
```

Prefer:

```python
records, total, page, page_size = paginate_query(query, page, page_size)
return build_paginated_response(result, total, page, page_size)
```

`build_paginated_response()` already returns the unified success wrapper; do not wrap it again.

## 6. Unified Error Response

Errors are handled centrally in `backend/utils/errors.py`.

Standard error:

```json
{
  "success": false,
  "message": "Not found",
  "error": {
    "code": 404,
    "detail": "Not found",
    "errors": null
  }
}
```

Validation error:

```json
{
  "success": false,
  "message": "Validation error",
  "error": {
    "code": 422,
    "detail": null,
    "errors": [
      {
        "field": "email",
        "message": "Field required",
        "type": "missing"
      }
    ]
  }
}
```

Common HTTP status codes:

| Code | Scenario |
| --- | --- |
| 200 | Successful read or update |
| 201 | Resource created (enable when needed) |
| 400 | Business rule violation |
| 401 | Not logged in or invalid token |
| 403 | Logged in but insufficient permission |
| 404 | Resource not found |
| 409 | Conflict (e.g. duplicate registration) |
| 422 | Invalid request parameters |
| 500 | Unhandled server exception |

Raise errors with `HTTPException`; handlers convert them to the unified format.

## 7. Schema Naming

Request and response models live in `backend/schemas.py`.

Naming conventions:

| Type | Example |
| --- | --- |
| Create request | `BookingCreate` |
| Update request | `ProviderProfileUpdate` |
| Status update request | `BookingStatusUpdate` |
| Login response | `TokenResponse` |
| General business payload | Prefer formatter dicts for now |

Many existing endpoints return dicts from formatters. Add `response_model` incrementally for better Swagger accuracy; a full rewrite is not required.

## 8. Data Formats

### 8.1 Time

- Store timestamps as `datetime` in the database.
- Return ISO 8601 strings in API responses.
- Use `_at` suffix for point-in-time fields: `created_at`, `paid_at`, `quoted_at`.
- Use explicit fields for scheduled windows: `scheduled_start_time`, `scheduled_end_time`.

Provider availability uses weekday integers 1–7 (1 = Monday, 7 = Sunday) and `HH:MM` strings for `start_time` / `end_time` (e.g. `09:00`). MVP supports same-day windows only; overnight spans are not supported.

### 8.2 Money

- Store amounts as `Numeric` or another decimal-safe type in the database.
- Return two decimal places or stringified values in API responses to avoid floating-point display issues.
- Include `currency` in metadata where relevant (e.g. `"TRY"`).

### 8.3 Status

- Status values are lowercase English strings.
- Every state transition must validate the current status is allowed.
- Important transitions should write to a status history table.
- User-visible state changes should create a notification via `backend/utils/notification.py`.

Booking status values (`BookingStatus`):

```text
pending
quoted
awaiting_payment
accepted
rejected
refunding
refunded
awaiting_confirmation
completed
cancelled
```

### 8.4 Provider Tags

Provider `tags` must come from a fixed allowlist defined in `backend/constants.py` (`ALLOWED_PROVIDER_TAGS`). The frontend should use a multi-select control; free-text tags are not allowed. Use `other` when no specific category fits.

Allowed tag slugs:

```text
cleaning
childcare
elderly_care
electrician
plumbing
painter
locksmith
technician
moving
other
```

### 8.5 Location

- Customer profiles may store `latitude` and `longitude` for default addresses.
- Provider profiles store the current business address coordinates in `latitude` and `longitude`.
- Service areas use the `service_locations` hierarchy: `province` → `city` →
  `district`. Approved providers select one or more non-overlapping nodes in
  `provider_service_areas`; selecting a parent covers its descendants.
  `ProviderProfile.service_location_id` and `service_province` remain only as
  compatibility fields for migrated providers.
- `GET /locations` is public and read-only. Omit `parent_id` to list the 81
  provinces; pass a location ID to list its direct children. Responses use the
  standard success envelope and return ordered items with `id`, `code`, `name`,
  `level`, and `parent_id`.
- `GET /locations/{location_id}` returns one location node by its globally
  unique ID using the same response fields.
- Every booking must persist the service location: `service_address`, `service_latitude`, `service_longitude`.
- Coordinates are for distance calculation; display addresses use text fields.
- Distance filtering compares the search or booking location against provider coordinates.

Public provider search supports location parameters:

```text
GET /providers?latitude=41.0082&longitude=28.9784&max_distance_km=10&sort_by=distance_asc
```

Rules:

- `latitude` and `longitude` must be sent together.
- `max_distance_km` requires `latitude` and `longitude`.
- `sort_by=distance_asc` or `sort_by=distance_desc` requires `latitude` and `longitude`.
- `max_distance_km` is an optional customer search filter measured from the provider's current business coordinates; providers no longer store a self-declared service radius.
- When location params are present, each provider item includes `distance_km`.

AI recommendation also accepts location:

```json
{
  "message": "Find a plumber near me",
  "latitude": 41.0082,
  "longitude": 28.9784,
  "max_distance_km": 15
}
```

Rules:

- `POST /ai/chat`, `POST /ai/chat/sync`, and `POST /ai/recommend-providers` accept location fields.
- For customer AI chat, if `latitude` / `longitude` are omitted, the backend falls back to the customer profile default coordinates.
- Closer providers score higher in recommendations.
- `max_distance_km`, when supplied by the customer, filters against the provider's current business coordinates.

Home recommendations and keyword search:

```text
GET /customer/home/recommendations?service_province=Istanbul
GET /customer/home/recommendations?service_province=Istanbul&provider_tag=locksmith
GET /customer/providers/search?keyword=locksmith Istanbul&service_province=Istanbul
GET /providers?service_location_id=<province-or-city-or-district-id>
```

Rules:

- Without `provider_tag`, recommendations use the customer's last viewed tag from `customer_search_histories`; default is `cleaning` when no history exists.
- With `provider_tag`, only providers containing that tag are returned.
- After selecting a service category, ranking prioritizes tag match, then province and distance.
- Opening a provider detail updates `customer_search_histories.last_provider_tag`.
- Home search uses hard matching (no AI): tokenize input and match against `tags`, `service_province`, and `business_name`.
- A province or city location filter includes providers in descendant districts;
  a district filter is exact for providers with a location ID. During the
  transition, providers without a location ID are also retained when their
  normalized legacy province matches the selected location's province; these
  legacy rows cannot provide city/district precision until they are backfilled.
- Empty search results return an empty list; the frontend shows "No matching providers".

Scheduled time filtering on public search:

```text
GET /providers?scheduled_start_time=2026-09-01T10:00:00&scheduled_end_time=2026-09-01T12:00:00
```

Rules:

- `scheduled_start_time` and `scheduled_end_time` must be sent together.
- `scheduled_end_time` must be after `scheduled_start_time`.
- When scheduled times are provided, unavailable providers are excluded.
- Booking creation also checks provider availability.

Provider availability management:

```text
GET /provider/availability
PUT /provider/availability
```

Update example:

```json
{
  "availabilities": [
    {
      "weekday": 1,
      "start_time": "09:00",
      "end_time": "18:00",
      "is_available": true
    },
    {
      "weekday": 7,
      "is_available": false
    }
  ]
}
```

### 8.6 File Uploads (MVP)

- MVP uses local file storage; root directory is configured via `WORKSHOP_UPLOAD_DIR`.
- Default upload directory: `backend/uploads` (not committed to git).
- Public URLs start with `/uploads`.
- When migrating to MinIO/S3, replace only the upload utility layer; business endpoints stay the same.

## 9. AI Tools Layer

AI business capabilities are encapsulated in `backend/ai/tools.py`. LangChain wrappers live in `backend/ai/langchain_tools.py`. Routers and LangChain agents should call the tools layer instead of duplicating search, review summary, or chat-room logic.

`GET /ai/tools` returns the tool list for the current user's role; customers and providers see different write tools.

Current tool set:

```text
search_providers_tool
summarize_provider_reviews_tool
create_chat_room_tool
get_booking_status_tool
explain_booking_flow_tool
prepare_create_booking_action_tool
prepare_cancel_booking_action_tool
prepare_refund_request_action_tool
prepare_pay_booking_action_tool
prepare_reject_quote_action_tool
prepare_confirm_complete_action_tool
prepare_reject_complete_action_tool
prepare_quote_booking_action_tool
prepare_reject_booking_action_tool
prepare_complete_booking_action_tool
prepare_approve_refund_action_tool
prepare_reject_refund_action_tool
```

Responsibilities:

| Tool | Purpose |
| --- | --- |
| `search_providers_tool` | Search and rank providers by tag, location, budget, and schedule |
| `summarize_provider_reviews_tool` | Summarize reviews via Milvus; fall back to SQLite on failure |
| `create_chat_room_tool` | Create or reuse a chat room under customer permission rules |
| `get_booking_status_tool` | Return booking status, quote, payment, refund, and recent history for the current user |
| `explain_booking_flow_tool` | Explain platform booking flow and status rules |
| `prepare_*_action_tool` | Build a pending action draft; never write to the database directly |

LangChain wrapper pattern:

```python
StructuredTool.from_function(
    func=search_providers,
    name="search_providers",
    description="Search local providers by service tag, area, budget, location, and scheduled time.",
    args_schema=SearchProvidersToolInput,
)
```

- `func` — Python function that executes the tool.
- `name` — Name the model uses when calling the tool.
- `description` — When the model should choose this tool.
- `args_schema` — Pydantic schema for tool arguments.

Debug endpoints:

```text
GET  /ai/tools
POST /ai/tools/run
POST /ai/tools/agent-preview
GET  /ai/tool-call-logs
POST /ai/actions/confirm
```

### 9.1 Tool Call Logs

Table: `ai_tool_call_logs`. Each LangChain tool execution writes one row:

- `user_id` — Who triggered the call.
- `tool_name` — Tool selected by the model.
- `tool_args_json` — Arguments passed to the tool.
- `status` — `success` or `failed`.
- `result_json` — Result snapshot on success (truncated if too long).
- `error_message`, `error_type`, `status_code` — Failure details.
- `duration_ms` — Execution time.
- `request_message` — Original user message.
- `context_json` — Context passed to the model, including `actionable_context`.

Query:

```text
GET /ai/tool-call-logs
GET /ai/tool-call-logs?status=failed
GET /ai/tool-call-logs?tool_name=prepare_quote_booking_action
```

Permissions:

- Customers and providers see only their own logs.
- Admins see all logs.

Manual tool execution (`POST /ai/tools/run`):

```json
{
  "tool_name": "search_providers",
  "tool_args": {
    "query": "Kitchen pipe leak",
    "service_tags": ["plumbing"],
    "max_distance_km": 10
  }
}
```

### 9.2 `/ai/chat/sync` Response Types

The endpoint uses `ApiResponse[AIChatResponseData]`. When the model invokes a tool, `data.type` is one of:

```text
casual_chat
provider_search
review_summary
chat_room
booking_status
booking_flow
booking_draft_missing_info
booking_draft_cancelled
ai_action_confirmation
tool_error
```

Example confirmation response (`data` only):

```json
{
  "type": "ai_action_confirmation",
  "answer": "I have prepared: Submit quote. Please review and confirm.",
  "confirmation_card": { "action_id": 1, "action_type": "quote_booking", "confirm_endpoint": "/ai/actions/confirm" },
  "tool_calls": []
}
```

Notes:

- The outer envelope is always `{ success, message, data }`.
- The frontend branches on `data.type` for text, provider lists, review summaries, confirmation cards, or errors.
- `tool_results` is mainly for debugging.
- `answer` is a stable backend-generated prompt; the model's raw reply is kept in internal metadata.

### 9.3 AI Context Enrichment

`/ai/chat/sync` flow:

```text
User input
-> build_langchain_tool_context
-> Load recent actionable data for the current user into actionable_context
-> Read pending_clarification from the latest assistant tool_error
-> LangChain tool calling may infer booking_id / refund_request_id from context
-> If user replies to pending_clarification with an index, merge args and re-run the tool
-> Prefer LangChain tool calling; fall back to classify_user_intent when no tool is chosen
```

`actionable_context` includes role-specific booking/refund candidates (max 5 per category). `pending_clarification` on the latest `tool_error` lets users reply with `1` / `first` / `second` to disambiguate missing `booking_id` or `refund_request_id`.

### 9.4 Multi-Turn Booking Draft Collection

```text
User: I need a plumber for a kitchen leak
-> AI calls prepare_booking_draft_action
-> Returns booking_draft_missing_info with partial draft

User: Address is Sultanahmet, Istanbul; tomorrow 2pm to 4pm
-> AI calls prepare_booking_draft_action again, merges with prior draft
-> If provider or coordinates are still missing, returns booking_draft_missing_info
-> When complete, returns ai_action_confirmation for create_booking
```

Provider selection from recommendations:

```text
User: Find a plumber near me
-> Returns provider_search and caches the recommendation list

User: Book the first one
-> If booking_draft lacks provider_profile_id, resolve "first" / "pick 1" / "the second" from the list
-> Merge provider_profile_id into booking_draft
-> Continue checking address, location, and schedule
```

Supported selection phrases:

- `1`, `first`, `pick 1`, `the second`
- `highest rated`, `best reviews`, `best reputation`
- `cheapest`, `lowest price`
- When only one candidate: `this one`, `that one`

Draft cancel / reset:

```text
User: Never mind / start over / cancel draft
-> If latest AI state is booking_draft_missing_info
-> Returns booking_draft_cancelled; prior draft is not carried forward
```

Field overrides via `/ai/chat/sync`:

| Request field | Draft field |
| --- | --- |
| `service_address` | `service_address` |
| `latitude` | `service_latitude` |
| `longitude` | `service_longitude` |
| `scheduled_start_time` | `scheduled_start_time` |
| `scheduled_end_time` | `scheduled_end_time` |

Location/time override example (`POST /ai/chat/sync`):

```json
{
  "message": "Here is my service location and time",
  "service_address": "Sultanahmet, Istanbul",
  "latitude": 41.0082,
  "longitude": 28.9784,
  "scheduled_start_time": "2026-09-03T14:00:00",
  "scheduled_end_time": "2026-09-03T16:00:00"
}
```

`booking_draft_missing_info` returns `draft_status`, `provided_fields`, `missing_fields` (with `question` prompts), `provider_choices`, and `next_question`. Drafts live in assistant metadata until complete.

Rules:

- Booking creation via AI starts with `prepare_booking_draft_action`, which accepts incomplete input.
- Drafts are stored in assistant message metadata, not in the `bookings` table.
- Each turn merges new fields into the prior draft.
- A full draft creates `AIPendingAction(create_booking)`; the user must still confirm.
- AI booking creation does not support attachments; use `POST /bookings` with `multipart/form-data` for media.

### 9.5 Tool Errors

When a tool fails (missing args, forbidden, invalid status, not found), `/ai/chat/sync` returns `tool_error` instead of silently falling back:

```json
{
  "type": "tool_error",
  "answer": "This action cannot be performed now: Only pending bookings can receive a quote",
  "tool_error": {
    "tool_name": "prepare_quote_booking_action",
    "tool_args": {
      "booking_id": 12,
      "quote_amount": 120
    },
    "error": "Only pending bookings can receive a quote",
    "error_code": "BOOKING_STATUS_NOT_ALLOWED",
    "error_type": "http_exception",
    "status_code": 400,
    "error_details": "Only pending bookings can receive a quote"
  },
  "tool_calls": [],
  "tool_results": []
}
```

Common `error_code` values:

| Code | Meaning |
| --- | --- |
| `VALIDATION_ERROR` | Missing or invalid tool arguments |
| `FORBIDDEN` | Current account lacks permission |
| `BOOKING_NOT_FOUND` | Booking missing or inaccessible |
| `PROVIDER_NOT_FOUND` | Provider missing |
| `REFUND_REQUEST_NOT_FOUND` | Refund request missing |
| `PROVIDER_NOT_APPROVED` | Provider not verified; cannot book |
| `MISSING_LOCATION` | Latitude/longitude required |
| `PROVIDER_NOT_AVAILABLE` | Provider unavailable at scheduled time |
| `BOOKING_STATUS_NOT_ALLOWED` | Status does not allow this action |
| `REASON_REQUIRED` | A reason field is mandatory |

`agent-preview` is a debug endpoint for LangChain tool calling. Production chat at `/ai/chat/sync` uses the same tool-calling path first.

## 10. Pending Action Confirmation

Write operations initiated through AI use a two-step confirm flow:

```text
User requests create/cancel/refund/pay/reject quote/confirm complete/reject completion
  or provider requests quote/reject/complete/approve refund/reject refund
-> Model calls prepare_* tool
-> Backend validates args and permissions
-> Backend saves ai_pending_actions record
-> Returns pending_action with id, status, expires_at, payload, and preview
-> User confirms
-> Frontend sends only pending_action.id to /ai/actions/confirm
-> Backend re-validates and executes the write
```

Confirm request:

```json
{
  "action_id": 1
}
```

Important: `prepare_*` tools only create `ai_pending_actions` drafts. Actual writes happen only at `/ai/actions/confirm`, which reads stored `payload_json` — not any payload from the frontend. `pending_action.preview` and `confirmation_card` are display-only.

When `/ai/chat/sync` returns `type = "ai_action_confirmation"`, the response includes `confirmation_card`:

```json
{
  "type": "ai_action_confirmation",
  "answer": "I have prepared: Confirm payment.\nPlease review the details below. The action runs only after you confirm.",
  "confirmation_card": {
    "ui_type": "confirmation_card",
    "action_id": 1,
    "action_type": "pay_booking",
    "title": "Confirm payment",
    "description": "After confirmation, booking 1 will be paid at 120.0 TRY and move to the in-progress stage.",
    "status": "pending",
    "expires_at": "2026-09-02T10:30:00+00:00",
    "fields": [
      {"label": "Booking ID", "value": 1},
      {"label": "Provider", "value": "Istanbul Plumbing"},
      {"label": "Quote amount", "value": 120.0}
    ],
    "confirm_label": "Confirm payment",
    "cancel_label": "Cancel",
    "confirm_endpoint": "/ai/actions/confirm",
    "confirm_request": {
      "action_id": 1
    },
    "cancel_endpoint": "/ai/actions/1/cancel"
  }
}
```

Customer write actions behind confirmation:

```text
create_booking
cancel_booking
request_refund
pay_booking
reject_quote
confirm_complete
reject_complete
```

Provider write actions behind confirmation:

```text
quote_booking
reject_booking
complete_booking
approve_refund
reject_refund
```

Manage pending actions:

```text
GET /ai/actions
GET /ai/actions/{action_id}
PUT /ai/actions/{action_id}/cancel
POST /ai/actions/confirm
```

Status transitions:

```text
pending -> executed
pending -> cancelled
pending -> expired
```

- `confirm` only runs `pending` actions that have not passed `expires_at`.
- `cancel` only cancels `pending` actions that have not passed `expires_at`.
- Listing or fetching auto-marks overdue `pending` actions as `expired`.

## 11. Customer and Provider Booking Action Reuse

Customer booking write logic is centralized in:

```text
backend/utils/customer_booking_actions.py
```

Both regular HTTP endpoints and AI confirm must call these functions so booking rules live in one place. Currently reused endpoints:

```text
POST /bookings
POST /bookings/{booking_id}/refund-requests
PUT  /customer/bookings/{booking_id}/reject-quote
PUT  /customer/bookings/{booking_id}/cancel
PUT  /customer/bookings/{booking_id}/confirm-complete
PUT  /customer/bookings/{booking_id}/reject-complete
```

Provider booking write logic is centralized in:

```text
backend/utils/provider_booking_actions.py
```

Currently reused endpoints:

```text
PUT /provider/refund-requests/{refund_request_id}/approve
PUT /provider/refund-requests/{refund_request_id}/reject
PUT /provider/bookings/{booking_id}/quote
PUT /provider/bookings/{booking_id}/reject
PUT /provider/bookings/{booking_id}/complete
```

When adding a new booking state transition, implement it in the appropriate utils module first, then wire both the HTTP router and AI confirm handler to that function.

## 12. WebSocket Basics

Connect at:

```text
ws://127.0.0.1:8000/ws/chats/{chat_room_id}?token=<access_token>
```

Implementation: `backend/routers/websocket.py`, connection manager: `backend/utils/websocket_manager.py`.

- Pass `access_token` as a query parameter (not a header).
- HTTP endpoints persist chat history; WebSocket delivers live events.
- Only chat room members may connect.
- On policy violation the server sends `{ "type": "error", "message": "..." }` and closes with code 1008.

Client → server message types:

| type | Purpose |
| --- | --- |
| `chat_message` | Send text and/or `attachment_ids` |
| `mark_read` | Mark messages in the room as read |
| `typing_start` | User started typing |
| `typing_stop` | User stopped typing |

Send chat message:

```json
{
  "type": "chat_message",
  "message": "Here is a video from the site",
  "attachment_ids": [1, 2]
}
```

Other client events: `{ "type": "mark_read" }`, `{ "type": "typing_start" }`, `{ "type": "typing_stop" }`.

Server → client events include:

- New `chat_message` payloads (with attachment metadata when applicable).
- `chat_read_summary` — unread count update for the current user.
- `chat_messages_read` — read receipt to the other party.
- `typing_start` / `typing_stop` — typing indicators.
- `user_online` / `user_offline` — presence in the room (not persisted; backed by Redis `online:user:{user_id}`).

Read events include `chat_read_summary` (for the reader) and `chat_messages_read` (receipt to the peer), each with `chat_room_id`, `message_ids`, and `read_at`.

## 13. Notifications

In-app notifications are created via `create_notification()` in `backend/utils/notification.py`. Delivery may be queued through `backend/utils/notification_queue.py` and Celery tasks in `backend/tasks/notification_tasks.py`.

Endpoints (`backend/routers/shared.py`):

```text
GET /notifications
GET /notifications/summary
PUT /notifications/{notification_id}/read
PUT /notifications/read-all
```

Rules:

- Create a notification when a state change affects the user (new booking, quote, payment, completion, refund, complaint update, etc.).
- `GET /notifications` supports `unread_only`, `page`, and `page_size`.
- `GET /notifications/summary` returns aggregate unread counts for the notification bell.
- Notifications may reference related resources via `related_type` and `related_id`.
- WebSocket can push real-time notification events where implemented; HTTP polling via `/notifications` remains the source of truth for history.

## 14. Chat Attachments

Chat attachments use a two-step flow: upload first, then reference in a message.

Endpoints:

```text
POST   /chats/{chat_room_id}/attachments
POST   /chats/{chat_room_id}/messages
DELETE /chats/{chat_room_id}/attachments/{attachment_id}
```

Rules:

- Only chat room members may upload, send, and view attachments.
- `POST /chats/{chat_room_id}/attachments` uses `multipart/form-data` and returns `attachment_id`; the file is not sent until referenced.
- `POST /chats/{chat_room_id}/messages` accepts JSON with `message` and `attachment_ids`.
- Send text only, attachments only, or both.
- Only reference attachments you uploaded, in the same room, that have not been sent yet.
- WebSocket `chat_message` uses the same `attachment_ids` pattern after HTTP upload.
- Unsent attachments may be deleted; sent attachments cannot be deleted individually.
- Supported types (MVP): `jpg`, `jpeg`, `png`, `pdf`, `mp4`, `mov`.
- Files are stored under `/uploads/chats/{chat_room_id}/...`.

Upload field: `file: pipe-video.mp4`. Send via HTTP or WebSocket with `message` and `attachment_ids: [1, 2]`.

Attachment messages set `message_type=attachment` with `metadata.attachments` (id, `file_url`, `content_type`, `size`). Quote/payment/refund lifecycle messages use `message_type=booking_status` with structured `metadata` (status transition, amounts, currency).

```text
text
attachment
booking_created
booking_status
```

Rules:

- User text → `message_type=text`.
- User message with chat attachments → `message_type=attachment`.
- Auto message on booking creation → `message_type=booking_created`.
- Booking lifecycle system messages → `message_type=booking_status`.
- Link business entities with `related_type` and `related_id` (e.g. `related_type=booking`, `related_id=<booking.id>`).
- Prefer `metadata` over parsing `message` text for rendering cards (quotes, payments, refunds).
- Quote, reject quote, pay, cancel, complete, refund, and admin status changes auto-create `booking_status` messages.

### 14.1 Chat Message Types

```text
GET /chats/{chat_room_id}/messages?message_type=attachment
GET /chats/{chat_room_id}/messages?message_type=booking_status
GET /chats/{chat_room_id}/messages?message_type=booking_created
GET /chats/{chat_room_id}/messages?message_type=text
```

### 14.2 Booking Attachments

```text
POST   /bookings/{booking_id}/attachments
GET    /bookings/{booking_id}/attachments
DELETE /bookings/{booking_id}/attachments/{attachment_id}
```

Rules:

- Primary flow: upload initial attachments in `POST /bookings` (`multipart/form-data`).
- Supplementary upload endpoint remains for adding files later.
- Only the booking customer may upload.
- Customer, provider, and admin may list attachments.
- Only the uploader may delete.
- Supported types: `jpg`, `jpeg`, `png`, `pdf`.
- Stored under `/uploads/bookings/{booking_id}/...`.
- `GET /bookings/{booking_id}` includes `attachments`.

Create booking with attachments (`POST /bookings`):

```text
provider_profile_id: 2
service_description: Kitchen pipe leak; need a plumber on site
service_address: Sultanahmet, Istanbul
service_latitude: 41.0082
service_longitude: 28.9784
scheduled_start_time: 2026-09-01T10:00:00
scheduled_end_time: 2026-09-01T12:00:00
chat_room_id: optional
attachments: leaking-pipe.png
attachments: invoice.pdf
```

If the customer has not opened a chat, the system creates or reuses a chat room with the provider, posts a `booking_created` message, and notifies the provider.

### 14.3 Provider Certificate and Portfolio Uploads

Certificate upload:

```text
POST /provider/certificates/upload
```

- Provider only. Types: `jpg`, `jpeg`, `png`, `pdf`. Max size: `WORKSHOP_MAX_UPLOAD_SIZE_MB` (default 5 MB).
- Returns `file_url`; submit it as `certificate_url` when creating or updating the provider profile.

Portfolio:

```text
POST   /provider/portfolio
GET    /provider/portfolio
DELETE /provider/portfolio/{portfolio_id}
GET    /providers/{provider_id}/portfolio
```

- `POST /provider/portfolio` uses `multipart/form-data`; images only (`jpg`, `jpeg`, `png`).
- Public portfolio is visible only for approved providers.
- Deleting a portfolio item removes the local image file.

Create portfolio fields:

```text
title: Before and after pipe repair
description: Photos after kitchen pipe repair
image: portfolio.png
```

## 15. New Endpoint Checklist

Before merging a new endpoint, verify:

- [ ] Route is in the correct router file.
- [ ] Correct permission dependency (`require_customer`, etc.).
- [ ] Request body schema exists in `backend/schemas.py`.
- [ ] Response uses `success_response()` or `build_paginated_response()`.
- [ ] Errors raised via `HTTPException` (unified handler applies).
- [ ] Pagination added for list endpoints.
- [ ] Status history written when state changes matter.
- [ ] Notification created when users should be informed.
- [ ] Celery task triggered if work should run asynchronously.
- [ ] Milvus/Redis cache impact considered.
- [ ] Swagger description is clear enough for frontend integration.
- [ ] Booking writes reuse `customer_booking_actions.py` or `provider_booking_actions.py` where applicable.
- [ ] AI write paths go through `prepare_*` + `/ai/actions/confirm` when appropriate.

## 16. MVP Conventions

The project is in MVP backend phase. The goal is **stable, consistent, frontend-friendly APIs** — not enterprise completeness on day one.

Short-term priorities:

1. Keep route placement and permissions obvious.
2. Keep response envelopes uniform (`success`, `message`, `data`).
3. Keep core booking state transitions explicit and documented.
4. Ship complex capabilities in working form: AI, Celery, WebSocket, Milvus, Redis.
5. Add finer `response_model` declarations and examples before major frontend milestones.

Pragmatic allowances:

- Some list endpoints still return `ApiResponse[Any]` in Swagger.
- Payment is implemented through the iyzico Sandbox Checkout Form. Keep the local
  payment record and iyzico callback/retrieve result as the source of truth for the
  payment state; do not reintroduce a mock payment gateway in application routes.
- Local file storage is fine until object storage is wired.
- `classify_user_intent` remains as a fallback behind LangChain tool calling.
- Natural-language time parsing is deferred; ISO timestamps are required for schedules.

When in doubt, match existing patterns in `backend/routers/`, `backend/schemas.py`, and `backend/utils/` rather than introducing a parallel style.
