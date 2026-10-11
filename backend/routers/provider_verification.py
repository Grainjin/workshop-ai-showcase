from datetime import date
import re

from pathlib import Path

from fastapi import Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_db, require_provider, require_verified_user
from backend.config import VERIFICATION_UPLOAD_DIR
from backend.schemas.provider_verification import (
    IdentityDocumentType,
    ProviderOperatingSettingsV2Patch,
    ProviderServiceAreasUpdate,
    QualificationVerificationSubmit,
)
from backend.utils.provider import (
    get_provider_profile_for_user,
    require_provider_qualification_approved,
)
from backend.utils.provider_verification import (
    format_identity_application,
    format_qualification_application,
    latest_identity_application,
    latest_qualification_application,
    provider_verification_status,
)
from backend.utils.formatters import tags_to_string
from backend.utils.response import success_response
from backend.utils.router import ApiRouter
from backend.utils.demo_mode import reject_demo_restricted_action
from backend.utils.service_locations import (
    format_service_area,
    get_location,
    location_scope_ids,
)
from backend.utils.upload import save_verification_upload


router = ApiRouter(tags=["Provider Verification"])


def _validated_service_area_locations(db: Session, location_ids: list[int]):
    locations = [get_location(db, location_id) for location_id in location_ids]
    for index, location in enumerate(locations):
        descendants = location_scope_ids(db, location.id)
        for other in locations[index + 1 :]:
            if other.id in descendants or location.id in location_scope_ids(db, other.id):
                raise HTTPException(
                    status_code=422,
                    detail="Service areas cannot contain overlapping parent and child locations",
                )
    return locations


