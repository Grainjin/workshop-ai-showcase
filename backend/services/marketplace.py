from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend import config, models
from backend.core.clock import utc_now
from backend.schemas import ProviderSubmerchantUpsert, SubmerchantStatus
from backend.services import iyzico as iyzico_service
from backend.utils.marketplace import format_submerchant_response


def _apply_submerchant_data(
    submerchant: models.ProviderSubmerchant,
    data: ProviderSubmerchantUpsert,
) -> None:
    submerchant.submerchant_type = data.submerchant_type.value
    submerchant.name = data.name
    submerchant.email = str(data.email)
    submerchant.gsm_number = data.gsm_number
    submerchant.address = data.address
    submerchant.iban = data.iban
    submerchant.contact_name = data.contact_name
    submerchant.contact_surname = data.contact_surname
    submerchant.identity_number = data.identity_number
    submerchant.tax_office = data.tax_office
    submerchant.tax_number = data.tax_number
    submerchant.legal_company_title = data.legal_company_title
    submerchant.currency = data.currency


def _submerchant_payload(
    submerchant: models.ProviderSubmerchant,
    data: ProviderSubmerchantUpsert,
) -> dict:
    payload = {
        "locale": "en",
        "subMerchantType": data.submerchant_type.value,
        "subMerchantExternalId": submerchant.submerchant_external_id,
        "address": data.address,
        "taxOffice": data.tax_office,
        "legalCompanyTitle": data.legal_company_title,
        "email": str(data.email),
        "gsmNumber": data.gsm_number,
        "name": data.name,
        "contactName": data.contact_name,
        "contactSurname": data.contact_surname,
        "iban": data.iban,
        "identityNumber": data.identity_number,
        "taxNumber": data.tax_number,
        "currency": data.currency,
    }
    if submerchant.submerchant_key:
        payload["subMerchantKey"] = submerchant.submerchant_key
    return {key: value for key, value in payload.items() if value is not None}


def _external_error(exc: Exception | dict) -> tuple[str, str]:
    response_data = getattr(exc, "response_data", None) or (
        exc if isinstance(exc, dict) else {}
    )
    return (
        str(response_data.get("errorCode") or "submerchant_sync_failed"),
        str(response_data.get("errorMessage") or str(exc)),
    )


def _is_existing_submerchant_response(response: dict) -> bool:
    error_code = str(response.get("errorCode") or "")
    error_message = str(response.get("errorMessage") or "").lower()
    return error_code == "2002" or "does exist" in error_message


async def upsert_provider_submerchant(
    provider_profile: models.ProviderProfile,
    data: ProviderSubmerchantUpsert,
    db: Session,
):
    if config.PAYMENT_MODE == "demo" or config.DEMO_MODE:
        raise HTTPException(status_code=403, detail="External payout changes are disabled in demo mode")
    submerchant = (
        db.query(models.ProviderSubmerchant)
        .filter(models.ProviderSubmerchant.provider_profile_id == provider_profile.id)
        .with_for_update()
        .first()
    )
    external_id = f"provider-{provider_profile.id}"
    if not submerchant:
        submerchant = models.ProviderSubmerchant(
            provider_profile_id=provider_profile.id,
            submerchant_type=data.submerchant_type.value,
            submerchant_external_id=external_id,
            email=str(data.email),
            gsm_number=data.gsm_number,
            address=data.address,
        )
        db.add(submerchant)
        db.flush()
        _apply_submerchant_data(submerchant, data)
    else:
        if (
            submerchant.status == SubmerchantStatus.active.value
            and submerchant.submerchant_type != data.submerchant_type.value
        ):
            raise ValueError("Submerchant type cannot be changed after activation")
        _apply_submerchant_data(submerchant, data)

    was_registered = bool(submerchant.submerchant_key)
    client = iyzico_service.get_iyzico_client()
    submerchant.status = SubmerchantStatus.draft.value
    submerchant.iyzico_error_code = None
    submerchant.iyzico_error_message = None
    db.flush()
    try:
        payload = _submerchant_payload(submerchant, data)
        recovered_existing = False
        result = (
            await client.update_submerchant(payload)
            if was_registered
            else await client.create_submerchant(payload)
        )
        if str(result.get("status", "")).lower() != "success":
            if not was_registered and _is_existing_submerchant_response(result):
                result = await client.get_submerchant(
                    submerchant.submerchant_external_id
                )
                recovered_existing = True
            else:
                raise iyzico_service.IyzicoClientError(
                    "iyzico rejected the submerchant",
                    response_data=result,
                )
        if str(result.get("status", "")).lower() != "success":
            raise iyzico_service.IyzicoClientError(
                "iyzico rejected the submerchant detail query",
                response_data=result,
            )
        key = result.get("subMerchantKey") or result.get("submerchantKey")
        if key:
            submerchant.submerchant_key = str(key)
        if not submerchant.submerchant_key:
            raise iyzico_service.IyzicoClientError(
                "iyzico did not return a subMerchantKey", response_data=result
            )

        detail = (
            result
            if recovered_existing
            else await client.get_submerchant(submerchant.submerchant_external_id)
        )
        if str(detail.get("status", "")).lower() != "success":
            raise iyzico_service.IyzicoClientError(
                "iyzico rejected the submerchant detail query",
                response_data=detail,
            )
        detail_key = detail.get("subMerchantKey") or detail.get("submerchantKey")
        if detail_key:
            submerchant.submerchant_key = str(detail_key)
        submerchant.status = SubmerchantStatus.active.value
        submerchant.last_synced_at = utc_now()
        submerchant.iyzico_error_code = None
        submerchant.iyzico_error_message = None
    except (iyzico_service.IyzicoClientError, ValueError) as exc:
        code, message = _external_error(exc)
        submerchant.status = (
            SubmerchantStatus.update_failed.value
            if was_registered
            else SubmerchantStatus.rejected.value
        )
        submerchant.iyzico_error_code = code
        submerchant.iyzico_error_message = message
        submerchant.last_synced_at = None

    db.commit()
    db.refresh(submerchant)
    return format_submerchant_response(submerchant)
