from backend.constants import ALLOWED_PROVIDER_TAGS
from backend.core.clock import to_workshop_datetime
from backend.services.redis_service import is_user_online


def format_user_response(user):
    return {
        "id": user.id,
        "name": user.name,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "tos_accepted_at": user.tos_accepted_at,
        "email": user.email,
        "role": user.role,
        "avatar_url": user.avatar_url,
        "is_active": user.is_active,
        "is_banned": user.is_banned,
        "email_verified": user.email_verified_at is not None,
        "phone_verified": user.phone_verified_at is not None,
        "identity_verification_status": getattr(
            user, "identity_verification_status", None
        ),
        "qualification_verification_status": getattr(
            user, "qualification_verification_status", None
        ),
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
    }


def normalize_provider_tags(tags: list[str]):
    normalized_tags = []

    for tag in tags:
        clean_tag = tag.strip()

        if (
            clean_tag
            and clean_tag in ALLOWED_PROVIDER_TAGS
            and clean_tag not in normalized_tags
        ):
            normalized_tags.append(clean_tag)

    return normalized_tags


def tags_to_string(tags: list[str]):
    return ",".join(normalize_provider_tags(tags))


def tags_to_list(tags: str):
    if not tags:
        return []

    return normalize_provider_tags(tags.split(","))


def format_provider_certificate_response(certificate):
    return {
        "id": certificate.id,
        "provider_profile_id": certificate.provider_profile_id,
        "file_url": certificate.file_url,
        "original_file_name": certificate.original_file_name,
        "content_type": certificate.content_type,
        "media_type": certificate.media_type,
        "sort_order": certificate.sort_order,
        "created_at": certificate.created_at,
    }


def format_provider_profile_response(
    profile, db=None, *, include_verification_documents: bool = True
):
    certificate_files = []

    if db is not None and include_verification_documents:
        from backend import models

        certificate_files = (
            db.query(models.ProviderCertificateFile)
            .filter(
                models.ProviderCertificateFile.provider_profile_id == profile.id
            )
            .order_by(models.ProviderCertificateFile.sort_order.asc())
            .all()
        )

    formatted_certificate_files = [
        format_provider_certificate_response(certificate)
        for certificate in certificate_files
    ]
    if (
        include_verification_documents
        and not formatted_certificate_files
        and profile.certificate_url
    ):
        formatted_certificate_files = [
            {
                "id": 0,
                "provider_profile_id": profile.id,
                "file_url": profile.certificate_url,
                "original_file_name": profile.certificate_name,
                "content_type": "application/octet-stream",
                "media_type": "document",
                "sort_order": 0,
                "created_at": "",
            }
        ]

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "business_name": profile.business_name,
        "bio": profile.bio,
        "phone_number": profile.phone_number,
        "address": profile.address,
        "service_province": profile.service_province,
        "service_location_id": profile.service_location_id,
        "latitude": profile.latitude,
        "longitude": profile.longitude,
        "business_place_id": getattr(profile, "business_place_id", None),
        "tags": tags_to_list(profile.tags),
        "certificate_name": (
            profile.certificate_name if include_verification_documents else ""
        ),
        "certificate_url": (
            profile.certificate_url if include_verification_documents else ""
        ),
        "certificate_files": formatted_certificate_files,
        "hourly_rate": profile.hourly_rate,
        "verification_status": profile.verification_status,
        "entity_type": getattr(profile, "entity_type", "personal"),
        "identity_verification_status": getattr(
            profile, "identity_verification_status", profile.verification_status
        ),
        "qualification_verification_status": getattr(
            profile, "qualification_verification_status", profile.verification_status
        ),
        "verification_note": profile.verification_note,
        "notes": profile.notes,
        "is_online": is_user_online(profile.user_id),
    }


def format_customer_profile_response(profile):
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "phone_number": profile.phone_number,
        "address": profile.address,
        "service_province": profile.service_province,
        "service_location_id": profile.service_location_id,
        "latitude": profile.latitude,
        "longitude": profile.longitude,
        "current_address": profile.current_address,
        "current_latitude": profile.current_latitude,
        "current_longitude": profile.current_longitude,
        "default_service_address": profile.default_service_address,
        "default_service_latitude": profile.default_service_latitude,
        "default_service_longitude": profile.default_service_longitude,
        "notes": profile.notes,
    }


