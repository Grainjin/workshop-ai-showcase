"""Provider API.

Provider endpoints: profile, availability, portfolio, quotes, rejections, completion, refunds.
Booking actions delegate to `utils/provider_booking_actions.py` for consistent state flow.
"""

from datetime import date, datetime, time, timezone
from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session
from backend import models
from backend.auth import get_db, require_provider
from backend.core.clock import WORKSHOP_TIMEZONE, to_workshop_datetime
from backend.utils.booking import format_booking_detail_response
from backend.utils.availability import (
    delete_provider_availability_override,
    format_provider_availability_response,
    format_provider_availability_override_response,
    get_provider_availabilities,
    get_provider_availability_overrides_by_month,
    is_provider_open_now,
    replace_provider_availabilities,
    upsert_provider_availability_override,
)
from backend.utils.chat import (
    format_chat_room_response_with_unread,
)
from backend.utils.formatters import (
    format_provider_profile_response,
    format_provider_portfolio_response,
    format_user_response,
    tags_to_string,
)
from backend.utils.verification import apply_phone_number_change
from backend.utils.pagination import build_paginated_response, paginate_query
from backend.utils.payment import format_payment_response
from backend.utils.booking_quote_upload import QUOTE_UPLOAD_OPENAPI, parse_quote_request
from backend.utils.provider_booking_actions import (
    approve_provider_refund_request_action,
    complete_provider_booking_action,
    quote_provider_booking_action,
    start_provider_visit_action,
    submit_final_quote_action,
    reject_provider_booking_action,
    reject_provider_refund_request_action,
)
from backend.utils.provider import (
    add_provider_verification_history,
    get_provider_profile_for_user,
    require_provider_qualification_approved,
    require_provider_identity_approved,
)
from backend.utils.service_locations import (
    apply_profile_location,
    get_province_for_location,
    validate_profile_location,
)
from backend.utils.refund import (
    add_refund_request_status_history,
    format_refund_request_response,
)
from backend.utils.review import (
    format_review_detail_response,
    get_provider_rating_summary,
)
from backend.utils.router import ApiRouter
from backend.utils.demo_mode import reject_demo_restricted_action
from backend.utils.upload import (
    delete_local_upload,
    save_certificate_upload,
    save_portfolio_media_upload,
)
from backend.schemas import (
    ApiResponse,
    BookingDetailResponse,
    BookingNoteUpdate,
    BookingStatus,
    CertificateUploadBatchResponse,
    CertificateUploadResponse,
    PaginatedData,
    PaymentStatus,
    ProviderAvailabilityResponse,
    ProviderAvailabilityOverrideResponse,
    ProviderAvailabilityOverrideUpdate,
    ProviderAvailabilityUpdate,
    ProviderContactProfilePatch,
    ProviderContactProfileUpdate,
    ProviderCertificateFileInput,
    ProviderOperatingSettingsPatch,
    ProviderProfileCreate,
    ProviderPortfolioResponse,
    ProviderRefundRejectCreate,
    ProviderVerificationStatus,
    RefundRequestStatus,
)
from backend.utils.response import success_response
from backend.core.clock import utc_now

router = ApiRouter(tags=["Provider"])


def replace_provider_certificate_files(
    profile: models.ProviderProfile,
    certificate_files: list[ProviderCertificateFileInput],
    db: Session,
):
    db.query(models.ProviderCertificateFile).filter(
        models.ProviderCertificateFile.provider_profile_id == profile.id
    ).delete(synchronize_session=False)

    now = utc_now()
    for index, certificate_file in enumerate(certificate_files):
        db.add(
            models.ProviderCertificateFile(
                provider_profile_id=profile.id,
                file_url=certificate_file.file_url,
                original_file_name=certificate_file.original_file_name,
                content_type=certificate_file.content_type,
                media_type=certificate_file.media_type,
                sort_order=certificate_file.sort_order or index,
                created_at=now,
            )
        )


@router.get("/provider/dashboard")
def provider_dashboard(current_user: models.User = Depends(require_provider)):
    return success_response(
        {
            "message": "Welcome to provider dashboard",
            "user": format_user_response(current_user),
        }
    )


