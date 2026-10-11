from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_db, require_admin
from backend.core.clock import utc_now
from backend.schemas.provider_verification import VerificationDecision
from backend.utils.formatters import tags_to_string
from backend.utils.provider_verification import (
    format_identity_application,
    format_qualification_application,
)
from backend.utils.response import success_response
from backend.utils.router import ApiRouter
from backend.utils.demo_mode import reject_demo_restricted_action


router = ApiRouter(tags=["Admin Verification"])


def _identity_application(application_id: int, db: Session):
    application = (
        db.query(models.IdentityVerificationApplication)
        .filter(models.IdentityVerificationApplication.id == application_id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Identity verification not found")
    return application


def _qualification_application(application_id: int, db: Session):
    application = (
        db.query(models.QualificationVerificationApplication)
        .filter(models.QualificationVerificationApplication.id == application_id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Qualification verification not found")
    return application


@router.get("/admin/identity-verifications")
def list_identity_verifications(
    status: str | None = None,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.IdentityVerificationApplication)
    if status:
        query = query.filter(models.IdentityVerificationApplication.status == status)
    applications = query.order_by(models.IdentityVerificationApplication.id.desc()).all()
    return success_response(
        [format_identity_application(application, db) for application in applications]
    )


@router.get("/admin/identity-verifications/{application_id}")
def get_identity_verification(
    application_id: int,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return success_response(
        format_identity_application(_identity_application(application_id, db), db)
    )


@router.put("/admin/identity-verifications/{application_id}/decision")
def decide_identity_verification(
    application_id: int,
    decision: VerificationDecision,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "decide_identity_verification")
    application = _identity_application(application_id, db)
    if application.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending applications can be reviewed")
    provider = db.query(models.User).filter(models.User.id == application.user_id).first()
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider account not found")
    application.status = decision.status
    application.review_note = decision.review_note
    application.reviewed_by_user_id = current_user.id
    application.reviewed_at = utc_now()
    provider.identity_verification_status = decision.status
    profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.user_id == provider.id)
        .first()
    )
    if profile is not None:
        profile.identity_verification_status = decision.status
        profile.verification_status = (
            "approved"
            if decision.status == "approved"
            and profile.qualification_verification_status == "approved"
            else decision.status
        )
    if provider.qualification_verification_status == "locked":
        provider.qualification_verification_status = "not_submitted"
    db.commit()
    db.refresh(application)
    return success_response(
        format_identity_application(application, db),
        message=f"Identity verification {decision.status}",
    )


@router.get("/admin/qualification-verifications")
def list_qualification_verifications(
    status: str | None = None,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.QualificationVerificationApplication)
    if status:
        query = query.filter(models.QualificationVerificationApplication.status == status)
    applications = query.order_by(models.QualificationVerificationApplication.id.desc()).all()
    return success_response(
        [format_qualification_application(application, db) for application in applications]
    )


@router.get("/admin/qualification-verifications/{application_id}")
def get_qualification_verification(
    application_id: int,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return success_response(
        format_qualification_application(_qualification_application(application_id, db), db)
    )


def _approve_qualification(application, provider, db: Session):
    services = (
        db.query(models.QualificationVerificationService)
        .filter(models.QualificationVerificationService.application_id == application.id)
        .all()
    )
    service_areas = (
        db.query(models.QualificationVerificationServiceArea)
        .filter(
            models.QualificationVerificationServiceArea.application_id == application.id
        )
        .order_by(models.QualificationVerificationServiceArea.id.asc())
        .all()
    )
    if not service_areas:
        raise HTTPException(
            status_code=409,
            detail=(
                "This application has no service areas. Reject it and ask the provider "
                "to submit a new application."
            ),
        )
    files = (
        db.query(models.QualificationVerificationFile)
        .filter(models.QualificationVerificationFile.application_id == application.id)
        .order_by(models.QualificationVerificationFile.sort_order.asc())
        .all()
    )
    profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.user_id == provider.id)
        .first()
    )
    first_file = files[0]
    if profile is None:
        profile = models.ProviderProfile(
            user_id=provider.id,
            business_name=application.display_name,
            bio=application.description,
            phone_number=application.contact_phone,
            address=application.business_address,
            service_province="",
            service_location_id=None,
            latitude=application.business_latitude,
            longitude=application.business_longitude,
            tags=tags_to_string([item.service_category for item in services]),
            certificate_name=first_file.original_file_name,
            certificate_url=first_file.file_url,
            hourly_rate=1,
            verification_status="approved",
            identity_verification_status="approved",
            qualification_verification_status="approved",
            entity_type=application.entity_type,
            verification_note=None,
        )
        db.add(profile)
        db.flush()
    else:
        profile.business_name = application.display_name
        profile.bio = application.description
        profile.phone_number = application.contact_phone
        profile.address = application.business_address
        profile.latitude = application.business_latitude
        profile.longitude = application.business_longitude
        profile.tags = tags_to_string([item.service_category for item in services])
        profile.certificate_name = first_file.original_file_name
        profile.certificate_url = first_file.file_url
        profile.verification_status = (
            "approved"
            if provider.identity_verification_status == "approved"
            else "pending"
        )
        profile.identity_verification_status = (
            provider.identity_verification_status or "not_submitted"
        )
        profile.qualification_verification_status = "approved"
        profile.entity_type = application.entity_type
    profile.business_place_id = application.business_place_id
    profile.unique_enterprise_id = application.unique_enterprise_id
    profile.qualification_application_id = application.id
    db.query(models.ProviderApprovedService).filter(
        models.ProviderApprovedService.provider_profile_id == profile.id
    ).delete(synchronize_session=False)
    for service in services:
        db.add(
            models.ProviderApprovedService(
                provider_profile_id=profile.id,
                service_category=service.service_category,
                is_enabled=True,
            )
        )
    db.query(models.ProviderServiceArea).filter(
        models.ProviderServiceArea.provider_profile_id == profile.id
    ).delete(synchronize_session=False)
    for area in service_areas:
        db.add(
            models.ProviderServiceArea(
                provider_profile_id=profile.id,
                service_location_id=area.service_location_id,
            )
        )
    db.query(models.ProviderCertificateFile).filter(
        models.ProviderCertificateFile.provider_profile_id == profile.id
    ).delete(synchronize_session=False)
    for file in files:
        db.add(
            models.ProviderCertificateFile(
                provider_profile_id=profile.id,
                file_url=file.file_url,
                original_file_name=file.original_file_name,
                content_type=file.content_type,
                media_type=("document" if file.content_type == "application/pdf" else "image"),
                sort_order=file.sort_order,
            )
        )
    return profile


@router.put("/admin/qualification-verifications/{application_id}/decision")
def decide_qualification_verification(
    application_id: int,
    decision: VerificationDecision,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "decide_qualification_verification")
    application = _qualification_application(application_id, db)
    if application.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending applications can be reviewed")
    provider = db.query(models.User).filter(models.User.id == application.user_id).first()
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider account not found")
    application.status = decision.status
    application.review_note = decision.review_note
    application.reviewed_by_user_id = current_user.id
    application.reviewed_at = utc_now()
    provider.qualification_verification_status = decision.status
    profile_id = None
    if decision.status == "approved":
        profile_id = _approve_qualification(application, provider, db).id
    db.commit()
    db.refresh(application)
    return success_response(
        {
            "application": format_qualification_application(application, db),
            "provider_profile_id": profile_id,
        },
        message=f"Qualification verification {decision.status}",
    )