def format_provider_portfolio_media_response(media):
    return {
        "id": media.id,
        "portfolio_id": media.portfolio_id,
        "file_url": media.file_url,
        "original_file_name": media.original_file_name,
        "content_type": media.content_type,
        "media_type": media.media_type,
        "sort_order": media.sort_order,
        "created_at": media.created_at,
    }


def format_provider_portfolio_response(portfolio, db=None):
    media_items = []

    if db is not None:
        from backend import models

        media_items = (
            db.query(models.ProviderPortfolioMedia)
            .filter(models.ProviderPortfolioMedia.portfolio_id == portfolio.id)
            .order_by(models.ProviderPortfolioMedia.sort_order.asc())
            .all()
        )

    if not media_items and portfolio.image_url:
        media_items = [
            type(
                "PortfolioMediaFallback",
                (),
                {
                    "id": 0,
                    "portfolio_id": portfolio.id,
                    "file_url": portfolio.image_url,
                    "original_file_name": portfolio.original_file_name,
                    "content_type": portfolio.content_type,
                    "media_type": portfolio.media_type,
                    "sort_order": 0,
                    "created_at": portfolio.created_at,
                },
            )()
        ]

    return {
        "id": portfolio.id,
        "provider_profile_id": portfolio.provider_profile_id,
        "title": portfolio.title,
        "description": portfolio.description,
        "image_url": portfolio.image_url,
        "original_file_name": portfolio.original_file_name,
        "content_type": portfolio.content_type,
        "media_type": portfolio.media_type,
        "media_items": [
            format_provider_portfolio_media_response(media) for media in media_items
        ],
        "verification_status": portfolio.verification_status,
        "verification_note": portfolio.verification_note,
        "created_at": portfolio.created_at,
    }


def format_booking_attachment_response(attachment):
    return {
        "id": attachment.id,
        "booking_id": attachment.booking_id,
        "uploaded_by_user_id": attachment.uploaded_by_user_id,
        "quote_revision_id": attachment.quote_revision_id,
        "purpose": attachment.purpose,
        "original_file_name": attachment.original_file_name,
        "file_name": attachment.file_name,
        "file_url": attachment.file_url,
        "content_type": attachment.content_type,
        "size": attachment.size,
        "created_at": attachment.created_at,
    }


def format_booking_response(booking):
    return {
        "id": booking.id,
        "customer_id": booking.customer_id,
        "provider_profile_id": booking.provider_profile_id,
        "chat_room_id": booking.chat_room_id,
        "title": booking.title,
        "service_category": booking.service_category,
        "service_description": booking.service_description,
        "service_address": booking.service_address,
        "service_latitude": booking.service_latitude,
        "service_longitude": booking.service_longitude,
        "customer_current_address": booking.customer_current_address,
        "customer_current_latitude": booking.customer_current_latitude,
        "customer_current_longitude": booking.customer_current_longitude,
        "booking_at": booking.booking_at,
        "scheduled_start_time": to_workshop_datetime(booking.scheduled_start_time),
        "scheduled_end_time": to_workshop_datetime(booking.scheduled_end_time),
        "completed_at": booking.completed_at,
        "total_amount": booking.total_amount,
        "quote_amount": booking.quote_amount,
        "quote_message": booking.quote_message,
        "expected_service_amount": booking.expected_service_amount,
        "visit_fee_amount": booking.visit_fee_amount,
        "final_quote_amount": booking.final_quote_amount,
        "final_quote_message": booking.final_quote_message,
        "quoted_at": booking.quoted_at,
        "arrival_started_at": booking.arrival_started_at,
        "final_quote_declined_at": booking.final_quote_declined_at,
        "final_quote_decline_reason": booking.final_quote_decline_reason,
        "final_quote_confirmed_at": booking.final_quote_confirmed_at,
        "closed_reason": booking.closed_reason,
        "status": booking.status,
        "status_note": booking.status_note,
        "booking_notice": (
            "This booking is temporarily unable to continue."
            if booking.onboarding_paused
            else None
        ),
    }


def format_review_response(review):
    return {
        "id": review.id,
        "booking_id": review.booking_id,
        "customer_id": review.customer_id,
        "provider_profile_id": review.provider_profile_id,
        "rating": review.rating,
        "comment": review.comment,
        "created_at": review.created_at,
        "is_visible": bool(review.is_visible),
        "embedding_status": review.embedding_status,
        "embedding_error": review.embedding_error,
        "embedding_synced_at": review.embedding_synced_at,
    }
