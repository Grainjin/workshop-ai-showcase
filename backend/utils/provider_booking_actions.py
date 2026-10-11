"""Provider booking actions.

Provider state changes: quote, reject, complete, approve/reject refund.
All entries verify the provider owns the booking.
"""

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend import models
from backend.schemas import (
    BookingNoteUpdate,
    BookingStatus,
    NotificationRelatedType,
    NotificationType,
    PaymentStatus,
    ProviderBookingQuoteCreate,
    ProviderRefundRejectCreate,
    RefundRequestStatus,
)
from backend.utils.booking import (
    add_booking_status_history,
    ensure_booking_status,
    format_booking_detail_response,
    save_booking,
)
from backend.utils.booking_quote_upload import quote_upload_transaction, save_quote_files
from backend.utils.chat import (
    create_booking_status_chat_message,
    push_chat_message_to_room_members,
)
from backend.utils.notification import create_notification
from backend.utils.payment import format_payment_response
from backend.utils.provider import get_provider_profile_for_user
from backend.utils.refund import (
    add_refund_request_status_history,
    execute_external_refund,
    format_refund_request_response,
)
from backend.utils.upload import delete_local_upload, save_booking_attachment_upload
from backend.utils.demo_proof import record_preset_proof
from backend.core.clock import utc_now


async def start_provider_visit_action(
    booking_id: int,
    current_user: models.User,
    db: Session,
    proof_files: list[UploadFile] | None,
    *,
    demo_proof: bool = False,
):
    """Record the provider's arrival; at least one evidence file is required."""
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == booking_id,
            models.Booking.provider_profile_id == provider_profile.id,
        )
        .with_for_update()
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    ensure_booking_status(booking, [BookingStatus.visit_paid], "Visit fee must be paid before starting the visit")
    if not proof_files and not demo_proof:
        raise HTTPException(status_code=400, detail="Arrival evidence photo or video is required")
    saved = [record_preset_proof(booking.id, "arrival_evidence", current_user, db)] if demo_proof else []
    uploads = []
    for file in proof_files or []:
        if not file.filename:
            continue
        uploads.append(await save_booking_attachment_upload(booking.id, file))
    for upload in uploads:
        attachment = models.BookingAttachment(
            booking_id=booking.id,
            uploaded_by_user_id=current_user.id,
            purpose="arrival_evidence",
            original_file_name=upload["original_file_name"],
            file_name=upload["file_name"],
            file_url=upload["file_url"],
            content_type=upload["content_type"],
            size=upload["size"],
            created_at=utc_now(),
        )
        db.add(attachment)
        saved.append(attachment)
    if not saved:
        raise HTTPException(status_code=400, detail="Arrival evidence photo or video is required")
    old_status = booking.status
    booking.status = BookingStatus.provider_arrived
    booking.arrival_started_at = utc_now()
    booking.status_note = "Provider arrived and submitted visit evidence"
    add_booking_status_history(booking, old_status, booking.status, booking.status_note, current_user, db)
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Provider started the visit",
        booking.status_note,
        db,
        {
            "arrival_started_at": booking.arrival_started_at,
            "arrival_evidence_count": len(saved),
        },
    )
    db.commit()
    db.refresh(booking)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    return {"message": "Visit started", "booking": format_booking_detail_response(booking, db)}


