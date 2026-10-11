"""Quote request decoding and transactional revision-linked file uploads."""

from contextlib import asynccontextmanager

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from backend import models
from backend.core.clock import utc_now
from backend.schemas import ProviderBookingQuoteCreate
from backend.utils.upload import delete_local_upload, save_booking_attachment_upload


_quote_schema = ProviderBookingQuoteCreate.model_json_schema()
QUOTE_UPLOAD_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {"schema": _quote_schema},
            "multipart/form-data": {
                "schema": {
                    **_quote_schema,
                    "properties": {
                        **_quote_schema["properties"],
                        "quote_files": {
                            "type": "array",
                            "items": {"type": "string", "format": "binary"},
                            "description": "Optional attachments belonging to this quote.",
                        },
                    },
                },
            },
        },
    },
}


async def parse_quote_request(request: Request):
    """Keep JSON/no-file callers while accepting multipart quotes from the UI."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    files = []
    if content_type == "multipart/form-data":
        form = await request.form()
        payload = {
            key: form[key]
            for key in ProviderBookingQuoteCreate.model_fields
            if key in form
        }
        files = form.getlist("quote_files")
        if any(not isinstance(file, UploadFile) or not file.filename for file in files):
            raise RequestValidationError([
                {"loc": ("body", "quote_files"), "msg": "Upload valid quote files", "type": "value_error"},
            ])
    elif content_type == "application/json":
        try:
            payload = await request.json()
        except ValueError as exc:
            raise RequestValidationError([
                {"loc": ("body",), "msg": "Invalid JSON", "type": "json_invalid"},
            ]) from exc
    else:
        raise HTTPException(status_code=415, detail="Use JSON or multipart/form-data for a quote")

    try:
        quote = ProviderBookingQuoteCreate.model_validate(payload)
    except ValidationError as exc:
        raise RequestValidationError([
            {**error, "loc": ("body", *error["loc"])} for error in exc.errors()
        ]) from exc
    return quote, files


@asynccontextmanager
async def quote_upload_transaction(db):
    """Commit quote and files together; remove new files only on a failed commit."""
    saved_urls = []
    try:
        yield saved_urls
        db.commit()
    except Exception:
        db.rollback()
        for file_url in saved_urls:
            delete_local_upload(file_url)
        raise


async def save_quote_files(booking, revision, current_user, db, files, saved_urls):
    db.add(revision)
    db.flush()
    for file in files or []:
        upload = await save_booking_attachment_upload(booking.id, file)
        saved_urls.append(upload["file_url"])
        db.add(models.BookingAttachment(
            booking_id=booking.id,
            uploaded_by_user_id=current_user.id,
            purpose="quote_attachment",
            quote_revision_id=revision.id,
            original_file_name=upload["original_file_name"],
            file_name=upload["file_name"],
            file_url=upload["file_url"],
            content_type=upload["content_type"],
            size=upload["size"],
            created_at=utc_now(),
        ))
    db.flush()