@router.post("/provider/profile")
def create_provider_profile(
    profile: ProviderProfileCreate,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "create_provider_profile")
    if current_user.identity_verification_status is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Provider profiles are created after qualification approval; "
                "use the identity and qualification verification endpoints"
            ),
        )
    existing_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.user_id == current_user.id)
        .first()
    )
    if existing_profile:
        raise HTTPException(status_code=400, detail="Provider profile already exists")
    new_profile = models.ProviderProfile(
        user_id=current_user.id,
        entity_type=profile.entity_type,
        business_name=profile.business_name,
        bio=profile.bio,
        phone_number=profile.phone_number,
        address=profile.address,
        service_province=profile.service_province,
        service_location_id=profile.service_location_id,
        latitude=profile.latitude,
        longitude=profile.longitude,
        tags=tags_to_string(profile.tags),
        certificate_name=profile.certificate_name,
        certificate_url=profile.certificate_url,
        hourly_rate=profile.hourly_rate,
        verification_status=ProviderVerificationStatus.pending,
        identity_verification_status=ProviderVerificationStatus.pending,
        qualification_verification_status=ProviderVerificationStatus.pending,
        verification_note=None,
        notes=profile.notes,
    )
    db.add(new_profile)
    apply_profile_location(db=db, profile=new_profile, location_id=profile.service_location_id)
    db.commit()
    db.refresh(new_profile)
    replace_provider_certificate_files(new_profile, profile.certificate_files, db)
    db.commit()
    db.refresh(new_profile)
    add_provider_verification_history(
        new_profile,
        "created",
        new_profile.verification_status,
        "Provider created profile and submitted certificate",
        current_user,
        db,
    )
    db.commit()
    return success_response(
        {
            "message": "Provider profile created successfully",
            "profile": format_provider_profile_response(new_profile, db),
        }
    )


@router.get("/provider/profile")
def get_provider_profile(
    current_user: models.User = Depends(require_provider), db: Session = Depends(get_db)
):
    profile = get_provider_profile_for_user(current_user.id, db)
    result = format_provider_profile_response(profile, db)
    result.update(get_provider_rating_summary(profile.id, db))
    result["is_open"] = is_provider_open_now(profile.id, db)
    return success_response(result)


@router.post(
    "/provider/certificates/upload",
    response_model=ApiResponse[CertificateUploadBatchResponse],
)
async def upload_provider_certificate(
    files: list[UploadFile] | None = File(default=None),
    file: UploadFile | None = File(default=None),
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "upload_provider_certificate")
    if current_user.identity_verification_status is not None:
        raise HTTPException(
            status_code=409,
            detail="Use the qualification verification upload endpoint",
        )
    require_provider_identity_approved(get_provider_profile_for_user(current_user.id, db))
    upload_files = list(files or [])
    if file is not None:
        upload_files.append(file)
    if not upload_files:
        raise HTTPException(status_code=400, detail="At least one certificate file is required")

    upload_results = [
        await save_certificate_upload(certificate_file) for certificate_file in upload_files
    ]
    return success_response(
        {"files": upload_results},
        message="Certificate files uploaded successfully",
    )


@router.put("/provider/profile")
def update_provider_profile(
    profile_data: ProviderProfileCreate,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "update_provider_profile")
    if current_user.identity_verification_status is not None:
        raise HTTPException(
            status_code=409,
            detail="Full provider profile replacement is not available in the new verification flow",
        )
    profile = get_provider_profile_for_user(current_user.id, db)
    old_identity_status = profile.identity_verification_status
    old_qualification_status = profile.qualification_verification_status
    identity_changed = any(
        (
            profile.entity_type != profile_data.entity_type,
            profile.business_name != profile_data.business_name,
        )
    )
    next_tags = tags_to_string(profile_data.tags)
    apply_phone_number_change(current_user, profile.phone_number, profile_data.phone_number)
    profile.business_name = profile_data.business_name
    profile.bio = profile_data.bio
    profile.phone_number = profile_data.phone_number
    profile.address = profile_data.address
    profile.service_province = profile_data.service_province
    profile.service_location_id = profile_data.service_location_id
    profile.latitude = profile_data.latitude
    profile.longitude = profile_data.longitude
    profile.tags = next_tags
    profile.certificate_name = profile_data.certificate_name
    profile.certificate_url = profile_data.certificate_url
    profile.hourly_rate = profile_data.hourly_rate
    profile.notes = profile_data.notes
    apply_profile_location(
        db=db,
        profile=profile,
        location_id=profile_data.service_location_id,
    )
    if old_identity_status != ProviderVerificationStatus.approved or identity_changed:
        profile.identity_verification_status = ProviderVerificationStatus.pending
        history_step = "identity"
        history_old_status = old_identity_status
    else:
        history_step = "qualification"
        history_old_status = old_qualification_status
    profile.qualification_verification_status = ProviderVerificationStatus.pending
    profile.verification_status = ProviderVerificationStatus.pending
    profile.entity_type = profile_data.entity_type
    profile.verification_note = None
    add_provider_verification_history(
        profile,
        history_old_status,
        ProviderVerificationStatus.pending,
        "Provider updated profile and submitted for verification",
        current_user,
        db,
        verification_step=history_step,
    )

    if "certificate_files" in profile_data.model_fields_set:
        replace_provider_certificate_files(profile, profile_data.certificate_files, db)
    db.commit()
    db.refresh(profile)
    return success_response(
        {
            "message": "Provider profile updated and submitted for verification",
            "profile": format_provider_profile_response(profile, db),
        }
    )