async def submit_final_quote_action(
    booking_id: int,
    quote_data: ProviderBookingQuoteCreate,
    current_user: models.User,
    db: Session,
    quote_files: list[UploadFile] | None = None,
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == booking_id,
            models.Booking.provider_profile_id == provider_profile.id,
        )
        .with_for_update()
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    ensure_booking_status(
        booking,
        [BookingStatus.provider_arrived, BookingStatus.awaiting_final_quote],
        "A final quote can only be submitted after the provider starts the visit",
    )
    if quote_data.quote_amount is None:
        raise HTTPException(status_code=422, detail="Final quote amount is required")
    final_amount = Decimal(str(quote_data.quote_amount)).quantize(Decimal("0.01"))
    async with quote_upload_transaction(db) as saved_urls:
        booking.final_quote_amount = final_amount
        booking.final_quote_message = quote_data.quote_message
        booking.final_quote_declined_at = None
        booking.final_quote_decline_reason = None
        latest = (
            db.query(models.BookingQuoteRevision)
            .filter(models.BookingQuoteRevision.booking_id == booking.id)
            .order_by(models.BookingQuoteRevision.revision_number.desc())
            .with_for_update()
            .first()
        )
        revision = models.BookingQuoteRevision(
            booking_id=booking.id,
            revision_number=(latest.revision_number if latest else 0) + 1,
            quote_amount=final_amount,
            quote_message=quote_data.quote_message,
            created_by_user_id=current_user.id,
            created_at=utc_now(),
        )
        await save_quote_files(
            booking,
            revision,
            current_user,
            db,
            quote_files,
            saved_urls,
        )
        old_status = booking.status
        booking.status = BookingStatus.final_quote_sent
        booking.status_note = (
            quote_data.quote_message.strip()
            if quote_data.quote_message and quote_data.quote_message.strip()
            else "Provider submitted the final quote"
        )
        add_booking_status_history(
            booking,
            old_status,
            booking.status,
            booking.status_note,
            current_user,
            db,
        )
        booking_status_chat_message = create_booking_status_chat_message(
            booking,
            old_status,
            current_user.id,
            "Provider submitted the final quote",
            booking.status_note,
            db,
            {
                "final_quote_amount": booking.final_quote_amount,
                "final_quote_message": booking.final_quote_message,
                "currency": "TRY",
            },
        )
    db.refresh(booking)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    return {"message": "Final quote sent", "booking": format_booking_detail_response(booking, db)}