def _parse_date_of_birth(value: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise HTTPException(
            status_code=422,
            detail="date_of_birth must use YYYY-MM-DD format",
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="date_of_birth must be a valid calendar date",
        ) from exc


@router.get("/verification-files/{kind}/{filename}")
def download_verification_file(
    kind: str,
    filename: str,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    if kind not in {"identity", "qualification"} or Path(filename).name != filename:
        raise HTTPException(status_code=404, detail="Verification file not found")
    file_url = f"/verification-files/{kind}/{filename}"
    if current_user.role != "admin":
        if current_user.role != "provider":
            raise HTTPException(status_code=403, detail="Provider or admin access required")
        if kind == "identity":
            owned_file = (
                db.query(models.IdentityVerificationFile.id)
                .join(
                    models.IdentityVerificationApplication,
                    models.IdentityVerificationApplication.id
                    == models.IdentityVerificationFile.application_id,
                )
                .filter(
                    models.IdentityVerificationFile.file_url == file_url,
                    models.IdentityVerificationApplication.user_id == current_user.id,
                )
                .first()
            )
        else:
            owned_file = (
                db.query(models.QualificationVerificationFile.id)
                .join(
                    models.QualificationVerificationApplication,
                    models.QualificationVerificationApplication.id
                    == models.QualificationVerificationFile.application_id,
                )
                .filter(
                    models.QualificationVerificationFile.file_url == file_url,
                    models.QualificationVerificationApplication.user_id == current_user.id,
                )
                .first()
            )
        if owned_file is None:
            raise HTTPException(status_code=404, detail="Verification file not found")
    path = (Path(VERIFICATION_UPLOAD_DIR) / kind / filename).resolve()
    root = Path(VERIFICATION_UPLOAD_DIR).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Verification file not found")
    return FileResponse(path)


def _ensure_can_submit_identity(user):
    if user.identity_verification_status in {"pending", "approved"}:
        raise HTTPException(
            status_code=409,
            detail="Identity verification is locked while pending or approved",
        )
    if not user.first_name or not user.last_name:
        raise HTTPException(
            status_code=422,
            detail="first_name and last_name are required before identity verification",
        )


def _ensure_can_submit_qualification(user):
    if user.qualification_verification_status in {"pending", "approved"}:
        raise HTTPException(
            status_code=409,
            detail="Qualification verification is locked while pending or approved",
        )


@router.get("/provider/verification-status")
def get_verification_status(
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    identity = latest_identity_application(current_user.id, db)
    qualification = latest_qualification_application(current_user.id, db)
    return success_response(
        {
            **provider_verification_status(current_user),
            "identity_application_id": identity.id if identity else None,
            "qualification_application_id": qualification.id if qualification else None,
        }
    )


@router.post("/provider/identity-verification")
async def submit_identity_verification(
    date_of_birth: str = Form(...),
    document_type: IdentityDocumentType = Form(...),
    files: list[UploadFile] = File(...),
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "submit_identity_verification")
    _ensure_can_submit_identity(current_user)
    parsed_date_of_birth = _parse_date_of_birth(date_of_birth)
    if not 1 <= len(files) <= 5:
        raise HTTPException(status_code=422, detail="Upload between 1 and 5 identity files")
    upload_results = [await save_verification_upload(file) for file in files]
    application = models.IdentityVerificationApplication(
        user_id=current_user.id,
        submitted_first_name=current_user.first_name,
        submitted_last_name=current_user.last_name,
        date_of_birth=parsed_date_of_birth,
        document_type=document_type.value,
        status="pending",
    )
    db.add(application)
    db.flush()
    for index, upload in enumerate(upload_results):
        db.add(
            models.IdentityVerificationFile(
                application_id=application.id,
                file_url=upload["file_url"],
                original_file_name=upload["original_file_name"],
                content_type=upload["content_type"],
                sort_order=index,
            )
        )
    current_user.identity_verification_status = "pending"
    if current_user.qualification_verification_status == "locked":
        current_user.qualification_verification_status = "not_submitted"
    db.commit()
    db.refresh(application)
    return success_response(
        format_identity_application(application, db),
        message="Identity verification submitted successfully",
    )


@router.get("/provider/identity-verification")
def get_identity_verification(
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    application = latest_identity_application(current_user.id, db)
    if application is None:
        raise HTTPException(status_code=404, detail="Identity verification not submitted")
    return success_response(format_identity_application(application, db))


@router.post("/provider/qualification-files/upload")
async def upload_qualification_files(
    files: list[UploadFile] = File(...),
    current_user: models.User = Depends(require_provider),
):
    reject_demo_restricted_action(current_user, "upload_qualification_files")
    _ensure_can_submit_qualification(current_user)
    if not 1 <= len(files) <= 5:
        raise HTTPException(status_code=422, detail="Upload between 1 and 5 qualification files")
    results = [
        await save_verification_upload(file, qualification=True) for file in files
    ]
    return success_response(
        {"files": results}, message="Qualification files uploaded successfully"
    )


@router.post("/provider/qualification-verification")
def submit_qualification_verification(
    payload: QualificationVerificationSubmit,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "submit_qualification_verification")
    _ensure_can_submit_qualification(current_user)
    service_area_locations = _validated_service_area_locations(
        db, payload.service_location_ids
    )
    for file in payload.qualification_files:
        if not file.file_url.startswith("/verification-files/qualification/"):
            raise HTTPException(
                status_code=422,
                detail="Qualification files must be uploaded with the qualification upload endpoint",
            )
    if payload.unique_enterprise_id:
        duplicate_application = (
            db.query(models.QualificationVerificationApplication)
            .filter(
                models.QualificationVerificationApplication.unique_enterprise_id
                == payload.unique_enterprise_id,
                models.QualificationVerificationApplication.status.in_(["pending", "approved"]),
            )
            .first()
        )
        duplicate_profile = (
            db.query(models.ProviderProfile)
            .filter(models.ProviderProfile.unique_enterprise_id == payload.unique_enterprise_id)
            .first()
        )
        if duplicate_application or duplicate_profile:
            raise HTTPException(status_code=409, detail="unique_enterprise_id is already in use")
    display_name = (
        f"{current_user.first_name} {current_user.last_name}"
        if payload.entity_type == "personal"
        else payload.legal_name
    )
    application = models.QualificationVerificationApplication(
        user_id=current_user.id,
        entity_type=payload.entity_type,
        legal_name=payload.legal_name,
        unique_enterprise_id=payload.unique_enterprise_id,
        display_name=display_name,
        description=payload.description,
        contact_phone=payload.contact_phone,
        business_address=payload.business_address,
        business_place_id=payload.business_place_id,
        business_latitude=payload.business_latitude,
        business_longitude=payload.business_longitude,
        status="pending",
    )
    db.add(application)
    db.flush()
    for service in payload.service_categories:
        db.add(
            models.QualificationVerificationService(
                application_id=application.id,
                service_category=service,
            )
        )
    for location in service_area_locations:
        db.add(
            models.QualificationVerificationServiceArea(
                application_id=application.id,
                service_location_id=location.id,
            )
        )
    for index, file in enumerate(payload.qualification_files):
        db.add(
            models.QualificationVerificationFile(
                application_id=application.id,
                file_url=file.file_url,
                original_file_name=file.original_file_name,
                content_type=file.content_type,
                sort_order=index,
            )
        )
    current_user.qualification_verification_status = "pending"
    db.commit()
    db.refresh(application)
    return success_response(
        format_qualification_application(application, db),
        message="Qualification verification submitted successfully",
    )


@router.get("/provider/qualification-verification")
def get_qualification_verification(
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    application = latest_qualification_application(current_user.id, db)
    if application is None:
        raise HTTPException(status_code=404, detail="Qualification verification not submitted")
    return success_response(format_qualification_application(application, db))


@router.get("/provider/approved-services")
def get_approved_services(
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(profile)
    services = (
        db.query(models.ProviderApprovedService)
        .filter(models.ProviderApprovedService.provider_profile_id == profile.id)
        .order_by(models.ProviderApprovedService.service_category.asc())
        .all()
    )
    return success_response(
        {
            "approved_service_categories": [item.service_category for item in services],
            "enabled_service_categories": [
                item.service_category for item in services if item.is_enabled
            ],
        }
    )


@router.patch("/provider/operating-settings")
def update_operating_settings(
    payload: ProviderOperatingSettingsV2Patch,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(profile)
    updates = payload.model_dump(exclude_unset=True)
    mapping = {
        "description": "bio",
        "contact_phone": "phone_number",
        "business_address": "address",
        "business_latitude": "latitude",
        "business_longitude": "longitude",
    }
    for field, value in updates.items():
        if field in {"enabled_service_categories"}:
            continue
        setattr(profile, mapping.get(field, field), value)
    if "business_address" in updates and "business_place_id" not in updates:
        profile.business_place_id = None
    if payload.enabled_service_categories is not None:
        rows = (
            db.query(models.ProviderApprovedService)
            .filter(models.ProviderApprovedService.provider_profile_id == profile.id)
            .all()
        )
        approved = {row.service_category for row in rows}
        requested = set(payload.enabled_service_categories)
        if not requested.issubset(approved):
            raise HTTPException(
                status_code=422,
                detail="Only approved service categories can be enabled",
            )
        for row in rows:
            row.is_enabled = row.service_category in requested
        profile.tags = tags_to_string(sorted(requested))
    db.commit()
    db.refresh(profile)
    return success_response({"message": "Operating settings updated successfully"})


@router.put("/provider/service-areas")
def replace_service_areas(
    payload: ProviderServiceAreasUpdate,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(profile)
    locations = _validated_service_area_locations(db, payload.service_location_ids)
    db.query(models.ProviderServiceArea).filter(
        models.ProviderServiceArea.provider_profile_id == profile.id
    ).delete(synchronize_session=False)
    for location in locations:
        db.add(
            models.ProviderServiceArea(
                provider_profile_id=profile.id,
                service_location_id=location.id,
            )
        )
    db.commit()
    return success_response(
        {
            "service_areas": [
                format_service_area(db, location) for location in locations
            ]
        },
        message="Service areas updated successfully",
    )


@router.get("/provider/service-areas")
def get_service_areas(
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(profile)
    rows = (
        db.query(models.ProviderServiceArea, models.ServiceLocation)
        .join(
            models.ServiceLocation,
            models.ServiceLocation.id == models.ProviderServiceArea.service_location_id,
        )
        .filter(models.ProviderServiceArea.provider_profile_id == profile.id)
        .order_by(models.ServiceLocation.name.asc())
        .all()
    )
    return success_response(
        {
            "service_areas": [
                format_service_area(db, location) for _, location in rows
            ]
        }
    )
