"""Mapped demo Provider actions: no request body, uploaded file, path or URL input."""

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_db, require_provider
from backend.schemas import BookingStatus
from backend.utils.booking import format_booking_detail_response
from backend.utils.demo_mode import DemoModeRoute
from backend.utils.demo_proof import preset_proof_asset, preset_proof_metadata, require_mapped_demo_provider
from backend.utils.provider import get_provider_profile_for_user, require_provider_qualification_approved
from backend.utils.provider_booking_actions import complete_provider_booking_action, start_provider_visit_action
from backend.utils.response import success_response
from backend.utils.router import ApiRouter

router = ApiRouter(tags=["Provider"], route_class=DemoModeRoute)


async def run_preset_action(booking_id, purpose, request, current_user, db):
    require_mapped_demo_provider(current_user)
    if request.query_params or await request.body():
        raise HTTPException(status_code=400, detail="Demo proof actions accept no input")
    profile = get_provider_profile_for_user(current_user.id, db)
    require_provider_qualification_approved(profile)
    booking = db.query(models.Booking).filter_by(
        id=booking_id, provider_profile_id=profile.id,
    ).with_for_update().populate_existing().first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    preset = preset_proof_metadata(purpose, current_user)
    existing = db.query(models.BookingAttachment).filter_by(
        booking_id=booking.id, purpose=purpose, uploaded_by_user_id=current_user.id,
        file_name=preset["file_name"], file_url=preset["file_url"],
    ).first()
    action_status = BookingStatus.provider_arrived if purpose == "arrival_evidence" else BookingStatus.awaiting_confirmation
    if existing and booking.status == action_status:
        # Only replay an action still reflected in the current state. A customer
        # rejection requires a new business transition, even when proof remains.
        return success_response({"booking": format_booking_detail_response(booking, db),
                                 "message": "Simulated proof already recorded"})
    action = start_provider_visit_action if purpose == "arrival_evidence" else complete_provider_booking_action
    result = await action(booking.id, current_user, db, None, demo_proof=True)
    return success_response(result)


@router.put("/provider/demo/bookings/{booking_id}/start-visit")
async def start_demo_visit(booking_id: int, request: Request,
    current_user: models.User = Depends(require_provider), db: Session = Depends(get_db)):
    return await run_preset_action(booking_id, "arrival_evidence", request, current_user, db)


@router.put("/provider/demo/bookings/{booking_id}/complete")
async def complete_demo_booking(booking_id: int, request: Request,
    current_user: models.User = Depends(require_provider), db: Session = Depends(get_db)):
    return await run_preset_action(booking_id, "completion_proof", request, current_user, db)


@router.get("/demo/proof/{purpose}.svg")
def get_demo_proof(purpose: str):
    return Response(preset_proof_asset(purpose), media_type="image/svg+xml")
