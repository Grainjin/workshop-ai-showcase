"""Admin API.

Cross-role platform management: users, provider verification, bookings, complaints,
refunds, review visibility, and stats. Not for customer/provider roles.
"""

from datetime import datetime, timezone
from fastapi import Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend import models
from backend.auth import get_db, require_admin
from backend.utils.booking import (
    add_booking_status_history,
    ensure_admin_booking_status_update_allowed,
    format_booking_detail_response,
    get_booking_or_404,
    save_booking,
)
from backend.utils.chat import (
    create_booking_status_chat_message,
    format_chat_message_response,
    format_chat_room_response,
    get_chat_room_or_404,
    push_chat_message_to_room_members,
)
from backend.utils.complaint import (
    add_complaint_status_history,
    format_complaint_response,
)
from backend.utils.formatters import (
    format_provider_portfolio_response,
    format_user_response,
)
from backend.utils.notification import create_notification
from backend.utils.pagination import build_paginated_response, paginate_query
from backend.utils.payment import format_payment_response
from backend.utils.marketplace import format_submerchant_response
from backend.utils.provider import (
    add_provider_verification_history,
    format_provider_profile_with_rating,
)
from backend.utils.refund import (
    add_refund_request_status_history,
    execute_external_refund,
    format_refund_request_response,
    ensure_refund_can_restore_previous_booking_status,
)
from backend.utils.review import format_review_detail_response
from backend.utils.review_embedding_queue import (
    enqueue_review_embedding_delete,
    enqueue_review_embedding_sync,
)
from backend.utils.router import ApiRouter
from backend.utils.demo_mode import reject_demo_restricted_action
from backend.schemas import (
    AdminBookingStatusUpdate,
    AdminComplaintStatusUpdate,
    AdminRefundDecisionCreate,
    AdminUserStatusUpdate,
    BookingStatus,
    ComplaintStatus,
    NotificationRelatedType,
    NotificationType,
    PaymentStatus,
    ProviderVerificationStatus,
    ProviderPortfolioVerificationUpdate,
    ProviderVerificationUpdate,
    RefundRequestStatus,
    ReviewVisibilityUpdate,
    SettlementStatus,
)
from backend.utils.response import success_response
from backend.core.clock import utc_now

router = ApiRouter(tags=["Admin"])


def count_by_value(db: Session, model, field, values: list[str]):
    result = {value: 0 for value in values}
    rows = db.query(field, func.count(model.id)).group_by(field).all()
    for value, count in rows:
        result[value] = count
    return result


@router.get("/admin/dashboard")
def get_admin_dashboard(
    current_user: models.User = Depends(require_admin), db: Session = Depends(get_db)
):
    user_roles = ["customer", "provider", "admin"]
    booking_statuses = [status.value for status in BookingStatus]
    payment_statuses = [status.value for status in PaymentStatus]
    provider_verification_statuses = [
        status.value for status in ProviderVerificationStatus
    ]
    complaint_statuses = [status.value for status in ComplaintStatus]
    refund_request_statuses = [status.value for status in RefundRequestStatus]
    paid_amount = (
        db.query(func.coalesce(func.sum(models.Payment.amount), 0))
        .filter(models.Payment.status == PaymentStatus.paid)
        .scalar()
    )
    refunded_amount = (
        db.query(func.coalesce(func.sum(models.Payment.amount), 0))
        .filter(models.Payment.status == PaymentStatus.refunded)
        .scalar()
    )
    return success_response(
        {
            "users": {
                "total": db.query(models.User).count(),
                "by_role": count_by_value(
                    db, models.User, models.User.role, user_roles
                ),
            },
            "providers": {
                "total": db.query(models.ProviderProfile).count(),
                "by_verification_status": count_by_value(
                    db,
                    models.ProviderProfile,
                    models.ProviderProfile.verification_status,
                    provider_verification_statuses,
                ),
            },
            "provider_portfolios": {
                "total": db.query(models.ProviderPortfolio).count(),
                "by_verification_status": count_by_value(
                    db,
                    models.ProviderPortfolio,
                    models.ProviderPortfolio.verification_status,
                    provider_verification_statuses,
                ),
            },
            "bookings": {
                "total": db.query(models.Booking).count(),
                "by_status": count_by_value(
                    db, models.Booking, models.Booking.status, booking_statuses
                ),
            },
            "payments": {
                "total": db.query(models.Payment).count(),
                "by_status": count_by_value(
                    db, models.Payment, models.Payment.status, payment_statuses
                ),
                "paid_amount": float(paid_amount),
                "refunded_amount": float(refunded_amount),
            },
            "refund_requests": {
                "total": db.query(models.RefundRequest).count(),
                "by_status": count_by_value(
                    db,
                    models.RefundRequest,
                    models.RefundRequest.status,
                    refund_request_statuses,
                ),
            },
            "complaints": {
                "total": db.query(models.Complaint).count(),
                "by_status": count_by_value(
                    db, models.Complaint, models.Complaint.status, complaint_statuses
                ),
            },
            "reviews": {
                "total": db.query(models.Review).count(),
                "visible": db.query(models.Review)
                .filter(models.Review.is_visible == 1)
                .count(),
                "hidden": db.query(models.Review)
                .filter(models.Review.is_visible == 0)
                .count(),
            },
            "chats": {
                "total_rooms": db.query(models.ChatRoom).count(),
                "total_messages": db.query(models.ChatMessage).count(),
            },
            "notifications": {
                "total": db.query(models.Notification).count(),
                "unread": db.query(models.Notification)
                .filter(models.Notification.read_at.is_(None))
                .count(),
            },
        }
    )


