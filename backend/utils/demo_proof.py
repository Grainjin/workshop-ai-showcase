"""Immutable, local proof selected by the server, never visitor-supplied uploads."""

from fastapi import HTTPException

from backend import models
from backend.core.clock import utc_now
from backend.constants import DEMO_USER_EMAILS
from backend.utils.demo_mode import require_demo_mode

PROOF_LABELS = {"arrival_evidence": "Arrival", "completion_proof": "Completion"}


def require_mapped_demo_provider(user: models.User) -> None:
    require_demo_mode()
    if user.role != "provider" or user.email != DEMO_USER_EMAILS["provider"]:
        raise HTTPException(status_code=404, detail="Not found")


def preset_proof_asset(purpose: str) -> str:
    label = PROOF_LABELS.get(purpose)
    if label is None:
        raise HTTPException(status_code=404, detail="Not found")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="400" '
        'role="img" aria-label="Simulated demo proof">'
        '<rect width="800" height="400" fill="#e7f4ef"/>'
        '<text x="60" y="165" font-family="sans-serif" font-size="40" fill="#15382c">'
        'Simulated demo proof</text>'
        f'<text x="60" y="230" font-family="sans-serif" font-size="28" fill="#15382c">{label} — server preset</text>'
        '<text x="60" y="290" font-family="sans-serif" font-size="22" fill="#15382c">No real service or uploaded evidence</text></svg>'
    )


def preset_proof_metadata(purpose: str, user: models.User) -> dict:
    require_mapped_demo_provider(user)
    asset = preset_proof_asset(purpose)
    return {
        "file_name": f"demo-{purpose}.svg",
        "file_url": f"/demo/proof/{purpose}.svg",
        "original_file_name": f"Simulated demo {PROOF_LABELS[purpose].lower()} proof.svg",
        "content_type": "image/svg+xml",
        "size": len(asset.encode("utf-8")),
    }


def record_preset_proof(booking_id: int, purpose: str, user: models.User, db):
    """Reuse only this provider's server-selected proof when resubmitting an action.

    The caller holds the booking lock and performs normal ownership/state checks.
    """
    metadata = preset_proof_metadata(purpose, user)
    attachment = db.query(models.BookingAttachment).filter_by(
        booking_id=booking_id, purpose=purpose, uploaded_by_user_id=user.id,
        file_name=metadata["file_name"], file_url=metadata["file_url"],
    ).first()
    if attachment is None:
        attachment = models.BookingAttachment(
            booking_id=booking_id, purpose=purpose, uploaded_by_user_id=user.id, created_at=utc_now(),
        )
        db.add(attachment)
    for key, value in metadata.items():
        setattr(attachment, key, value)
    return attachment