async def approve_provider_refund_request_action(
    refund_request_id: int,
    current_user: models.User,
    db: Session,
):
    """Provider approves refund.

    Updates refund request, payment, and booking to approved/refunded.
    payment -> refunded, booking -> refunded.
    """

    provider_profile = get_provider_profile_for_user(current_user.id, db)
    refund_request = (
        db.query(models.RefundRequest)
        .filter(
            models.RefundRequest.id == refund_request_id,
            models.RefundRequest.provider_profile_id == provider_profile.id,
        )
        .first()
    )
    if not refund_request:
        raise HTTPException(status_code=404, detail="Refund request not found")
    if refund_request.status != RefundRequestStatus.pending:
        raise HTTPException(
            status_code=400, detail="Only pending refund requests can be approved"
        )

    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == refund_request.booking_id,
            models.Booking.provider_profile_id == provider_profile.id,
        )
        .first()
    )
    payment = (
        db.query(models.Payment)
        .filter(
            models.Payment.id == refund_request.payment_id,
            models.Payment.booking_id == refund_request.booking_id,
            models.Payment.customer_id == refund_request.customer_id,
            models.Payment.provider_profile_id == provider_profile.id,
            models.Payment.status.in_([PaymentStatus.paid, PaymentStatus.partially_refunded]),
        )
        .first()
    )
    if not booking or not payment:
        raise HTTPException(
            status_code=400,
            detail="Booking or paid payment not found for this refund request",
        )

    ensure_booking_status(
        booking, [BookingStatus.refunding], "Only refunding bookings can be refunded"
    )
    await execute_external_refund(payment, refund_request, db)
    now = utc_now()
    old_status = booking.status
    old_refund_status = refund_request.status
    refund_request.status = RefundRequestStatus.approved
    refund_request.responded_at = now
    refund_request.refunded_at = now
    booking.status = (
        BookingStatus.refunded
        if refund_request.refund_amount >= payment.amount
        else BookingStatus.partially_refunded
    )
    booking.status_note = "Provider approved refund request"
    add_booking_status_history(
        booking, old_status, booking.status, booking.status_note, current_user, db
    )
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Provider approved the refund request",
        booking.status_note,
        db,
        {
            "refund_request_id": refund_request.id,
            "refund_status": refund_request.status,
            "payment_id": payment.id,
            "payment_status": payment.status,
            "refunded_at": refund_request.refunded_at,
        },
    )
    add_refund_request_status_history(
        refund_request,
        old_refund_status,
        refund_request.status,
        "Provider approved refund request",
        current_user,
        db,
    )
    create_notification(
        refund_request.customer_id,
        "Refund approved",
        "Your refund request was approved",
        NotificationType.refund_approved,
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

    return {
        "message": "Refund request approved successfully",
        "refund_request": format_refund_request_response(refund_request, db),
        "booking": format_booking_detail_response(booking, db),
        "payment": format_payment_response(payment, db),
    }


async def reject_provider_refund_request_action(
    refund_request_id: int,
    reject_data: ProviderRefundRejectCreate,
    current_user: models.User,
    db: Session,
):
    """Provider rejects refund.

    Refund request becomes rejected but booking stays refunding for further discussion or admin.
    """

    provider_profile = get_provider_profile_for_user(current_user.id, db)
    refund_request = (
        db.query(models.RefundRequest)
        .filter(
            models.RefundRequest.id == refund_request_id,
            models.RefundRequest.provider_profile_id == provider_profile.id,
        )
        .first()
    )
    if not refund_request:
        raise HTTPException(status_code=404, detail="Refund request not found")
    if refund_request.status != RefundRequestStatus.pending:
        raise HTTPException(
            status_code=400, detail="Only pending refund requests can be rejected"
        )

    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == refund_request.booking_id,
            models.Booking.provider_profile_id == provider_profile.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    ensure_booking_status(
        booking,
        [BookingStatus.refunding],
        "Only refunding bookings can keep a rejected refund request",
    )
    old_status = booking.status
    old_refund_status = refund_request.status
    refund_request.status = RefundRequestStatus.rejected
    refund_request.provider_note = reject_data.provider_note
    refund_request.responded_at = utc_now()
    booking.status = BookingStatus.refunding
    booking.status_note = reject_data.provider_note
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Provider rejected the refund request",
        booking.status_note,
        db,
        {
            "refund_request_id": refund_request.id,
            "refund_status": refund_request.status,
            "provider_note": refund_request.provider_note,
            "responded_at": refund_request.responded_at,
        },
    )
    add_refund_request_status_history(
        refund_request,
        old_refund_status,
        refund_request.status,
        refund_request.provider_note,
        current_user,
        db,
    )
    create_notification(
        refund_request.customer_id,
        "Refund rejected",
        "Your refund request was rejected by the provider",
        NotificationType.refund_rejected,
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

    return {
        "message": "Refund request rejected. Booking remains in refunding status",
        "refund_request": format_refund_request_response(refund_request, db),
        "booking": format_booking_detail_response(booking, db),
    }


async def quote_provider_booking_action(
    booking_id: int,
    quote_data: ProviderBookingQuoteCreate,
    current_user: models.User,
    db: Session,
    quote_files: list[UploadFile] | None = None,
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == booking_id,
            models.Booking.provider_profile_id == provider_profile.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    ensure_booking_status(
        booking, [BookingStatus.pending], "Only pending bookings can receive a quote"
    )
    if quote_data.visit_fee_amount is None:
        raise HTTPException(
            status_code=422,
            detail="Visit fee is required for the initial quote",
        )
    if quote_data.expected_service_amount is None and quote_data.quote_amount is None:
        raise HTTPException(
            status_code=422,
            detail="Expected service amount is required for the initial quote",
        )
    expected_service_amount = Decimal(
        str(quote_data.expected_service_amount or quote_data.quote_amount)
    ).quantize(Decimal("0.01"))
    visit_fee_amount = Decimal(
        str(quote_data.visit_fee_amount)
    ).quantize(Decimal("0.01"))
    if visit_fee_amount > expected_service_amount:
        raise HTTPException(
            status_code=422,
            detail="Visit fee cannot exceed the expected service amount",
        )
    async with quote_upload_transaction(db) as saved_urls:
        old_status = booking.status
        booking.status = BookingStatus.quoted
        # Retain the existing legacy quote_amount alias for payment/AI callers.
        booking.quote_amount = expected_service_amount
        booking.quote_message = quote_data.quote_message
        booking.expected_service_amount = expected_service_amount
        booking.visit_fee_amount = visit_fee_amount
        booking.final_quote_amount = None
        booking.final_quote_message = None
        booking.total_amount = expected_service_amount + visit_fee_amount
        booking.quoted_at = utc_now()
        booking.status_note = (
            quote_data.quote_message.strip()
            if quote_data.quote_message and quote_data.quote_message.strip()
            else "Provider submitted an initial quote"
        )
        latest_revision = (
            db.query(models.BookingQuoteRevision)
            .filter(models.BookingQuoteRevision.booking_id == booking.id)
            .order_by(models.BookingQuoteRevision.revision_number.desc())
            .with_for_update()
            .first()
        )
        revision = models.BookingQuoteRevision(
            booking_id=booking.id,
            revision_number=(latest_revision.revision_number if latest_revision else 0) + 1,
            quote_amount=expected_service_amount,
            quote_message=quote_data.quote_message,
            expected_service_amount=expected_service_amount,
            visit_fee_amount=visit_fee_amount,
            total_amount=expected_service_amount + visit_fee_amount,
            created_by_user_id=current_user.id,
            created_at=utc_now(),
        )
        await save_quote_files(
            booking,
            revision,
            current_user,
            db,
            quote_files,
            saved_urls,
        )
        add_booking_status_history(
            booking, old_status, booking.status, booking.status_note, current_user, db
        )
        booking_status_chat_message = create_booking_status_chat_message(
            booking,
            old_status,
            current_user.id,
            f"Provider submitted a quote: visit fee {booking.visit_fee_amount} TRY",
            booking.status_note,
            db,
            {
                "quote_amount": booking.quote_amount,
                "expected_service_amount": booking.expected_service_amount,
                "visit_fee_amount": booking.visit_fee_amount,
                "quote_message": booking.quote_message,
                "quoted_at": booking.quoted_at,
                "currency": "TRY",
            },
        )
        create_notification(
            booking.customer_id,
            "New quote received",
            "A provider sent you a quote for your booking",
            NotificationType.booking_quoted,
            NotificationRelatedType.booking,
            booking.id,
            db,
        )
    db.refresh(booking)
    result = {}
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    result["booking"] = format_booking_detail_response(booking, db)
    result["message"] = "Booking quoted successfully"

    return result


async def reject_provider_booking_action(
    booking_id: int,
    note_data: BookingNoteUpdate,
    current_user: models.User,
    db: Session,
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == booking_id,
            models.Booking.provider_profile_id == provider_profile.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    ensure_booking_status(
        booking, [BookingStatus.pending], "Only pending bookings can be rejected"
    )
    old_status = booking.status
    booking.status = BookingStatus.rejected
    booking.status_note = note_data.status_note
    add_booking_status_history(
        booking, old_status, booking.status, booking.status_note, current_user, db
    )
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Provider rejected the booking request",
        booking.status_note,
        db,
        {"reason": booking.status_note},
    )
    create_notification(
        booking.customer_id,
        "Booking rejected",
        "A provider rejected your booking request",
        NotificationType.booking_rejected,
        NotificationRelatedType.booking,
        booking.id,
        db,
    )
    result = save_booking(booking, db)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    result["booking"] = format_booking_detail_response(booking, db)
    result["message"] = "Booking rejected successfully"

    return result


async def complete_provider_booking_action(
    booking_id: int,
    current_user: models.User,
    db: Session,
    proof_files: list[UploadFile] | None = None,
    final_quote_amount: float | None = None,
    final_quote_message: str | None = None,
    *,
    demo_proof: bool = False,
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == booking_id,
            models.Booking.provider_profile_id == provider_profile.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    ensure_booking_status(
        booking,
        [BookingStatus.service_paid, BookingStatus.accepted],
        "Only bookings with a paid service fee can be completed",
    )

    if not proof_files and not demo_proof:
        raise HTTPException(
            status_code=400,
            detail="Completion proof photo or video is required",
        )

    if final_quote_amount is not None and final_quote_amount <= 0:
        raise HTTPException(status_code=400, detail="Final quote amount must be positive")

    saved_file_urls = []
    proof_attachments = []
    try:
        if demo_proof:
            proof_attachments.append(record_preset_proof(booking.id, "completion_proof", current_user, db))
            db.flush()
        uploads = []
        for file in proof_files or []:
            if not file.filename:
                continue
            upload_result = await save_booking_attachment_upload(booking.id, file)
            saved_file_urls.append(upload_result["file_url"])
            uploads.append(upload_result)
        for upload_result in uploads:
            attachment = models.BookingAttachment(
                booking_id=booking.id,
                uploaded_by_user_id=current_user.id,
                purpose="completion_proof",
                original_file_name=upload_result["original_file_name"],
                file_name=upload_result["file_name"],
                file_url=upload_result["file_url"],
                content_type=upload_result["content_type"],
                size=upload_result["size"],
                created_at=utc_now(),
            )
            db.add(attachment)
            db.flush()
            proof_attachments.append(attachment)

        if not proof_attachments:
            raise HTTPException(
                status_code=400,
                detail="Completion proof photo or video is required",
            )

        proof_metadata = [
            {
                "id": attachment.id,
                "file_url": attachment.file_url,
                "content_type": attachment.content_type,
                "original_file_name": attachment.original_file_name,
            }
            for attachment in proof_attachments
        ]
    except Exception:
        db.rollback()
        for file_url in saved_file_urls:
            delete_local_upload(file_url)
        raise

    if final_quote_amount is not None:
        current_amount = Decimal(str(booking.quote_amount or 0)).quantize(Decimal("0.01"))
        new_amount = Decimal(str(final_quote_amount)).quantize(Decimal("0.01"))
        if new_amount != current_amount or final_quote_message is not None:
            latest_revision = (
                db.query(models.BookingQuoteRevision)
                .filter(models.BookingQuoteRevision.booking_id == booking.id)
                .order_by(models.BookingQuoteRevision.revision_number.desc())
                .first()
            )
            booking.quote_amount = new_amount
            booking.quote_message = final_quote_message
            db.add(
                models.BookingQuoteRevision(
                    booking_id=booking.id,
                    revision_number=(latest_revision.revision_number if latest_revision else 0) + 1,
                    quote_amount=new_amount,
                    quote_message=final_quote_message,
                    created_by_user_id=current_user.id,
                    created_at=utc_now(),
                )
            )

    old_status = booking.status
    booking.status = BookingStatus.awaiting_confirmation
    booking.status_note = "Provider marked service as complete"
    add_booking_status_history(
        booking, old_status, booking.status, booking.status_note, current_user, db
    )
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Provider marked the service as complete",
        booking.status_note,
        db,
        {
            "awaiting_customer_confirmation": True,
            "proof_attachment_count": len(proof_attachments),
            "proof_attachments": proof_metadata,
        },
    )
    create_notification(
        booking.customer_id,
        "Service marked complete",
        "A provider marked your booking as complete",
        NotificationType.booking_completed_by_provider,
        NotificationRelatedType.booking,
        booking.id,
        db,
    )
    result = save_booking(booking, db)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    result["booking"] = format_booking_detail_response(booking, db)
    result["message"] = "Booking is waiting for customer confirmation"

    return result