@router.get("/admin/users")
def get_users(
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.User).order_by(models.User.id.desc())
    users, total, page, page_size = paginate_query(query, page, page_size)
    safe_users = []
    for user in users:
        safe_users.append(format_user_response(user))
    return success_response(
        build_paginated_response(safe_users, total, page, page_size)
    )


@router.put("/admin/users/{user_id}/status")
def update_user_status(
    user_id: int,
    status_data: AdminUserStatusUpdate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "update_user_status")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id and (
        status_data.is_active is False or status_data.is_banned is True
    ):
        raise HTTPException(
            status_code=400, detail="You cannot disable or ban yourself"
        )
    if status_data.is_active is not None:
        user.is_active = status_data.is_active
    if status_data.is_banned is not None:
        user.is_banned = status_data.is_banned
    if user.is_active is False or user.is_banned is True:
        db.query(models.RefreshToken).filter(
            models.RefreshToken.user_id == user.id,
            models.RefreshToken.revoked_at.is_(None),
        ).update(
            {models.RefreshToken.revoked_at: utc_now()},
            synchronize_session=False,
        )
    db.commit()
    db.refresh(user)
    return success_response(
        {
            "message": "User status updated successfully",
            "user": format_user_response(user),
        }
    )


@router.get("/admin/providers")
def get_admin_providers(
    verification_status: ProviderVerificationStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.ProviderProfile)
    if verification_status:
        query = query.filter(
            models.ProviderProfile.verification_status == verification_status
        )
    query = query.order_by(models.ProviderProfile.id.desc())
    profiles, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for profile in profiles:
        result.append(format_provider_profile_with_rating(profile, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.get("/admin/providers/{provider_profile_id}")
def get_admin_provider_by_id(
    provider_profile_id: int,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == provider_profile_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Provider profile not found")
    return success_response(format_provider_profile_with_rating(profile, db))


@router.put("/admin/providers/{provider_profile_id}/verification")
def update_provider_verification(
    provider_profile_id: int,
    verification_data: ProviderVerificationUpdate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "update_provider_verification")
    profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == provider_profile_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Provider profile not found")
    provider_user = db.query(models.User).filter(models.User.id == profile.user_id).first()
    if provider_user and provider_user.identity_verification_status is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Use the identity-verifications and qualification-verifications "
                "decision endpoints"
            ),
        )
    step = verification_data.verification_step
    if step is None:
        old_status = profile.verification_status
        new_status = verification_data.verification_status
        profile.identity_verification_status = new_status
        profile.qualification_verification_status = new_status
        history_step = "legacy"
    elif step == "identity":
        old_status = profile.identity_verification_status
        new_status = verification_data.verification_status
        profile.identity_verification_status = new_status
        if new_status != ProviderVerificationStatus.approved:
            profile.qualification_verification_status = new_status
        history_step = step
    else:
        old_status = profile.qualification_verification_status
        new_status = verification_data.verification_status
        profile.qualification_verification_status = new_status
        history_step = step
    profile.verification_status = profile.qualification_verification_status
    profile.verification_note = verification_data.verification_note
    add_provider_verification_history(
        profile,
        old_status,
        new_status,
        profile.verification_note,
        current_user,
        db,
        verification_step=history_step,
    )
    if old_status != new_status:
        if new_status == ProviderVerificationStatus.approved:
            create_notification(
                profile.user_id,
                f"Provider {history_step} approved",
                f"Your provider {history_step} review was approved."
                + (" You can now appear in listings and accept bookings." if step == "qualification" else ""),
                NotificationType.provider_profile_approved,
                NotificationRelatedType.provider_profile,
                profile.id,
                db,
            )
        elif new_status == ProviderVerificationStatus.rejected:
            create_notification(
                profile.user_id,
                f"Provider {history_step} rejected",
                f"Your provider {history_step} review was rejected. Reason: {verification_data.verification_note}",
                NotificationType.provider_profile_rejected,
                NotificationRelatedType.provider_profile,
                profile.id,
                db,
            )
    db.commit()
    db.refresh(profile)
    return success_response(
        {
            "message": "Provider verification updated successfully",
            "profile": format_provider_profile_with_rating(profile, db),
        }
    )


@router.get("/admin/providers/{provider_profile_id}/verification-history")
def get_provider_verification_history(
    provider_profile_id: int,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == provider_profile_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Provider profile not found")
    query = (
        db.query(models.ProviderVerificationHistory)
        .filter(
            models.ProviderVerificationHistory.provider_profile_id
            == provider_profile_id
        )
        .order_by(models.ProviderVerificationHistory.changed_at.asc())
    )
    histories, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for history in histories:
        result.append(
            {
                "id": history.id,
                "provider_profile_id": history.provider_profile_id,
                "changed_by_user_id": history.changed_by_user_id,
                "old_status": history.old_status,
                "new_status": history.new_status,
                "verification_step": getattr(history, "verification_step", "qualification"),
                "note": history.note,
                "changed_at": history.changed_at,
            }
        )
    return success_response(build_paginated_response(result, total, page, page_size))


@router.get("/admin/provider-portfolios")
def get_admin_provider_portfolios(
    verification_status: ProviderVerificationStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.ProviderPortfolio)
    if verification_status:
        query = query.filter(
            models.ProviderPortfolio.verification_status == verification_status
        )
    query = query.order_by(models.ProviderPortfolio.created_at.desc())
    portfolios, total, page, page_size = paginate_query(query, page, page_size)
    result = [
        format_provider_portfolio_response(portfolio, db) for portfolio in portfolios
    ]
    return success_response(build_paginated_response(result, total, page, page_size))


@router.get("/admin/provider-portfolios/{portfolio_id}")
def get_admin_provider_portfolio_by_id(
    portfolio_id: int,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    portfolio = (
        db.query(models.ProviderPortfolio)
        .filter(models.ProviderPortfolio.id == portfolio_id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    return success_response(format_provider_portfolio_response(portfolio, db))


@router.put("/admin/provider-portfolios/{portfolio_id}/verification")
def update_provider_portfolio_verification(
    portfolio_id: int,
    verification_data: ProviderPortfolioVerificationUpdate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "update_provider_portfolio_verification")
    portfolio = (
        db.query(models.ProviderPortfolio)
        .filter(models.ProviderPortfolio.id == portfolio_id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio item not found")

    old_status = portfolio.verification_status
    portfolio.verification_status = verification_data.verification_status
    portfolio.verification_note = verification_data.verification_note
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == portfolio.provider_profile_id)
        .first()
    )

    if provider_profile and old_status != portfolio.verification_status:
        if portfolio.verification_status == ProviderVerificationStatus.approved:
            create_notification(
                provider_profile.user_id,
                "Portfolio approved",
                f"Your portfolio '{portfolio.title}' was approved.",
                NotificationType.provider_portfolio_approved,
                NotificationRelatedType.provider_portfolio,
                portfolio.id,
                db,
            )
        elif portfolio.verification_status == ProviderVerificationStatus.rejected:
            create_notification(
                provider_profile.user_id,
                "Portfolio rejected",
                (
                    f"Your portfolio '{portfolio.title}' was rejected. "
                    f"Reason: {verification_data.verification_note}"
                ),
                NotificationType.provider_portfolio_rejected,
                NotificationRelatedType.provider_portfolio,
                portfolio.id,
                db,
            )

    db.commit()
    db.refresh(portfolio)
    return success_response(
        {
            "message": "Provider portfolio verification updated successfully",
            "portfolio": format_provider_portfolio_response(portfolio, db),
        }
    )


@router.get("/admin/bookings")
def get_all_bookings(
    status: BookingStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.Booking)
    if status:
        query = query.filter(models.Booking.status == status)
    query = query.order_by(models.Booking.booking_at.desc())
    bookings, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for booking in bookings:
        result.append(format_booking_detail_response(booking, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.put("/admin/bookings/{booking_id}/status")
async def admin_update_booking_status(
    booking_id: int,
    status_data: AdminBookingStatusUpdate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "admin_update_booking_status")
    booking = get_booking_or_404(booking_id, db)
    ensure_admin_booking_status_update_allowed(booking, status_data.status, db)
    old_status = booking.status
    booking.status = status_data.status
    booking.status_note = status_data.status_note
    if status_data.status == BookingStatus.completed:
        booking.completed_at = utc_now()
    add_booking_status_history(
        booking, old_status, booking.status, booking.status_note, current_user, db
    )
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Admin updated the booking status",
        booking.status_note,
        db,
        {
            "admin_note": booking.status_note,
            "completed_at": booking.completed_at,
        },
    )
    create_notification(
        booking.customer_id,
        "Booking status updated",
        "An admin updated your booking status",
        NotificationType.booking_status_updated_by_admin,
        NotificationRelatedType.booking,
        booking.id,
        db,
    )
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == booking.provider_profile_id)
        .first()
    )
    if provider_profile:
        create_notification(
            provider_profile.user_id,
            "Booking status updated",
            "An admin updated one of your booking statuses",
            NotificationType.booking_status_updated_by_admin,
            NotificationRelatedType.booking,
            booking.id,
            db,
        )
    result = save_booking(booking, db)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    result["booking"] = format_booking_detail_response(booking, db)
    result["message"] = "Booking status updated by admin"
    return success_response(result)


@router.get("/admin/payments")
def get_all_payments(
    status: PaymentStatus | None = None,
    settlement_status: SettlementStatus | None = None,
    provider_profile_id: int | None = None,
    booking_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.Payment)
    if status:
        query = query.filter(models.Payment.status == status)
    if settlement_status:
        query = query.join(
            models.PaymentSettlement,
            models.PaymentSettlement.payment_id == models.Payment.id,
        ).filter(models.PaymentSettlement.status == settlement_status)
    if provider_profile_id is not None:
        query = query.filter(
            models.Payment.provider_profile_id == provider_profile_id
        )
    if booking_id is not None:
        query = query.filter(models.Payment.booking_id == booking_id)
    query = query.order_by(models.Payment.created_at.desc())
    payments, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for payment in payments:
        result.append(format_payment_response(payment, db, include_settlement=True))
    return success_response(build_paginated_response(result, total, page, page_size))


def _mask_secret(value: str | None) -> str | None:
    if not value:
        return value
    if len(value) <= 4:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]


@router.get("/admin/submerchants")
def get_admin_submerchants(
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.ProviderSubmerchant).order_by(
        models.ProviderSubmerchant.updated_at.desc()
    )
    submerchants, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for submerchant in submerchants:
        item = format_submerchant_response(submerchant)
        item["iban"] = _mask_secret(item.get("iban"))
        item["identity_number"] = _mask_secret(item.get("identity_number"))
        item["tax_number"] = _mask_secret(item.get("tax_number"))
        result.append(item)
    return success_response(build_paginated_response(result, total, page, page_size))


@router.post("/admin/payments/{payment_id}/settlement/retry")
def retry_payment_settlement(
    payment_id: int,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "retry_payment_settlement")
    payment = db.get(models.Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    settlement = (
        db.query(models.PaymentSettlement)
        .filter(models.PaymentSettlement.payment_id == payment_id)
        .first()
    )
    if not settlement:
        raise HTTPException(status_code=404, detail="Payment settlement not found")
    if settlement.status != SettlementStatus.approval_failed.value:
        raise HTTPException(
            status_code=400,
            detail="Only failed Marketplace approvals can be retried",
        )
    from backend.tasks.marketplace_tasks import enqueue_payment_settlement

    if not enqueue_payment_settlement(payment_id):
        raise HTTPException(status_code=503, detail="Settlement retry could not be queued")
    return success_response(
        {
            "message": "Marketplace settlement retry queued",
            "payment": format_payment_response(payment, db, include_settlement=True),
        }
    )


@router.get("/admin/refund-requests")
def get_all_refund_requests(
    status: RefundRequestStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.RefundRequest)
    if status:
        query = query.filter(models.RefundRequest.status == status)
    query = query.order_by(models.RefundRequest.created_at.desc())
    refund_requests, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for refund_request in refund_requests:
        result.append(format_refund_request_response(refund_request, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.get("/admin/refund-requests/{refund_request_id}/history")
def get_refund_request_status_history(
    refund_request_id: int,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    refund_request = (
        db.query(models.RefundRequest)
        .filter(models.RefundRequest.id == refund_request_id)
        .first()
    )
    if not refund_request:
        raise HTTPException(status_code=404, detail="Refund request not found")
    query = (
        db.query(models.RefundRequestStatusHistory)
        .filter(
            models.RefundRequestStatusHistory.refund_request_id == refund_request.id
        )
        .order_by(models.RefundRequestStatusHistory.changed_at.asc())
    )
    histories, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for history in histories:
        result.append(
            {
                "id": history.id,
                "refund_request_id": history.refund_request_id,
                "changed_by_user_id": history.changed_by_user_id,
                "old_status": history.old_status,
                "new_status": history.new_status,
                "note": history.note,
                "changed_at": history.changed_at,
            }
        )
    return success_response(build_paginated_response(result, total, page, page_size))


@router.put("/admin/refund-requests/{refund_request_id}/approve")
async def admin_approve_refund_request(
    refund_request_id: int,
    decision_data: AdminRefundDecisionCreate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "admin_approve_refund_request")
    refund_request = (
        db.query(models.RefundRequest)
        .filter(models.RefundRequest.id == refund_request_id)
        .first()
    )
    if not refund_request:
        raise HTTPException(status_code=404, detail="Refund request not found")
    if refund_request.status != RefundRequestStatus.appealed:
        raise HTTPException(
            status_code=400,
            detail="Only appealed refund requests can be approved by admin",
        )

    booking = (
        db.query(models.Booking)
        .filter(models.Booking.id == refund_request.booking_id)
        .first()
    )
    payment = (
        db.query(models.Payment)
        .filter(
            models.Payment.id == refund_request.payment_id,
            models.Payment.status.in_([PaymentStatus.paid, PaymentStatus.partially_refunded]),
        )
        .first()
    )
    if not booking or not payment:
        raise HTTPException(
            status_code=400,
            detail="Booking or paid payment not found for this refund request",
        )
    if booking.status != BookingStatus.refunding:
        raise HTTPException(
            status_code=400,
            detail="Only refunding bookings can be refunded by admin",
        )

    await execute_external_refund(payment, refund_request, db)
    now = utc_now()
    old_status = booking.status
    old_refund_status = refund_request.status
    refund_request.status = RefundRequestStatus.approved
    refund_request.admin_note = decision_data.admin_note
    refund_request.admin_responded_at = now
    refund_request.refunded_at = now
    booking.status = (
        BookingStatus.refunded
        if refund_request.refund_amount >= payment.amount
        else BookingStatus.partially_refunded
    )
    booking.status_note = decision_data.admin_note
    add_booking_status_history(
        booking, old_status, booking.status, booking.status_note, current_user, db
    )
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Admin approved the refund appeal",
        booking.status_note,
        db,
        {
            "refund_request_id": refund_request.id,
            "refund_status": refund_request.status,
            "payment_id": payment.id,
            "payment_status": payment.status,
            "admin_note": refund_request.admin_note,
            "refunded_at": refund_request.refunded_at,
        },
    )
    add_refund_request_status_history(
        refund_request,
        old_refund_status,
        refund_request.status,
        refund_request.admin_note,
        current_user,
        db,
    )
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == refund_request.provider_profile_id)
        .first()
    )
    create_notification(
        refund_request.customer_id,
        "Refund appeal approved",
        "Customer service approved the refund",
        NotificationType.refund_admin_approved,
        NotificationRelatedType.refund_request,
        refund_request.id,
        db,
    )
    if provider_profile:
        create_notification(
            provider_profile.user_id,
            "Refund appeal approved",
            "Customer service approved the refund",
            NotificationType.refund_admin_approved,
            NotificationRelatedType.refund_request,
            refund_request.id,
            db,
        )

    db.commit()
    db.refresh(refund_request)
    db.refresh(payment)
    db.refresh(booking)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)

    return success_response(
        {
            "message": "Refund appeal approved by admin",
            "refund_request": format_refund_request_response(refund_request, db),
            "booking": format_booking_detail_response(booking, db),
            "payment": format_payment_response(payment, db),
        }
    )


@router.put("/admin/refund-requests/{refund_request_id}/reject")
async def admin_reject_refund_request(
    refund_request_id: int,
    decision_data: AdminRefundDecisionCreate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "admin_reject_refund_request")
    refund_request = (
        db.query(models.RefundRequest)
        .filter(models.RefundRequest.id == refund_request_id)
        .first()
    )
    if not refund_request:
        raise HTTPException(status_code=404, detail="Refund request not found")
    if refund_request.status != RefundRequestStatus.appealed:
        raise HTTPException(
            status_code=400,
            detail="Only appealed refund requests can be rejected by admin",
        )

    booking = (
        db.query(models.Booking)
        .filter(models.Booking.id == refund_request.booking_id)
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status != BookingStatus.refunding:
        raise HTTPException(
            status_code=400,
            detail="Only refunding bookings can be restored after admin rejection",
        )
    ensure_refund_can_restore_previous_booking_status(refund_request)

    now = utc_now()
    old_status = booking.status
    old_refund_status = refund_request.status
    refund_request.status = RefundRequestStatus.admin_rejected
    refund_request.admin_note = decision_data.admin_note
    refund_request.admin_responded_at = now
    booking.status = refund_request.previous_booking_status
    booking.status_note = decision_data.admin_note
    add_booking_status_history(
        booking, old_status, booking.status, booking.status_note, current_user, db
    )
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Admin rejected the refund appeal",
        booking.status_note,
        db,
        {
            "refund_request_id": refund_request.id,
            "refund_status": refund_request.status,
            "admin_note": refund_request.admin_note,
            "restored_booking_status": booking.status,
        },
    )
    add_refund_request_status_history(
        refund_request,
        old_refund_status,
        refund_request.status,
        refund_request.admin_note,
        current_user,
        db,
    )
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == refund_request.provider_profile_id)
        .first()
    )
    create_notification(
        refund_request.customer_id,
        "Refund appeal rejected",
        "Customer service rejected the refund appeal",
        NotificationType.refund_admin_rejected,
        NotificationRelatedType.refund_request,
        refund_request.id,
        db,
    )
    if provider_profile:
        create_notification(
            provider_profile.user_id,
            "Refund appeal rejected",
            "Customer service rejected the refund appeal",
            NotificationType.refund_admin_rejected,
            NotificationRelatedType.refund_request,
            refund_request.id,
            db,
        )

    db.commit()
    db.refresh(refund_request)
    db.refresh(booking)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)

    return success_response(
        {
            "message": "Refund appeal rejected by admin",
            "refund_request": format_refund_request_response(refund_request, db),
            "booking": format_booking_detail_response(booking, db),
        }
    )