@router.put("/provider/profile/contact")
def update_provider_contact_profile(
    profile_data: ProviderContactProfileUpdate,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    if current_user.identity_verification_status is not None:
        raise HTTPException(
            status_code=409,
            detail="Use the operating settings endpoint after qualification approval",
        )
    profile = get_provider_profile_for_user(current_user.id, db)
    apply_phone_number_change(current_user, profile.phone_number, profile_data.phone_number)
    profile.phone_number = profile_data.phone_number
    profile.address = profile_data.address
    profile.service_province = profile_data.service_province
    profile.service_location_id = profile_data.service_location_id
    profile.notes = profile_data.notes
    apply_profile_location(
        db=db,
        profile=profile,
        location_id=profile_data.service_location_id,
    )
    db.commit()
    db.refresh(profile)
    return success_response(
        {
            "message": "Provider contact profile updated successfully",
            "profile": format_provider_profile_response(profile),
        }
    )


@router.patch("/provider/profile/contact")
def patch_provider_contact_profile(
    profile_data: ProviderContactProfilePatch,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    if current_user.identity_verification_status is not None:
        raise HTTPException(
            status_code=409,
            detail="Use the operating settings endpoint after qualification approval",
        )
    profile = get_provider_profile_for_user(current_user.id, db)

    previous_phone = profile.phone_number
    updates = profile_data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if field != "service_location_id":
            setattr(profile, field, value)
    if "service_location_id" in updates:
        profile.service_location_id = updates["service_location_id"]
        if profile.service_location_id is not None:
            apply_profile_location(
                db=db,
                profile=profile,
                location_id=profile.service_location_id,
            )
    elif "service_province" in updates:
        profile.service_location_id = None
    apply_phone_number_change(current_user, previous_phone, profile.phone_number)

    db.commit()
    db.refresh(profile)
    return success_response(
        {
            "message": "Provider contact profile updated successfully",
            "profile": format_provider_profile_response(profile),
        }
    )


@router.patch("/provider/profile/operating-settings")
def patch_provider_operating_settings(
    settings: ProviderOperatingSettingsPatch,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    if current_user.identity_verification_status is not None:
        raise HTTPException(
            status_code=409,
            detail="Use /provider/operating-settings for the new verification flow",
        )
    profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(profile)
    updates = settings.model_dump(exclude_unset=True)
    location = None
    location_province = None
    if "service_location_id" in updates:
        location = validate_profile_location(db, updates["service_location_id"])
        location_province = get_province_for_location(db, location)

    if "hourly_rate" in updates:
        profile.hourly_rate = updates["hourly_rate"]
    if location is not None:
        profile.service_location_id = location.id
        profile.service_province = location_province.name

    db.commit()
    db.refresh(profile)
    return success_response(
        {
            "message": "Provider operating settings updated successfully",
            "profile": format_provider_profile_response(profile, db),
        }
    )


@router.get("/provider/availability")
def get_provider_availability(
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    availabilities = get_provider_availabilities(provider_profile.id, db)
    return success_response(
        {
            "availabilities": [
                format_provider_availability_response(availability)
                for availability in availabilities
            ]
        }
    )


@router.put("/provider/availability")
def update_provider_availability(
    availability_data: ProviderAvailabilityUpdate,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    availabilities = replace_provider_availabilities(
        provider_profile.id,
        availability_data.availabilities,
        db,
    )
    return success_response(
        {
            "message": "Provider availability updated successfully",
            "availabilities": [
                format_provider_availability_response(availability)
                for availability in availabilities
            ],
        }
    )


@router.get(
    "/provider/availability/overrides",
    response_model=ApiResponse[list[ProviderAvailabilityOverrideResponse]],
)
def get_provider_availability_overrides(
    month: str,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    requested_month = parse_availability_month(month)
    current_month = to_workshop_datetime(utc_now()).date().replace(day=1)
    if requested_month < current_month:
        raise HTTPException(
            status_code=400,
            detail="Cannot view availability before the current month",
        )

    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    availability_overrides = get_provider_availability_overrides_by_month(
        provider_profile.id,
        month,
        db,
    )

    return success_response(
        [
            format_provider_availability_override_response(availability_override)
            for availability_override in availability_overrides
        ]
    )


@router.put(
    "/provider/availability/overrides/{override_date}",
    response_model=ApiResponse[ProviderAvailabilityOverrideResponse],
)
def update_provider_availability_override(
    override_date: date,
    override_data: ProviderAvailabilityOverrideUpdate,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    validate_availability_override_date(override_date)

    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    availability_override = upsert_provider_availability_override(
        provider_profile.id,
        override_date,
        override_data,
        db,
    )

    return success_response(format_provider_availability_override_response(availability_override))


@router.delete("/provider/availability/overrides/{override_date}")
def remove_provider_availability_override(
    override_date: date,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    validate_availability_override_date(override_date)

    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    delete_provider_availability_override(provider_profile.id, override_date, db)

    return success_response({"message": "Availability override removed successfully"})


def parse_availability_month(month: str):
    try:
        return date.fromisoformat(f"{month}-01")
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Month must use YYYY-MM format",
        ) from exc


def validate_availability_override_date(override_date: date):
    if override_date < to_workshop_datetime(utc_now()).date():
        raise HTTPException(
            status_code=400,
            detail="Cannot adjust availability before today",
        )


def add_one_month(month_date: date):
    if month_date.month == 12:
        return date(month_date.year + 1, 1, 1)

    return date(month_date.year, month_date.month + 1, 1)


@router.post(
    "/provider/portfolio",
    response_model=ApiResponse[ProviderPortfolioResponse],
)
async def create_provider_portfolio(
    title: str = Form(...),
    description: str | None = Form(default=None),
    media_files: list[UploadFile] = File(...),
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "create_provider_portfolio")
    clean_title = title.strip()

    if not clean_title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    if not media_files:
        raise HTTPException(
            status_code=400,
            detail="Please upload at least one portfolio media file",
        )

    clean_description = description.strip() if description else None
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    uploaded_media = []

    for file in media_files:
        uploaded_media.append(await save_portfolio_media_upload(file))

    cover_media = uploaded_media[0]
    portfolio = models.ProviderPortfolio(
        provider_profile_id=provider_profile.id,
        title=clean_title,
        description=clean_description,
        image_url=cover_media["file_url"],
        original_file_name=cover_media["original_file_name"],
        content_type=cover_media["content_type"],
        media_type=cover_media["media_type"],
        verification_status=ProviderVerificationStatus.pending,
        verification_note=None,
        created_at=utc_now(),
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)

    for index, upload_result in enumerate(uploaded_media):
        db.add(
            models.ProviderPortfolioMedia(
                portfolio_id=portfolio.id,
                file_url=upload_result["file_url"],
                original_file_name=upload_result["original_file_name"],
                content_type=upload_result["content_type"],
                media_type=upload_result["media_type"],
                sort_order=index,
                created_at=portfolio.created_at,
            )
        )

    db.commit()
    db.refresh(portfolio)
    return success_response(
        format_provider_portfolio_response(portfolio, db),
        message="Portfolio item created successfully",
    )


@router.get(
    "/provider/portfolio/{portfolio_id}",
    response_model=ApiResponse[ProviderPortfolioResponse],
)
def get_provider_portfolio_item(
    portfolio_id: int,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    portfolio = (
        db.query(models.ProviderPortfolio)
        .filter(
            models.ProviderPortfolio.id == portfolio_id,
            models.ProviderPortfolio.provider_profile_id == provider_profile.id,
        )
        .first()
    )

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio item not found")

    return success_response(format_provider_portfolio_response(portfolio, db))


@router.get(
    "/provider/portfolio",
    response_model=ApiResponse[PaginatedData[ProviderPortfolioResponse]],
)
def get_provider_portfolio(
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    query = (
        db.query(models.ProviderPortfolio)
        .filter(models.ProviderPortfolio.provider_profile_id == provider_profile.id)
        .order_by(models.ProviderPortfolio.created_at.desc())
    )
    portfolios, total, page, page_size = paginate_query(query, page, page_size)
    result = [format_provider_portfolio_response(portfolio, db) for portfolio in portfolios]
    return build_paginated_response(result, total, page, page_size)


@router.get("/provider/reviews")
def get_provider_reviews(
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    query = (
        db.query(models.Review)
        .filter(
            models.Review.provider_profile_id == provider_profile.id,
            models.Review.is_visible == 1,
        )
        .order_by(models.Review.created_at.desc())
    )
    reviews, total, page, page_size = paginate_query(query, page, page_size)
    result = [format_review_detail_response(review, db) for review in reviews]
    return build_paginated_response(result, total, page, page_size)


@router.delete("/provider/portfolio/{portfolio_id}", response_model=ApiResponse[None])
def delete_provider_portfolio(
    portfolio_id: int,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    portfolio = (
        db.query(models.ProviderPortfolio)
        .filter(
            models.ProviderPortfolio.id == portfolio_id,
            models.ProviderPortfolio.provider_profile_id == provider_profile.id,
        )
        .first()
    )

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio item not found")

    media_items = (
        db.query(models.ProviderPortfolioMedia)
        .filter(models.ProviderPortfolioMedia.portfolio_id == portfolio.id)
        .all()
    )
    for media in media_items:
        delete_local_upload(media.file_url)
        db.delete(media)

    if not media_items:
        delete_local_upload(portfolio.image_url)

    db.delete(portfolio)
    db.commit()
    return success_response(message="Portfolio item deleted successfully")


@router.get("/provider/chats")
def get_provider_chats(
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    query = (
        db.query(models.ChatRoom)
        .filter(models.ChatRoom.provider_profile_id == provider_profile.id)
        .order_by(models.ChatRoom.last_message_at.desc().nullslast())
    )
    chat_rooms, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for chat_room in chat_rooms:
        result.append(format_chat_room_response_with_unread(chat_room, db, current_user))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.get("/provider/bookings")
def get_provider_bookings(
    status: BookingStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    query = db.query(models.Booking).filter(
        models.Booking.provider_profile_id == provider_profile.id
    )
    if status:
        query = query.filter(models.Booking.status == status)
    query = query.order_by(models.Booking.booking_at.desc())
    bookings, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for booking in bookings:
        result.append(format_booking_detail_response(booking, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.get(
    "/provider/bookings/schedule",
    response_model=ApiResponse[list[BookingDetailResponse]],
)
def get_provider_schedule_bookings(
    month: str,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    requested_month = parse_availability_month(month)
    current_month = to_workshop_datetime(utc_now()).date().replace(day=1)
    if requested_month < current_month:
        raise HTTPException(
            status_code=400,
            detail="Cannot view schedule bookings before the current month",
        )

    next_month = add_one_month(requested_month)
    month_start = datetime.combine(requested_month, time.min, tzinfo=WORKSHOP_TIMEZONE).astimezone(
        timezone.utc
    )
    month_end = datetime.combine(next_month, time.min, tzinfo=WORKSHOP_TIMEZONE).astimezone(
        timezone.utc
    )
    bookings = (
        db.query(models.Booking)
        .filter(
            models.Booking.provider_profile_id == provider_profile.id,
            models.Booking.status.in_(
                [
                    BookingStatus.accepted.value,
                    BookingStatus.awaiting_confirmation.value,
                ]
            ),
            models.Booking.scheduled_start_time < month_end,
            models.Booking.scheduled_end_time > month_start,
        )
        .order_by(models.Booking.scheduled_start_time.asc())
        .all()
    )

    return success_response([format_booking_detail_response(booking, db) for booking in bookings])


@router.get("/provider/payments")
def get_provider_payments(
    status: PaymentStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    query = db.query(models.Payment).filter(
        models.Payment.provider_profile_id == provider_profile.id
    )
    if status:
        query = query.filter(models.Payment.status == status)
    query = query.order_by(models.Payment.created_at.desc())
    payments, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for payment in payments:
        result.append(format_payment_response(payment, db, include_settlement=True))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.get("/provider/refund-requests")
def get_provider_refund_requests(
    status: RefundRequestStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(provider_profile)
    query = db.query(models.RefundRequest).filter(
        models.RefundRequest.provider_profile_id == provider_profile.id
    )
    if status:
        query = query.filter(models.RefundRequest.status == status)
    query = query.order_by(models.RefundRequest.created_at.desc())
    refund_requests, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for refund_request in refund_requests:
        result.append(format_refund_request_response(refund_request, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.put("/provider/refund-requests/{refund_request_id}/approve")
async def approve_refund_request(
    refund_request_id: int,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    require_provider_qualification_approved(get_provider_profile_for_user(current_user.id, db))
    return success_response(
        await approve_provider_refund_request_action(
            refund_request_id,
            current_user,
            db,
        )
    )


@router.put("/provider/refund-requests/{refund_request_id}/reject")
async def reject_refund_request(
    refund_request_id: int,
    reject_data: ProviderRefundRejectCreate,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    require_provider_qualification_approved(get_provider_profile_for_user(current_user.id, db))
    return success_response(
        await reject_provider_refund_request_action(
            refund_request_id,
            reject_data,
            current_user,
            db,
        )
    )


@router.put(
    "/provider/bookings/{booking_id}/quote",
    openapi_extra=QUOTE_UPLOAD_OPENAPI,
)
async def quote_booking(
    booking_id: int,
    request: Request,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    require_provider_qualification_approved(get_provider_profile_for_user(current_user.id, db))
    quote_data, quote_files = await parse_quote_request(request)
    if quote_files:
        reject_demo_restricted_action(current_user, "quote_upload")
    return success_response(
        await quote_provider_booking_action(
            booking_id,
            quote_data,
            current_user,
            db,
            quote_files,
        )
    )


@router.put("/provider/bookings/{booking_id}/reject")
async def reject_booking(
    booking_id: int,
    note_data: BookingNoteUpdate,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    require_provider_qualification_approved(get_provider_profile_for_user(current_user.id, db))
    return success_response(
        await reject_provider_booking_action(
            booking_id,
            note_data,
            current_user,
            db,
        )
    )


@router.put("/provider/bookings/{booking_id}/complete")
async def complete_booking(
    booking_id: int,
    proof_files: list[UploadFile] = File(...),
    final_quote_amount: float | None = Form(default=None),
    final_quote_message: str | None = Form(default=None),
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "complete_booking")
    require_provider_qualification_approved(get_provider_profile_for_user(current_user.id, db))
    return success_response(
        await complete_provider_booking_action(
            booking_id,
            current_user,
            db,
            proof_files,
            final_quote_amount,
            final_quote_message,
        )
    )


@router.put("/provider/bookings/{booking_id}/start-visit")
async def start_visit(
    booking_id: int,
    proof_files: list[UploadFile] = File(...),
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "start_visit")
    require_provider_qualification_approved(get_provider_profile_for_user(current_user.id, db))
    return success_response(
        await start_provider_visit_action(booking_id, current_user, db, proof_files)
    )


@router.put(
    "/provider/bookings/{booking_id}/final-quote",
    openapi_extra=QUOTE_UPLOAD_OPENAPI,
)
async def submit_final_quote(
    booking_id: int,
    request: Request,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    require_provider_qualification_approved(get_provider_profile_for_user(current_user.id, db))
    quote_data, quote_files = await parse_quote_request(request)
    if quote_files:
        reject_demo_restricted_action(current_user, "quote_upload")
    return success_response(
        await submit_final_quote_action(
            booking_id,
            quote_data,
            current_user,
            db,
            quote_files,
        )
    )
