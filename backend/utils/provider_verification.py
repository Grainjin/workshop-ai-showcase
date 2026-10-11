from sqlalchemy.orm import Session

from backend import models
from backend.utils.service_locations import format_service_area


def latest_identity_application(user_id: int, db: Session):
    return (
        db.query(models.IdentityVerificationApplication)
        .filter(models.IdentityVerificationApplication.user_id == user_id)
        .order_by(models.IdentityVerificationApplication.id.desc())
        .first()
    )


def latest_qualification_application(user_id: int, db: Session):
    return (
        db.query(models.QualificationVerificationApplication)
        .filter(models.QualificationVerificationApplication.user_id == user_id)
        .order_by(models.QualificationVerificationApplication.id.desc())
        .first()
    )


def format_identity_application(application, db: Session, *, include_files: bool = True):
    result = {
        "id": application.id,
        "user_id": application.user_id,
        "submitted_first_name": application.submitted_first_name,
        "submitted_last_name": application.submitted_last_name,
        "date_of_birth": application.date_of_birth,
        "document_type": application.document_type,
        "status": application.status,
        "review_note": application.review_note,
        "reviewed_by_user_id": application.reviewed_by_user_id,
        "submitted_at": application.submitted_at,
        "reviewed_at": application.reviewed_at,
    }
    if include_files:
        files = (
            db.query(models.IdentityVerificationFile)
            .filter(models.IdentityVerificationFile.application_id == application.id)
            .order_by(models.IdentityVerificationFile.sort_order.asc())
            .all()
        )
        result["document_files"] = [
            {
                "id": item.id,
                "file_url": item.file_url,
                "original_file_name": item.original_file_name,
                "content_type": item.content_type,
                "sort_order": item.sort_order,
            }
            for item in files
        ]
    return result


def format_qualification_application(application, db: Session, *, include_files: bool = True):
    services = (
        db.query(models.QualificationVerificationService)
        .filter(models.QualificationVerificationService.application_id == application.id)
        .order_by(models.QualificationVerificationService.service_category.asc())
        .all()
    )
    area_rows = (
        db.query(models.QualificationVerificationServiceArea, models.ServiceLocation)
        .join(
            models.ServiceLocation,
            models.ServiceLocation.id
            == models.QualificationVerificationServiceArea.service_location_id,
        )
        .filter(
            models.QualificationVerificationServiceArea.application_id == application.id
        )
        .order_by(models.QualificationVerificationServiceArea.id.asc())
        .all()
    )
    result = {
        "id": application.id,
        "user_id": application.user_id,
        "entity_type": application.entity_type,
        "legal_name": application.legal_name,
        "unique_enterprise_id": application.unique_enterprise_id,
        "display_name": application.display_name,
        "description": application.description,
        "contact_phone": application.contact_phone,
        "business_address": application.business_address,
        "business_place_id": application.business_place_id,
        "business_latitude": application.business_latitude,
        "business_longitude": application.business_longitude,
        "service_categories": [item.service_category for item in services],
        "service_location_ids": [row.service_location_id for row, _ in area_rows],
        "service_areas": [
            format_service_area(db, location) for _, location in area_rows
        ],
        "status": application.status,
        "review_note": application.review_note,
        "reviewed_by_user_id": application.reviewed_by_user_id,
        "submitted_at": application.submitted_at,
        "reviewed_at": application.reviewed_at,
    }
    if include_files:
        files = (
            db.query(models.QualificationVerificationFile)
            .filter(models.QualificationVerificationFile.application_id == application.id)
            .order_by(models.QualificationVerificationFile.sort_order.asc())
            .all()
        )
        result["qualification_files"] = [
            {
                "id": item.id,
                "file_url": item.file_url,
                "original_file_name": item.original_file_name,
                "content_type": item.content_type,
                "sort_order": item.sort_order,
            }
            for item in files
        ]
    return result


def provider_verification_status(user: models.User):
    return {
        "identity_status": user.identity_verification_status or "not_submitted",
        "qualification_status": user.qualification_verification_status or "locked",
    }