@router.get("/admin/chats")
def get_all_chats(
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.ChatRoom).order_by(
        models.ChatRoom.last_message_at.desc().nullslast()
    )
    chat_rooms, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for chat_room in chat_rooms:
        result.append(format_chat_room_response(chat_room, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.get("/admin/chats/{chat_room_id}/messages")
def get_admin_chat_messages(
    chat_room_id: int,
    page: int = 1,
    page_size: int = 50,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    chat_room = get_chat_room_or_404(chat_room_id, db)
    query = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.chat_room_id == chat_room.id)
        .order_by(models.ChatMessage.created_at.desc())
    )
    messages, total, page, page_size = paginate_query(query, page, page_size)
    messages.reverse()
    result = []
    for message in messages:
        result.append(format_chat_message_response(message, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.get("/admin/complaints")
def get_all_complaints(
    status: ComplaintStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.Complaint)
    if status:
        query = query.filter(models.Complaint.status == status)
    query = query.order_by(models.Complaint.created_at.desc())
    complaints, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for complaint in complaints:
        result.append(format_complaint_response(complaint, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.get("/admin/complaints/{complaint_id}")
def get_complaint_by_id(
    complaint_id: int,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    complaint = (
        db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    )
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return success_response(
        format_complaint_response(complaint, db, include_chat_messages=True)
    )


@router.put("/admin/complaints/{complaint_id}/status")
def update_complaint_status(
    complaint_id: int,
    status_data: AdminComplaintStatusUpdate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "update_complaint_status")
    complaint = (
        db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    )
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    old_status = complaint.status
    complaint.status = status_data.status
    complaint.admin_note = status_data.admin_note
    if status_data.status == ComplaintStatus.open:
        complaint.resolved_at = None
    else:
        complaint.resolved_at = utc_now()
    add_complaint_status_history(
        complaint, old_status, complaint.status, complaint.admin_note, current_user, db
    )
    notification_type = NotificationType.complaint_resolved
    notification_title = "Complaint resolved"
    if complaint.status == ComplaintStatus.rejected:
        notification_type = NotificationType.complaint_rejected
        notification_title = "Complaint rejected"
    if complaint.status == ComplaintStatus.open:
        notification_type = NotificationType.complaint_reopened
        notification_title = "Complaint reopened"
    create_notification(
        complaint.customer_id,
        notification_title,
        "An admin updated your complaint",
        notification_type,
        NotificationRelatedType.complaint,
        complaint.id,
        db,
    )
    db.commit()
    db.refresh(complaint)
    return success_response(
        {
            "message": "Complaint status updated successfully",
            "complaint": format_complaint_response(complaint, db),
        }
    )


@router.get("/admin/complaints/{complaint_id}/history")
def get_complaint_status_history(
    complaint_id: int,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    complaint = (
        db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    )
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    query = (
        db.query(models.ComplaintStatusHistory)
        .filter(models.ComplaintStatusHistory.complaint_id == complaint.id)
        .order_by(models.ComplaintStatusHistory.changed_at.asc())
    )
    histories, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for history in histories:
        result.append(
            {
                "id": history.id,
                "complaint_id": history.complaint_id,
                "changed_by_user_id": history.changed_by_user_id,
                "old_status": history.old_status,
                "new_status": history.new_status,
                "note": history.note,
                "changed_at": history.changed_at,
            }
        )
    return success_response(build_paginated_response(result, total, page, page_size))


@router.get("/admin/reviews")
def get_all_reviews(
    is_visible: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.Review)
    if is_visible is not None:
        query = query.filter(models.Review.is_visible == (1 if is_visible else 0))
    query = query.order_by(models.Review.created_at.desc())
    reviews, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for review in reviews:
        result.append(format_review_detail_response(review, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.put("/admin/reviews/{review_id}/visibility")
def update_review_visibility(
    review_id: int,
    visibility_data: ReviewVisibilityUpdate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "update_review_visibility")
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.is_visible = 1 if visibility_data.is_visible else 0
    db.commit()
    db.refresh(review)
    if review.is_visible == 1:
        embedding_task_id = enqueue_review_embedding_sync(review, db, current_user.id)
    else:
        embedding_task_id = enqueue_review_embedding_delete(review, db, current_user.id)
    return success_response(
        {
            "message": "Review visibility updated successfully",
            "embedding_task_id": embedding_task_id,
            "review": format_review_detail_response(review, db),
        }
    )
