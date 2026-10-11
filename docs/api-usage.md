# Workshop AI Backend API Usage

> Derived from FastAPI OpenAPI with notes for frontend developers. Use with Swagger.

## Conventions

- Base URL (local): `http://127.0.0.1:8000`.
- Most HTTP responses: `{ success, message, data }`.
- Errors: `{ success: false, message, error: { code, detail, errors } }`.
- Except Auth/Public/health, send `Authorization: Bearer <access_token>`.
- `access_token` for API calls; `refresh_token` to refresh.
- `page` starts at 1; pagination in `data.items`, `data.total`, `data.total_pages`.
- Uploads use `multipart/form-data`.
- e.g. `POST /bookings` shows as `Body_create_booking_bookings_post` in Swagger (auto-generated form body for booking fields and attachments).
- WebSocket URLs are in the WebSocket section below.

## API overview

- **Auth**: login, social login, token refresh, current user, mock verify, change password/email (11 endpoints).
- **Public**: providers, reviews, portfolios without login (6 endpoints).
- **Customer**: profile, favorites, chat, bookings, payments, refunds, complaints, reviews (26 endpoints).
- **Payment**: iyzico Sandbox Checkout Form callback (1 public provider callback).
- **Provider**: profile, availability, portfolio, quotes, completion, refunds (19 endpoints).
- **Admin**: users, verification, bookings, payments, refunds, chat, complaints, reviews (20 endpoints).
- **Shared**: chat, notifications, booking details, attachments, status history (14 endpoints).
- **AI**: chat, tools, pending actions, async tasks, health checks (24 endpoints).
- **Other**: health endpoints (2).

## Auth

Login, social login, token refresh, and current user.

Auth: some public; /me, /logout, /refresh-token need tokens.

| Method | Path | Purpose | Params | Body | Success |
|---|---|---|---|---|---|
| `POST` | `/login` | Login; returns tokens and user. | - | `application/x-www-form-urlencoded` -> `Body_login_login_post` | `ApiResponse_TokenResponse_` |
| `POST` | `/logout` | Revoke refresh token. | - | `application/json` -> `RefreshTokenRequest` | `ApiResponse_NoneType_` |
| `GET` | `/me` | Current user. | - | - | `ApiResponse_UserResponse_` |
| `POST` | `/refresh-token` | Refresh access token. | - | `application/json` -> `RefreshTokenRequest` | `ApiResponse_TokenResponse_` |
| `POST` | `/register` | Register. | - | `application/json` -> `UserRegister` | `ApiResponse_RegisterResponseData_` |
| `POST` | `/social-login` | Google/Apple login; verifies id_token and returns platform tokens. | - | `application/json` -> `SocialLoginRequest` | `ApiResponse_SocialLoginResponseData_` |
| `POST` | `/auth/verify-email` | Demo email verify. Body any 6 digits. | - | `application/json` -> `MockVerificationRequest` | `ApiResponse_UserResponse_` |
| `POST` | `/auth/verify-phone` | Demo phone verify. Body any 6 digits. Needs a saved phone. | - | `application/json` -> `MockVerificationRequest` | `ApiResponse_UserResponse_` |
| `POST` | `/auth/change-password` | Change password with the current password. | - | `application/json` -> `ChangePasswordRequest` | `ApiResponse_UserResponse_` |
| `POST` | `/auth/change-email` | Change login email with any 6-digit demo code. | - | `application/json` -> `ChangeEmailRequest` | `ApiResponse_UserResponse_` |
| `POST` | `/token` | OAuth2 password flow for Swagger Authorize. | - | `application/x-www-form-urlencoded` -> `Body_swagger_login_token_post` | `OAuthTokenResponse` |

## Public

Public providers, reviews, portfolios, and Places lookup.

Auth: none.

