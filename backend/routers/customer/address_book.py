from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_db, require_customer
from backend.core.clock import utc_now
from backend.schemas import (
    ApiResponse,
    CustomerAddressCreate,
    CustomerAddressResponse,
    CustomerAddressUpdate,
)
from backend.utils.response import success_response
from backend.utils.router import ApiRouter

router = ApiRouter(tags=["Customer Address Book"])


def _query_for_customer(db: Session, customer_id: int):
    return db.query(models.CustomerAddress).filter(
        models.CustomerAddress.customer_id == customer_id
    )


def _serialize(address: models.CustomerAddress) -> dict:
    return {
        "id": address.id,
        "customer_id": address.customer_id,
        "label": address.label,
        "place_id": address.place_id,
        "formatted_address": address.formatted_address,
        "latitude": address.latitude,
        "longitude": address.longitude,
        "service_location_id": address.service_location_id,
        "is_default": address.is_default,
        "created_at": address.created_at,
        "updated_at": address.updated_at,
    }


def _set_default(db: Session, customer_id: int, selected: models.CustomerAddress) -> None:
    _query_for_customer(db, customer_id).filter(models.CustomerAddress.id != selected.id).update(
        {models.CustomerAddress.is_default: False}, synchronize_session=False
    )
    selected.is_default = True


def _ensure_service_location(db: Session, service_location_id: int | None) -> None:
    if service_location_id is None:
        return
    location = db.get(models.ServiceLocation, service_location_id)
    if location is None or location.level not in {"province", "city", "district"}:
        raise HTTPException(status_code=422, detail="Invalid service location")


@router.get("/customer/addresses", response_model=ApiResponse[list[CustomerAddressResponse]])
def list_addresses(
    current_user: models.User = Depends(require_customer), db: Session = Depends(get_db)
):
    addresses = (
        _query_for_customer(db, current_user.id)
        .order_by(models.CustomerAddress.is_default.desc(), models.CustomerAddress.created_at.asc())
        .all()
    )
    return success_response([_serialize(address) for address in addresses])


@router.post("/customer/addresses", response_model=ApiResponse[CustomerAddressResponse])
def create_address(
    address_data: CustomerAddressCreate,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    _ensure_service_location(db, address_data.service_location_id)
    count = _query_for_customer(db, current_user.id).count()
    if count >= 5:
        raise HTTPException(status_code=409, detail="A customer can save at most 5 addresses")
    address = models.CustomerAddress(
        customer_id=current_user.id,
        **address_data.model_dump(),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(address)
    db.flush()
    existing_default = (
        _query_for_customer(db, current_user.id)
        .filter(
            models.CustomerAddress.id != address.id,
            models.CustomerAddress.is_default.is_(True),
        )
        .first()
    )
    if address.is_default or existing_default is None:
        _set_default(db, current_user.id, address)
    db.commit()
    db.refresh(address)
    return success_response(_serialize(address))


@router.patch(
    "/customer/addresses/{address_id}", response_model=ApiResponse[CustomerAddressResponse]
)
def update_address(
    address_id: int,
    address_data: CustomerAddressUpdate,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    address = (
        _query_for_customer(db, current_user.id)
        .filter(models.CustomerAddress.id == address_id)
        .first()
    )
    if address is None:
        raise HTTPException(status_code=404, detail="Address not found")
    updates = address_data.model_dump(exclude_unset=True)
    if "label" in updates:
        address.label = updates["label"]
    if updates.get("is_default") is True:
        _set_default(db, current_user.id, address)
    elif updates.get("is_default") is False and address.is_default:
        raise HTTPException(status_code=422, detail="Address book must retain a default address")
    db.commit()
    db.refresh(address)
    return success_response(_serialize(address))


@router.delete("/customer/addresses/{address_id}", response_model=ApiResponse[None])
def delete_address(
    address_id: int,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    address = (
        _query_for_customer(db, current_user.id)
        .filter(models.CustomerAddress.id == address_id)
        .first()
    )
    if address is None:
        raise HTTPException(status_code=404, detail="Address not found")
    was_default = address.is_default
    db.delete(address)
    db.flush()
    if was_default:
        replacement = (
            _query_for_customer(db, current_user.id)
            .order_by(models.CustomerAddress.created_at.asc())
            .first()
        )
        if replacement is not None:
            replacement.is_default = True
    db.commit()
    return success_response(None, message="Address deleted successfully")