| Method | Path | Purpose | Params | Body | Success |
|---|---|---|---|---|---|
| `GET` | `/locations` | List direct service-area children; omit `parent_id` for provinces. | `parent_id`(query, optional, integer / null) | - | `ApiResponse_ServiceLocationListResponse_` |
| `GET` | `/locations/{location_id}` | Get one service-area node by ID. | `location_id`(path, required, integer) | - | `ApiResponse_ServiceLocationResponse_` |
| `GET` | `/providers` | Search approved providers. | `service_province`(query, optional, string / null)<br>`service_location_id`(query, optional, integer / null)<br>`min_price`(query, optional, integer / null)<br>`max_price`(query, optional, integer / null)<br>`latitude`(query, optional, number / null)<br>`longitude`(query, optional, number / null)<br>`max_distance_km`(query, optional, number / null)<br>`scheduled_start_time`(query, optional, string / null)<br>`scheduled_end_time`(query, optional, string / null)<br>`tags`(query, optional, array[string] / null)<br>`sort_by`(query, optional, string / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_PaginatedData_ProviderProfileWithRatingResponse__` |
| `GET` | `/providers/{provider_id}` | Public provider detail. | `provider_id`(path, required, integer) | - | `ApiResponse_ProviderProfileWithRatingResponse_` |
| `GET` | `/providers/{provider_id}/portfolio` | Public portfolio. | `provider_id`(path, required, integer)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_PaginatedData_ProviderPortfolioResponse__` |
| `GET` | `/providers/{provider_id}/rating-summary` | Rating summary. | `provider_id`(path, required, integer) | - | `ApiResponse_RatingSummaryResponse_` |
| `GET` | `/providers/{provider_id}/reviews` | Public reviews. | `provider_id`(path, required, integer)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_PaginatedData_ReviewDetailResponse__` |
| `GET` | `/reviews/{review_id}` | Public review detail. | `review_id`(path, required, integer) | - | `ApiResponse_ReviewDetailResponse_` |
| `GET` | `/places/autocomplete` | Search place suggestions through the server-side Google Places proxy. | `q`(query, required, string) | - | `ApiResponse_PlacesAutocompleteResponse_` |
| `GET` | `/places/details` | Resolve a selected place ID to its address and coordinates. | `place_id`(query, required, string) | - | `ApiResponse_PlaceDetailsResponse_` |

Places success payloads use `place_id` and `description` for autocomplete suggestions. `/places/details` returns `place_id`, `formatted_address`, `latitude`, and `longitude`. The Google Places key is server-only in `WORKSHOP_GOOGLE_MAPS_API_KEY`; it must not be placed in Expo environment variables. These endpoints provide street addresses. Service-area selection uses `/locations`: the root response lists 81 provinces, and passing a province/city `parent_id` lists its direct children. Profile writes persist the final district as `service_location_id`; `service_province` remains a compatibility projection.

## Customer

Customer profile, favorites, chat, bookings, payments, refunds, complaints, reviews.

Auth: customer.

| Method | Path | Purpose | Params | Body | Success |
|---|---|---|---|---|---|
| `POST` | `/bookings` | Create booking with form fields and attachments. | - | `multipart/form-data` -> `Body_create_booking_bookings_post` | `ApiResponse_BookingCreateResponseData_` |
| `POST` | `/bookings/{booking_id}/complaints` | Create Complaint | `booking_id`(path, required, integer) | `application/json` -> `ComplaintCreate` | `ApiResponse_Any_` |
| `PUT` | `/customer/bookings/{booking_id}/accept-quote` | Accept Booking Quote | `booking_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/customer/bookings/{booking_id}/accept-final-quote` | Accept final service quote before payment | `booking_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/customer/bookings/{booking_id}/reject-final-quote` | Decline final quote and request revision | `booking_id`(path, required, integer) | `BookingNoteUpdate` | `ApiResponse_Any_` |
| `PUT` | `/customer/bookings/{booking_id}/close-final-quote` | Close after arrival without an automatic refund | `booking_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `POST` | `/bookings/{booking_id}/refund-requests` | Create Refund Request | `booking_id`(path, required, integer) | `application/json` -> `RefundRequestCreate` | `ApiResponse_Any_` |
| `POST` | `/bookings/{booking_id}/review` | Create Review | `booking_id`(path, required, integer) | `application/json` -> `ReviewCreate` | `ApiResponse_Any_` |
| `GET` | `/customer/bookings` | Get Customer Bookings | `status`(query, optional, BookingStatus / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/customer/bookings/{booking_id}/cancel` | Cancel Booking | `booking_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/customer/bookings/{booking_id}/confirm-complete` | Confirm Booking Complete | `booking_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/customer/bookings/{booking_id}/reject-complete` | Reject Booking Complete | `booking_id`(path, required, integer) | `application/json` -> `BookingNoteUpdate` | `ApiResponse_Any_` |
| `PUT` | `/customer/bookings/{booking_id}/reject-quote` | Reject Booking Quote | `booking_id`(path, required, integer) | `application/json` -> `BookingNoteUpdate` | `ApiResponse_Any_` |
| `GET` | `/customer/chats` | Get Customer Chats | `page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `POST` | `/customer/chats/{provider_profile_id}` | Open Chat With Provider | `provider_profile_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `GET` | `/customer/complaints` | Get Customer Complaints | `status`(query, optional, ComplaintStatus / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/customer/favorites` | Get Favorite Providers | `page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `POST` | `/customer/favorites/{provider_profile_id}` | Add Favorite Provider | `provider_profile_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `DELETE` | `/customer/favorites/{provider_profile_id}` | Remove Favorite Provider | `provider_profile_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `GET` | `/customer/payments` | Get Customer Payments | `status`(query, optional, PaymentStatus / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/customer/bookings/{booking_id}/pay` | Start Booking Payment | `booking_id`(path, required, integer) | `application/json` -> `PaymentCreate` | `ApiResponse_Any_` |
| `GET` | `/customer/profile` | Get Customer Profile | - | - | `ApiResponse_Any_` |
| `POST` | `/customer/profile` | Create Customer Profile | - | `application/json` -> `CustomerProfileCreate` | `ApiResponse_Any_` |
| `PUT` | `/customer/profile` | Update Customer Profile | - | `application/json` -> `CustomerProfileCreate` | `ApiResponse_Any_` |
| `GET` | `/customer/refund-requests` | Get Customer Refund Requests | `status`(query, optional, RefundRequestStatus / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/customer/reviews` | Get Customer Reviews | `is_visible`(query, optional, boolean / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/refund-requests/{refund_request_id}/cancel` | Cancel Refund Request | `refund_request_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/reviews/{review_id}` | Update Review | `review_id`(path, required, integer) | `application/json` -> `ReviewUpdate` | `ApiResponse_Any_` |
| `DELETE` | `/reviews/{review_id}` | Delete Review | `review_id`(path, required, integer) | - | `ApiResponse_Any_` |

## Payment

The payment flow uses two direct iyzico Sandbox Hosted Checkouts: `visit_fee` before
arrival and `service_fee` after the customer accepts the final quote. The same
`PUT /customer/bookings/{booking_id}/pay` endpoint starts either stage and returns
`payment_page_url`. iyzico posts a `token` to the callback; the backend retrieves and
verifies the result server-to-server before recording `paid`. This is not PreAuth:
completion confirmation does not charge the customer again.

| Method | Path | Purpose | Params | Body | Success |
|---|---|---|---|---|---|
| `POST` | `/payments/iyzico/callback` | Receive Checkout Form token and finalize payment | - | `application/x-www-form-urlencoded` -> `token` | `ApiResponse_Any_` |

Payment start response fields:

- `data.payment_page_url`: iyzico Sandbox checkout page to open or redirect to.
- `data.token`: Checkout Form token returned by iyzico.
- `data.payment.status`: initially `checkout_created`; after verification it becomes `paid`, `failed`, or remains `processing` while unresolved.
- `data.booking.status`: `awaiting_visit_payment` → `visit_paid`, or `awaiting_service_payment` → `service_paid`, after the corresponding successful callback.
- Send `Idempotency-Key` per booking/payment stage; continuing a valid checkout reuses its link.

Cancellation does not refund paid fees automatically. After arrival, a customer can
request a full/partial refund; Provider approval or Admin appeal approval calls iyzico
Refund. Failed or cancelled requests can be retried/replaced, but only one successful
refund is allowed per booking. Refunds allocate service-fee money before visit-fee money.

## Provider

Provider profile, availability, portfolio, quotes, completion, refunds.

Auth: provider.

| Method | Path | Purpose | Params | Body | Success |
|---|---|---|---|---|---|
| `GET` | `/provider/availability` | Get Provider Availability | - | - | `ApiResponse_Any_` |
| `PUT` | `/provider/availability` | Update Provider Availability | - | `application/json` -> `ProviderAvailabilityUpdate` | `ApiResponse_Any_` |
| `GET` | `/provider/bookings` | Get Provider Bookings | `status`(query, optional, BookingStatus / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/provider/bookings/{booking_id}/complete` | Complete Booking | `booking_id`(path, required, integer) | `multipart/form-data` -> proof files, `final_quote_amount`, `final_quote_message` | `ApiResponse_Any_` |
| `PUT` | `/provider/bookings/{booking_id}/quote` | Quote Booking | `booking_id`(path, required, integer) | JSON, or `multipart/form-data` with quote fields and optional `quote_files` | `ApiResponse_Any_` |
| `PUT` | `/provider/bookings/{booking_id}/start-visit` | Confirm arrival with evidence | `booking_id`(path, required, integer) | `multipart/form-data` -> `proof_files` | `ApiResponse_Any_` |
| `PUT` | `/provider/bookings/{booking_id}/final-quote` | Submit or revise final service quote | `booking_id`(path, required, integer) | JSON, or `multipart/form-data` with quote fields and optional `quote_files` | `ApiResponse_Any_` |
| `PUT` | `/provider/bookings/{booking_id}/reject` | Reject Booking | `booking_id`(path, required, integer) | `application/json` -> `BookingNoteUpdate` | `ApiResponse_Any_` |
| `GET` | `/provider/verification-status` | Read identity and qualification state | - | - | `ApiResponse_Any_` |
| `POST` | `/provider/identity-verification` | Submit real-name verification | - | multipart date, document type, 1-5 files | `ApiResponse_Any_` |
| `GET` | `/provider/identity-verification` | Read latest identity application | - | - | `ApiResponse_Any_` |
| `POST` | `/provider/qualification-files/upload` | Upload private qualification documents | - | multipart 1-5 files | `ApiResponse_Any_` |
| `POST` | `/provider/qualification-verification` | Submit qualification snapshot independently of identity approval | - | `QualificationVerificationSubmit` | `ApiResponse_Any_` |
| `GET` | `/provider/qualification-verification` | Read latest qualification application | - | - | `ApiResponse_Any_` |
| `GET` | `/provider/approved-services` | Read approved and enabled services | - | - | `ApiResponse_Any_` |
| `PATCH` | `/provider/operating-settings` | Update approved provider's current operating data | - | `ProviderOperatingSettingsV2Patch` | `ApiResponse_Any_` |
| `PUT` | `/provider/service-areas` | Replace province/city/district service areas | - | `ProviderServiceAreasUpdate` | `ApiResponse_Any_` |
| `POST` | `/provider/certificates/upload` | Legacy-provider certificate upload; new providers use qualification upload | - | `multipart/form-data` -> `Body_upload_provider_certificate_provider_certificates_upload_post` | `ApiResponse_CertificateUploadResponse_` |
| `GET` | `/provider/chats` | Get Provider Chats | `page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/provider/dashboard` | Provider Dashboard | - | - | `ApiResponse_Any_` |
| `GET` | `/provider/payments` | Get Provider Payments | `status`(query, optional, PaymentStatus / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/provider/submerchant` | Read Provider Payout Account | - | - | `ApiResponse_Any_` |
| `POST` | `/provider/submerchant` | Create and synchronize iyzico Submerchant | - | `application/json` -> `ProviderSubmerchantUpsert` | `ApiResponse_Any_` |
| `PUT` | `/provider/submerchant` | Update and synchronize iyzico Submerchant | - | `application/json` -> `ProviderSubmerchantUpsert` | `ApiResponse_Any_` |
| `GET` | `/provider/portfolio` | Get Provider Portfolio | `page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_PaginatedData_ProviderPortfolioResponse__` |
| `POST` | `/provider/portfolio` | Create Provider Portfolio | - | `multipart/form-data` -> `Body_create_provider_portfolio_provider_portfolio_post` | `ApiResponse_ProviderPortfolioResponse_` |
| `DELETE` | `/provider/portfolio/{portfolio_id}` | Delete Provider Portfolio | `portfolio_id`(path, required, integer) | - | `ApiResponse_NoneType_` |
| `GET` | `/provider/profile` | Get Provider Profile | - | - | `ApiResponse_Any_` |
| `POST` | `/provider/profile` | Legacy compatibility only; new profiles are created by qualification approval | - | `application/json` -> `ProviderProfileCreate` | `ApiResponse_Any_` |
| `PUT` | `/provider/profile` | Legacy compatibility only; new providers use operating settings | - | `application/json` -> `ProviderProfileCreate` | `ApiResponse_Any_` |
| `GET` | `/provider/refund-requests` | Get Provider Refund Requests | `status`(query, optional, RefundRequestStatus / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/provider/refund-requests/{refund_request_id}/approve` | Approve Refund Request | `refund_request_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/provider/refund-requests/{refund_request_id}/reject` | Reject Refund Request | `refund_request_id`(path, required, integer) | `application/json` -> `ProviderRefundRejectCreate` | `ApiResponse_Any_` |

## Admin

Admin: users, verification, bookings, payments, refunds, chat, complaints, reviews.

Auth: admin.

| Method | Path | Purpose | Params | Body | Success |
|---|---|---|---|---|---|
| `GET` | `/admin/bookings` | Get All Bookings | `status`(query, optional, BookingStatus / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/admin/bookings/{booking_id}/status` | Admin Update Booking Status | `booking_id`(path, required, integer) | `application/json` -> `AdminBookingStatusUpdate` | `ApiResponse_Any_` |
| `GET` | `/admin/chats` | Get All Chats | `page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/admin/chats/{chat_room_id}/messages` | Get Admin Chat Messages | `chat_room_id`(path, required, integer)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/admin/complaints` | Get All Complaints | `status`(query, optional, ComplaintStatus / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/admin/complaints/{complaint_id}` | Get Complaint By Id | `complaint_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `GET` | `/admin/complaints/{complaint_id}/history` | Get Complaint Status History | `complaint_id`(path, required, integer)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/admin/complaints/{complaint_id}/status` | Update Complaint Status | `complaint_id`(path, required, integer) | `application/json` -> `AdminComplaintStatusUpdate` | `ApiResponse_Any_` |
| `GET` | `/admin/dashboard` | Get Admin Dashboard | - | - | `ApiResponse_Any_` |
| `GET` | `/admin/payments` | Get All Payments | `status`(query, optional, PaymentStatus / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/admin/submerchants` | Get masked provider payout accounts | `page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `POST` | `/admin/payments/{payment_id}/settlement/retry` | Queue a failed Marketplace approval retry | `payment_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `GET` | `/admin/identity-verifications` | List identity applications | `status`(query, optional) | - | `ApiResponse_Any_` |
| `GET` | `/admin/identity-verifications/{application_id}` | Read an identity application | `application_id` | - | `ApiResponse_Any_` |
| `PUT` | `/admin/identity-verifications/{application_id}/decision` | Approve/reject pending identity application | `application_id` | `VerificationDecision` | `ApiResponse_Any_` |
| `GET` | `/admin/qualification-verifications` | List qualification applications | `status`(query, optional) | - | `ApiResponse_Any_` |
| `GET` | `/admin/qualification-verifications/{application_id}` | Read a qualification application | `application_id` | - | `ApiResponse_Any_` |
| `PUT` | `/admin/qualification-verifications/{application_id}/decision` | Approve/reject pending qualification application | `application_id` | `VerificationDecision` | `ApiResponse_Any_` |
| `GET` | `/admin/providers` | Get Admin Providers | `verification_status`(query, optional, ProviderVerificationStatus / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/admin/providers/{provider_profile_id}` | Get Admin Provider By Id | `provider_profile_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/admin/providers/{provider_profile_id}/verification` | Legacy verification only; new providers use separate application decisions | `provider_profile_id`(path, required, integer) | `application/json` -> `ProviderVerificationUpdate` | `ApiResponse_Any_` |
| `GET` | `/admin/providers/{provider_profile_id}/verification-history` | Get Provider Verification History | `provider_profile_id`(path, required, integer)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/admin/refund-requests` | Get All Refund Requests | `status`(query, optional, RefundRequestStatus / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/admin/refund-requests/{refund_request_id}/history` | Get Refund Request Status History | `refund_request_id`(path, required, integer)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/admin/reviews` | Get All Reviews | `is_visible`(query, optional, boolean / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/admin/reviews/{review_id}/visibility` | Update Review Visibility | `review_id`(path, required, integer) | `application/json` -> `ReviewVisibilityUpdate` | `ApiResponse_Any_` |
| `GET` | `/admin/users` | Get Users | `page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/admin/users/{user_id}/status` | Update User Status | `user_id`(path, required, integer) | `application/json` -> `AdminUserStatusUpdate` | `ApiResponse_Any_` |

## Shared

Shared chat, notifications, booking details, attachments, status history.

Auth: required; access checked by resource ownership.

| Method | Path | Purpose | Params | Body | Success |
|---|---|---|---|---|---|
| `GET` | `/bookings/{booking_id}` | Get Booking By Id | `booking_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `GET` | `/bookings/{booking_id}/attachments` | Get Booking Attachments | `booking_id`(path, required, integer)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_PaginatedData_BookingAttachmentResponse__` |
| `POST` | `/bookings/{booking_id}/attachments` | Upload Booking Attachment | `booking_id`(path, required, integer) | `multipart/form-data` -> `Body_upload_booking_attachment_bookings__booking_id__attachments_post` | `ApiResponse_BookingAttachmentResponse_` |
| `DELETE` | `/bookings/{booking_id}/attachments/{attachment_id}` | Delete Booking Attachment | `booking_id`(path, required, integer)<br>`attachment_id`(path, required, integer) | - | `ApiResponse_NoneType_` |
| `GET` | `/bookings/{booking_id}/history` | Get Booking Status History | `booking_id`(path, required, integer)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `POST` | `/chats/{chat_room_id}/attachments` | Upload Chat Attachment | `chat_room_id`(path, required, integer) | `multipart/form-data` -> `Body_upload_chat_attachment_chats__chat_room_id__attachments_post` | `ApiResponse_ChatMessageAttachmentResponse_` |
| `DELETE` | `/chats/{chat_room_id}/attachments/{attachment_id}` | Delete Unsent Chat Attachment | `chat_room_id`(path, required, integer)<br>`attachment_id`(path, required, integer) | - | `ApiResponse_NoneType_` |
| `GET` | `/chats/{chat_room_id}/bookings` | Get Chat Bookings | `chat_room_id`(path, required, integer)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/chats/{chat_room_id}/messages` | Get Chat Messages | `chat_room_id`(path, required, integer)<br>`message_type`(query, optional, ChatMessageType / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_PaginatedData_ChatMessageResponse__` |
| `POST` | `/chats/{chat_room_id}/messages` | Send Chat Message | `chat_room_id`(path, required, integer) | `application/json` -> `ChatMessageCreate` | `ApiResponse_ChatMessageSendResponseData_` |
| `GET` | `/notifications` | Get Notifications | `unread_only`(query, optional, boolean)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/notifications/read-all` | Mark All Notifications As Read | - | - | `ApiResponse_Any_` |
| `GET` | `/notifications/summary` | Get Notification Summary | - | - | `ApiResponse_Any_` |
| `PUT` | `/notifications/{notification_id}/read` | Mark Notification As Read | `notification_id`(path, required, integer) | - | `ApiResponse_Any_` |

## AI

AI chat, tools, pending actions, async tasks, Milvus/Redis/Qwen health.

Auth: required; some admin-only maintenance endpoints.

| Method | Path | Purpose | Params | Body | Success |
|---|---|---|---|---|---|
| `GET` | `/ai/actions` | Get Ai Pending Actions | `status`(query, optional, AIPendingActionStatus / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `POST` | `/ai/actions/confirm` | Confirm a pending AI action. | - | `application/json` -> `AIActionConfirmRequest` | `ApiResponse_Any_` |
| `GET` | `/ai/actions/{action_id}` | Get Ai Pending Action | `action_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `PUT` | `/ai/actions/{action_id}/cancel` | Cancel Ai Action | `action_id`(path, required, integer) | - | `ApiResponse_Any_` |
| `GET` | `/ai/oauth` | Get chat auth status (API key + ChatGPT + Grok) | - | - | `ApiResponse_Any_` |
| `PUT` | `/ai/oauth` | Switch chat auth (`key`, `chatgpt`, or `grok`) | - | `application/json` -> `LLMAuthUpdate` | `ApiResponse_Any_` |
| `PUT` | `/ai/oauth/key` | Save an admin chat API key | - | `application/json` -> `LLMApiKeyUpdate` | `ApiResponse_Any_` |
| `DELETE` | `/ai/oauth/key` | Clear the admin chat API key | - | - | `ApiResponse_Any_` |
| `POST` | `/ai/oauth/models` | List official chat models | - | `application/json` -> `LLMModelsRequest` | `ApiResponse_Any_` |
| `POST` | `/ai/oauth/chatgpt/start` | Start ChatGPT device login | - | - | `ApiResponse_Any_` |
| `POST` | `/ai/oauth/grok/start` | Start Grok device login | - | - | `ApiResponse_Any_` |
| `POST` | `/ai/chat` | Enqueue Ai Chat | - | `application/json` -> `AIChatRequest` | `ApiResponse_Any_` |
| `POST` | `/ai/chat/async` | Enqueue Ai Chat Alias | - | `application/json` -> `AIChatRequest` | `ApiResponse_Any_` |
| `GET` | `/ai/chat/messages` | Get Ai Chat Messages | `page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `DELETE` | `/ai/chat/messages` | Clear Ai Chat Messages | - | - | `ApiResponse_Any_` |
| `POST` | `/ai/chat/sync` | Sync AI chat; may return answers, recommendations, reviews, drafts, confirmations, or tool errors. | - | `application/json` -> `AIChatRequest` | `ApiResponse_AIChatResponseData_` |
| `GET` | `/ai/health/embedding` | Check Ai Embedding Health | - | - | `ApiResponse_Any_` |
| `GET` | `/ai/health/milvus` | Check Ai Milvus Health | - | - | `ApiResponse_Any_` |
| `GET` | `/ai/health/qwen` | Check Ai Qwen Health | - | - | `ApiResponse_Any_` |
| `GET` | `/ai/health/redis` | Check Ai Redis Health | - | - | `ApiResponse_Any_` |
| `POST` | `/ai/milvus/retry-failed-reviews` | Retry Failed Review Embeddings | - | - | `ApiResponse_Any_` |
| `POST` | `/ai/milvus/review-collection` | Create Ai Review Collection | - | - | `ApiResponse_Any_` |
| `GET` | `/ai/milvus/review-sync-status` | Get Review Sync Status | - | - | `ApiResponse_Any_` |
| `POST` | `/ai/milvus/sync-reviews` | Sync Reviews To Milvus | - | - | `ApiResponse_Any_` |
| `POST` | `/ai/recommend-providers` | Recommend Providers | - | `application/json` -> `AIProviderRecommendRequest` | `ApiResponse_Any_` |
| `GET` | `/ai/tasks` | Get Ai Tasks | `task_type`(query, optional, string / null)<br>`status`(query, optional, string / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/ai/tasks/{task_id}` | Get Ai Task Status | `task_id`(path, required, string) | - | `ApiResponse_Any_` |
| `GET` | `/ai/tool-call-logs` | Get Ai Tool Call Logs | `tool_name`(query, optional, string / null)<br>`status`(query, optional, string / null)<br>`page`(query, optional, integer)<br>`page_size`(query, optional, integer) | - | `ApiResponse_Any_` |
| `GET` | `/ai/tools` | Get Ai Tools | - | - | `ApiResponse_Any_` |
| `POST` | `/ai/tools/agent-preview` | Preview Ai Tool Agent | - | `application/json` -> `AIToolAgentPreviewRequest` | `ApiResponse_Any_` |
| `POST` | `/ai/tools/run` | Run Ai Tool | - | `application/json` -> `AIToolExecuteRequest` | `ApiResponse_Any_` |

## Other

Basic health checks.

Auth: none.

| Method | Path | Purpose | Params | Body | Success |
|---|---|---|---|---|---|
| `GET` | `/` | Home | - | - | `-` |
| `GET` | `/health` | Health Check | - | - | `-` |

## WebSocket

| URL | Purpose | Auth | Notes |
|---|---|---|---|
| `ws://127.0.0.1:8000/ws/chats/{chat_room_id}?token=<access_token>` | Real-time chat | token in query | HTTP persists history; WebSocket delivers live messages. |

## Common flows

### Customer booking flow

1. `POST /register` or `POST /login`.
2. `POST /customer/profile` create profile.
3. `GET /providers` or `POST /ai/chat/sync` for search/AI recommendations.
4. `POST /customer/chats/{provider_profile_id}` open chat.
5. `POST /bookings` with attachments, or AI draft then `POST /ai/actions/confirm`.
6. Provider `PUT /provider/bookings/{booking_id}/quote`.
7. Customer accepts the initial quote, then pays with `payment_stage: "visit_fee"`.
8. Provider `PUT /provider/bookings/{booking_id}/start-visit` with arrival evidence.
9. Provider `PUT /provider/bookings/{booking_id}/final-quote`; Customer may reject/revise repeatedly or accept it.
10. Customer accepts the final quote, then pays with `payment_stage: "service_fee"`.
11. Provider `PUT /provider/bookings/{booking_id}/complete` with completion proof.
12. Customer `PUT /customer/bookings/{booking_id}/confirm-complete`, then `POST /bookings/{booking_id}/review`.

### Provider onboarding

1. Register provider account.
2. Submit ID verification, Service verification, and Payout account in any order from Account → Verification.
3. Admin reviews ID/Service applications; iyzico synchronizes the payout account through `/provider/submerchant`.
4. Service approval creates the Provider Profile. New order eligibility requires identity approved + qualification approved + payout active.
5. Demo seed pre-approves the first two checks but only prepares local payout drafts; synchronize a chosen provider explicitly with `backend.seed_sandbox_submerchants --provider-id 29`.

### AI booking flow

1. `POST /ai/chat/sync` with natural language need.
2. AI calls `prepare_booking_draft_action`; missing fields return `booking_draft_missing_info`.
3. User/app fills provider, address, location, schedule.
4. Complete draft returns `ai_action_confirmation` and `confirmation_card`.
5. `POST /ai/actions/confirm` creates the booking.

## Key schema fields

### `UserRegister`

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | yes | Name |
| `email` | `string` | yes | Email |
| `password` | `string` | yes | Password |
| `role` | `UserRole` | yes |  |

### `RegisterResponseData`

| Field | Type | Required | Description |
|---|---|---|---|
| `user` | `UserResponse` | yes |  |

### `TokenResponse`

| Field | Type | Required | Description |
|---|---|---|---|
| `access_token` | `string` | yes | Access Token |
| `refresh_token` | `string` | yes | Refresh Token |
| `token_type` | `string` | no | Token Type |
| `user` | `UserResponse` | yes |  |

### `UserResponse`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `integer` | yes | Id |
| `name` | `string` | yes | Name |
| `email` | `string` | yes | Email |
| `role` | `UserRole` | yes |  |
| `is_active` | `boolean` | no | Is Active |
| `is_banned` | `boolean` | no | Is Banned |
| `last_login_at` | `string / null` | no | Last Login At |
| `created_at` | `string / null` | no | Created At |

### `ProviderProfileCreate`

| Field | Type | Required | Description |
|---|---|---|---|
| `business_name` | `string` | yes | Business Name |
| `bio` | `string` | yes | Bio |
| `service_province` | `string` | yes | Compatibility province projection |
| `service_location_id` | `integer / null` | no | Selected service district ID |
| `latitude` | `number / null` | no | Latitude |
| `longitude` | `number / null` | no | Longitude |
| `tags` | `list[string]` | yes | Tags |
| `certificate_name` | `string` | yes | Certificate Name |
| `certificate_url` | `string` | yes | Certificate Url |
| `hourly_rate` | `integer` | yes | Hourly Rate |

### `ProviderProfileResponse`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `integer` | yes | Id |
| `user_id` | `integer` | yes | User Id |
| `business_name` | `string` | yes | Business Name |
| `bio` | `string` | yes | Bio |
| `service_province` | `string` | yes | Compatibility province projection |
| `service_location_id` | `integer / null` | no | Selected service district ID |
| `latitude` | `number / null` | no | Latitude |
| `longitude` | `number / null` | no | Longitude |
| `tags` | `list[string]` | yes | Tags |
| `certificate_name` | `string` | yes | Certificate Name |
| `certificate_url` | `string` | yes | Certificate Url |
| `hourly_rate` | `integer` | yes | Hourly Rate |
| `verification_status` | `ProviderVerificationStatus` | yes |  |
| `verification_note` | `string / null` | no | Verification Note |

### `ProviderProfileWithRatingResponse`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `integer` | yes | Id |
| `user_id` | `integer` | yes | User Id |
| `business_name` | `string` | yes | Business Name |
| `bio` | `string` | yes | Bio |
| `service_province` | `string` | yes | Compatibility province projection |
| `service_location_id` | `integer / null` | no | Selected service district ID |
| `latitude` | `number / null` | no | Latitude |
| `longitude` | `number / null` | no | Longitude |
| `tags` | `list[string]` | yes | Tags |
| `certificate_name` | `string` | yes | Certificate Name |
| `certificate_url` | `string` | yes | Certificate Url |
| `hourly_rate` | `integer` | yes | Hourly Rate |
| `verification_status` | `ProviderVerificationStatus` | yes |  |
| `verification_note` | `string / null` | no | Verification Note |
| `average_rating` | `number / null` | no | Average Rating |
| `review_count` | `integer` | yes | Review Count |
| `distance_km` | `number / null` | no | Distance Km |
| `is_available_for_requested_time` | `boolean / null` | no | Is Available For Requested Time |

### `CustomerProfileCreate`

| Field | Type | Required | Description |
|---|---|---|---|
| `phone_number` | `string` | yes | Phone Number |
| `address` | `string` | yes | Address |
| `service_province` | `string` | yes | Compatibility province projection |
| `service_location_id` | `integer / null` | no | Selected service district ID |
| `latitude` | `number / null` | no | Latitude |
| `longitude` | `number / null` | no | Longitude |
| `notes` | `string / null` | no | Notes |

### `BookingCreateResponseData`

| Field | Type | Required | Description |
|---|---|---|---|
| `booking` | `BookingDetailResponse` | yes |  |
| `chat_room` | `ChatRoomResponse` | yes |  |
| `chat_message` | `ChatMessageResponse` | yes |  |

### `BookingDetailResponse`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `integer` | yes | Id |
| `customer_id` | `integer` | yes | Customer Id |
| `provider_profile_id` | `integer` | yes | Provider Profile Id |
| `chat_room_id` | `integer / null` | no | Chat Room Id |
| `service_description` | `string` | yes | Service Description |
| `service_address` | `string` | yes | Service Address |
| `service_latitude` | `number` | yes | Service Latitude |
| `service_longitude` | `number` | yes | Service Longitude |
| `booking_at` | `string` | yes | Booking At |
| `scheduled_start_time` | `string` | yes | Scheduled Start Time |
| `scheduled_end_time` | `string` | yes | Scheduled End Time |
| `completed_at` | `string / null` | no | Completed At |
| `total_amount` | `number` | yes | Total Amount |
| `quote_amount` | `number / null` | no | Quote Amount |
| `quote_message` | `string / null` | no | Quote Message |
| `quote_files` | `binary[]` | no | Optional JPG, PNG, PDF, MP4 or MOV files attached to this quote revision when using multipart form data. |
| `quoted_at` | `string / null` | no | Quoted At |
| `status` | `BookingStatus` | yes |  |
| `status_note` | `string / null` | no | Status Note |
| `customer` | `UserResponse / null` | no |  |
| `provider` | `ProviderProfileResponse / null` | no |  |
| `attachments` | `list[BookingAttachmentResponse]` | no | Attachments |
| `complaint_summary` | `BookingComplaintSummaryResponse` | yes |  |

### `BookingStatus`

Direct-flow values: `pending`, `quoted`, `awaiting_visit_payment`, `visit_paid`, `provider_arrived`, `awaiting_final_quote`, `final_quote_sent`, `awaiting_service_payment`, `service_paid`, `awaiting_confirmation`, `completed`, `rejected`, `cancelled`, `cancelled_before_visit`, `provider_no_show`, `visit_completed_closed`, `service_cancelled_after_payment`, `refunding`, `refunded`, `partially_refunded`. `awaiting_payment` and `accepted` remain accepted legacy enum values, not new payment stages.

### `PaymentCreate`

| Field | Type | Required | Description |
|---|---|---|---|
| `payment_method` | `string` | no | Payment method; use `iyzico_checkout` (the backend currently routes payment through iyzico Sandbox). |
| `payment_stage` | `string` | no | `visit_fee` or `service_fee`; otherwise inferred from the booking stage. |

### `PaymentStatus`

Allowed values: `pending`, `checkout_created`, `processing`, `authorized`, `paid`, `voided`, `failed`, `capture_failed`, `refund_failed`, `refunded`, `partially_refunded`

### `RefundRequestCreate`

| Field | Type | Required | Description |
|---|---|---|---|
| `reason` | `string` | yes | Reason |
| `refund_amount` | `number` | no | Full refund when omitted; otherwise a positive amount not exceeding the booking's paid total. |

### `ProviderBookingQuoteCreate`

| Field | Type | Required | Description |
|---|---|---|---|
| `expected_service_amount` | `number` | initial quote | Positive expected work amount, separate from the visit fee. |
| `visit_fee_amount` | `number` | initial quote | Positive visit fee, no greater than the expected service amount. |
| `quote_amount` | `number` | final quote | Positive final service amount; also accepted as the initial expected amount alias. |
| `quote_message` | `string / null` | no | Quote Message |

### `BookingNoteUpdate`

| Field | Type | Required | Description |
|---|---|---|---|
| `status_note` | `string` | yes | Status Note |

### `ComplaintCreate`

| Field | Type | Required | Description |
|---|---|---|---|
| `reason` | `string` | yes | Reason |

### `ReviewCreate`

| Field | Type | Required | Description |
|---|---|---|---|
| `rating` | `integer` | yes | Rating |
| `comment` | `string / null` | no | Comment |

### `ReviewUpdate`

| Field | Type | Required | Description |
|---|---|---|---|
| `rating` | `integer` | yes | Rating |
| `comment` | `string / null` | no | Comment |

### `ChatMessageCreate`

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | `string / null` | no | Message |
| `attachment_ids` | `list[integer]` | no | Attachment Ids |

### `ChatMessageResponse`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `integer` | yes | Id |
| `chat_room_id` | `integer` | yes | Chat Room Id |
| `sender_id` | `integer` | yes | Sender Id |
| `sender` | `UserResponse / null` | no |  |
| `message` | `string` | yes | Message |
| `message_type` | `ChatMessageType` | yes |  |
| `related_type` | `string / null` | no | Related Type |
| `related_id` | `integer / null` | no | Related Id |
| `metadata` | `object / null` | no | Metadata |
| `attachments` | `list[ChatMessageAttachmentResponse]` | no | Attachments |
| `created_at` | `string` | yes | Created At |
| `read_at` | `string / null` | no | Read At |

### `ChatRoomResponse`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `integer` | yes | Id |
| `customer_id` | `integer` | yes | Customer Id |
| `provider_profile_id` | `integer` | yes | Provider Profile Id |
| `created_at` | `string` | yes | Created At |
| `last_message_at` | `string / null` | no | Last Message At |
| `customer` | `UserResponse / null` | no |  |
| `customer_online` | `boolean` | yes | Customer Online |
| `provider` | `ProviderProfileWithRatingResponse / null` | no |  |
| `provider_online` | `boolean` | yes | Provider Online |
| `last_message` | `ChatMessageResponse / null` | no |  |
| `unread_count` | `integer / null` | no | Unread Count |

### `AIChatRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | `string` | yes | Message |
| `service_province` | `string / null` | no | Service Province |
| `service_address` | `string / null` | no | Service Address |
| `max_price` | `number / null` | no | Max Price |
| `latitude` | `number / null` | no | Latitude |
| `longitude` | `number / null` | no | Longitude |
| `max_distance_km` | `number / null` | no | Max Distance Km |
| `scheduled_start_time` | `string / null` | no | Scheduled Start Time |
| `scheduled_end_time` | `string / null` | no | Scheduled End Time |
| `candidate_provider_ids` | `list[integer]` | no | Candidate Provider Ids |

### `AIChatResponseData`

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | `string` | yes | Message |
| `type` | `string` | yes | Type |
| `intent` | `AIIntentResponse | object` | yes | Intent |
| `answer` | `string` | yes | Answer |
| `service_province` | `string / null` | no | Service Province |
| `service_address` | `string / null` | no | Service Address |
| `max_price` | `number / null` | no | Max Price |
| `latitude` | `number / null` | no | Latitude |
| `longitude` | `number / null` | no | Longitude |
| `max_distance_km` | `number / null` | no | Max Distance Km |
| `scheduled_start_time` | `string / null` | no | Scheduled Start Time |
| `scheduled_end_time` | `string / null` | no | Scheduled End Time |
| `candidate_provider_ids` | `list[integer]` | no | Candidate Provider Ids |
| `extracted_need` | `object / null` | no | Extracted Need |
| `recommendation_count` | `integer / null` | no | Recommendation Count |
| `recommendations` | `list[object] / null` | no | Recommendations |
| `review_context_source` | `string / null` | no | Review Context Source |
| `review_context` | `object / list[object] / null` | no | Review Context |
| `chat_room` | `object / null` | no | Chat Room |
| `chat_room_created` | `boolean / null` | no | Chat Room Created |
| `booking` | `object / null` | no | Booking |
| `status_explanation` | `string / null` | no | Status Explanation |
| `recent_status_histories` | `list[object] / null` | no | Recent Status Histories |
| `payments` | `list[object] / null` | no | Payments |
| `refund_requests` | `list[object] / null` | no | Refund Requests |
| `topic` | `string / null` | no | Topic |
| `flow_steps` | `list[object] / null` | no | Flow Steps |
| `statuses` | `object / list[object] / null` | no | Statuses |
| `pending_action` | `object / null` | no | Pending Action |
| `confirmation_card` | `AIConfirmationCardResponse | object / null` | no | Confirmation Card |
| `booking_draft` | `AIBookingDraftResponse | object / null` | no | Booking Draft |
| `booking_draft_status` | `string / null` | no | Booking Draft Status |
| `booking_draft_preview` | `object / null` | no | Booking Draft Preview |
| `missing_fields` | `list[AIBookingDraftMissingFieldResponse | object] / null` | no | Missing Fields |
| `provider_choices` | `list[object] / null` | no | Provider Choices |
| `next_question` | `string / null` | no | Next Question |
| `tool_error` | `AIToolErrorData | object / null` | no | Tool Error |
| `pending_clarification` | `AIPendingClarificationResponse | object / null` | no | Pending Clarification |
| `tool_calls` | `list[AIToolCallResponse | object]` | no | Tool Calls |
| `tool_results` | `list[object] / null` | no | Tool Results |

### `AIBookingDraftResponse`

| Field | Type | Required | Description |
|---|---|---|---|
| `draft_status` | `string` | yes | Draft Status |
| `draft_type` | `string` | no | Draft Type |
| `provided_fields` | `object` | no | Provided Fields |
| `missing_field_names` | `list[string]` | no | Missing Field Names |
| `missing_fields` | `list[AIBookingDraftMissingFieldResponse]` | no | Missing Fields |
| `provider_choices` | `list[object]` | no | Provider Choices |
| `preview` | `object / null` | no | Preview |
| `next_question` | `string / null` | no | Next Question |

### `AIConfirmationCardResponse`

| Field | Type | Required | Description |
|---|---|---|---|
| `ui_type` | `string` | no | Ui Type |
| `action_id` | `integer` | yes | Action Id |
| `action_type` | `string` | yes | Action Type |
| `title` | `string` | yes | Title |
| `description` | `string / null` | no | Description |
| `status` | `string` | yes | Status |
| `expires_at` | `string` | yes | Expires At |
| `fields` | `list[AIConfirmationFieldResponse]` | no | Fields |
| `provider` | `object / null` | no | Provider |
| `booking_id` | `integer / null` | no | Booking Id |
| `refund_request_id` | `integer / null` | no | Refund Request Id |
| `warnings` | `list[string]` | no | Warnings |
| `warning` | `string / null` | no | Warning |
| `confirm_label` | `string` | no | Confirm Label |
| `cancel_label` | `string` | no | Cancel Label |
| `confirm_endpoint` | `string` | yes | Confirm Endpoint |
| `confirm_request` | `object` | yes | Confirm Request |
| `cancel_endpoint` | `string` | yes | Cancel Endpoint |

### `AIToolErrorData`

| Field | Type | Required | Description |
|---|---|---|---|
| `tool_name` | `string / null` | no | Tool Name |
| `tool_args` | `object` | no | Tool Args |
| `error` | `string / null` | no | Error |
| `error_code` | `string / null` | no | Error Code |
| `error_type` | `string / null` | no | Error Type |
| `status_code` | `integer / null` | no | Status Code |
| `error_details` | `Any` | no | Error Details |

### `AIActionConfirmRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| `action_id` | `integer` | yes | Action Id |
