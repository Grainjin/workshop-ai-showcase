from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from backend.config import (
    MAX_UPLOAD_SIZE_BYTES,
    MAX_UPLOAD_SIZE_MB,
    UPLOAD_DIR,
    VERIFICATION_UPLOAD_DIR,
)

CERTIFICATE_UPLOAD_SUBDIR = "certificates"
PORTFOLIO_UPLOAD_SUBDIR = "portfolio"
BOOKING_UPLOAD_SUBDIR = "bookings"
CHAT_UPLOAD_SUBDIR = "chats"
AVATAR_UPLOAD_SUBDIR = "avatars"
IDENTITY_VERIFICATION_UPLOAD_SUBDIR = "identity"
QUALIFICATION_VERIFICATION_UPLOAD_SUBDIR = "qualification"

VERIFICATION_FILE_LIMIT_BYTES = 5 * 1024 * 1024
ALLOWED_VERIFICATION_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
ALLOWED_VERIFICATION_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
}

ALLOWED_CERTIFICATE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".mp4",
    ".pdf",
}
ALLOWED_CERTIFICATE_CONTENT_TYPES = {
    "image/jpeg",
    "video/mp4",
    "application/pdf",
    "application/octet-stream",
}
ALLOWED_PORTFOLIO_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".mp4",
    ".mov",
}
ALLOWED_PORTFOLIO_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "video/mp4",
    "video/quicktime",
    "application/octet-stream",
}
ALLOWED_BOOKING_ATTACHMENT_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".pdf",
    ".mp4",
    ".mov",
}
ALLOWED_BOOKING_ATTACHMENT_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
    "video/mp4",
    "video/quicktime",
    "application/octet-stream",
}
ALLOWED_CHAT_ATTACHMENT_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".pdf",
    ".mp4",
    ".mov",
}
ALLOWED_CHAT_ATTACHMENT_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
    "video/mp4",
    "video/quicktime",
    "application/octet-stream",
}
ALLOWED_AVATAR_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
}
ALLOWED_AVATAR_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "application/octet-stream",
}


def get_certificate_upload_dir():
    return get_upload_subdir(CERTIFICATE_UPLOAD_SUBDIR)


def get_portfolio_upload_dir():
    return get_upload_subdir(PORTFOLIO_UPLOAD_SUBDIR)


def get_booking_upload_dir(booking_id: int):
    return get_upload_subdir(f"{BOOKING_UPLOAD_SUBDIR}/{booking_id}")


def get_chat_upload_dir(chat_room_id: int):
    return get_upload_subdir(f"{CHAT_UPLOAD_SUBDIR}/{chat_room_id}")


def get_avatar_upload_dir():
    return get_upload_subdir(AVATAR_UPLOAD_SUBDIR)


def get_upload_subdir(subdir: str):
    upload_dir = Path(UPLOAD_DIR) / subdir
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def get_safe_original_filename(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a name")

    return Path(file.filename).name


def validate_certificate_file_metadata(file: UploadFile):
    return validate_file_metadata(
        file,
        ALLOWED_CERTIFICATE_EXTENSIONS,
        ALLOWED_CERTIFICATE_CONTENT_TYPES,
        "Only jpg, mp4 and pdf files are allowed",
    )


def validate_portfolio_image_metadata(file: UploadFile):
    return validate_file_metadata(
        file,
        ALLOWED_PORTFOLIO_IMAGE_EXTENSIONS,
        ALLOWED_PORTFOLIO_IMAGE_CONTENT_TYPES,
        "Only jpg, jpeg, png, mp4 and mov files are allowed",
    )


def validate_booking_attachment_metadata(file: UploadFile):
    return validate_file_metadata(
        file,
        ALLOWED_BOOKING_ATTACHMENT_EXTENSIONS,
        ALLOWED_BOOKING_ATTACHMENT_CONTENT_TYPES,
        "Only jpg, jpeg, png, pdf, mp4 and mov files are allowed",
    )


def validate_booking_attachments(files: list[UploadFile] | None) -> None:
    files = [file for file in files or [] if file.filename]
    if len(files) > 7:
        raise HTTPException(status_code=422, detail="A booking can include at most 7 attachments")
    image_count = 0
    video_count = 0
    for file in files:
        original_filename = get_safe_original_filename(file)
        extension = Path(original_filename).suffix.lower()
        content_type = file.content_type or "application/octet-stream"
        if extension in {".jpg", ".jpeg", ".png"} and content_type.startswith("image/"):
            image_count += 1
            limit = 2 * 1024 * 1024
        elif extension in {".mp4", ".mov"} and content_type.startswith("video/"):
            video_count += 1
            limit = 10 * 1024 * 1024
        else:
            raise HTTPException(status_code=422, detail="Booking attachments must be images or videos")
        current_position = file.file.tell()
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(current_position)
        if size > limit:
            raise HTTPException(status_code=422, detail="Booking attachment exceeds its size limit")
    if image_count > 5:
        raise HTTPException(status_code=422, detail="A booking can include at most 5 images")
    if video_count > 2:
        raise HTTPException(status_code=422, detail="A booking can include at most 2 videos")


def validate_chat_attachment_metadata(file: UploadFile):
    return validate_file_metadata(
        file,
        ALLOWED_CHAT_ATTACHMENT_EXTENSIONS,
        ALLOWED_CHAT_ATTACHMENT_CONTENT_TYPES,
        "Only jpg, jpeg, png, pdf, mp4 and mov files are allowed",
    )


def validate_avatar_metadata(file: UploadFile):
    return validate_file_metadata(
        file,
        ALLOWED_AVATAR_EXTENSIONS,
        ALLOWED_AVATAR_CONTENT_TYPES,
        "Only jpg, jpeg and png files are allowed",
    )


def validate_file_metadata(
    file: UploadFile,
    allowed_extensions: set[str],
    allowed_content_types: set[str],
    error_detail: str,
):
    original_filename = get_safe_original_filename(file)
    extension = Path(original_filename).suffix.lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=error_detail,
        )

    content_type = file.content_type or "application/octet-stream"

    if content_type not in allowed_content_types:
        raise HTTPException(
            status_code=400,
            detail=error_detail,
        )

    return original_filename, extension, content_type


def validate_upload_content(content: bytes):
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file cannot be empty")

    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded file cannot be larger than {MAX_UPLOAD_SIZE_MB}MB",
        )


async def save_certificate_upload(file: UploadFile):
    original_filename, extension, content_type = validate_certificate_file_metadata(
        file
    )
    content = await file.read()
    validate_upload_content(content)

    stored_filename = f"{uuid4().hex}{extension}"
    upload_dir = get_certificate_upload_dir()
    stored_path = upload_dir / stored_filename
    stored_path.write_bytes(content)

    return {
        "original_file_name": original_filename,
        "file_name": stored_filename,
        "file_url": f"/uploads/{CERTIFICATE_UPLOAD_SUBDIR}/{stored_filename}",
        "content_type": content_type,
        "media_type": (
            "video"
            if content_type == "video/mp4" or extension == ".mp4"
            else "document"
            if content_type == "application/pdf" or extension == ".pdf"
            else "image"
        ),
        "size": len(content),
    }


async def save_verification_upload(file: UploadFile, *, qualification: bool = False):
    original_filename, extension, content_type = validate_file_metadata(
        file,
        ALLOWED_VERIFICATION_EXTENSIONS,
        ALLOWED_VERIFICATION_CONTENT_TYPES,
        "Only jpg, jpeg, png and pdf files are allowed",
    )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file cannot be empty")
    if len(content) > VERIFICATION_FILE_LIMIT_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Verification files cannot be larger than 5MB",
        )
    subdir = (
        QUALIFICATION_VERIFICATION_UPLOAD_SUBDIR
        if qualification
        else IDENTITY_VERIFICATION_UPLOAD_SUBDIR
    )
    stored_filename = f"{uuid4().hex}{extension}"
    upload_dir = Path(VERIFICATION_UPLOAD_DIR) / subdir
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / stored_filename
    stored_path.write_bytes(content)
    return {
        "original_file_name": original_filename,
        "file_name": stored_filename,
        "file_url": f"/verification-files/{subdir}/{stored_filename}",
        "content_type": content_type,
        "size": len(content),
    }


async def save_portfolio_image_upload(file: UploadFile):
    original_filename, extension, content_type = validate_portfolio_image_metadata(file)
    content = await file.read()
    validate_upload_content(content)

    stored_filename = f"{uuid4().hex}{extension}"
    upload_dir = get_portfolio_upload_dir()
    stored_path = upload_dir / stored_filename
    stored_path.write_bytes(content)

    return {
        "original_file_name": original_filename,
        "file_name": stored_filename,
        "file_url": f"/uploads/{PORTFOLIO_UPLOAD_SUBDIR}/{stored_filename}",
        "content_type": content_type,
        "media_type": (
            "video"
            if content_type.startswith("video/") or extension in {".mp4", ".mov"}
            else "image"
        ),
        "size": len(content),
    }


async def save_portfolio_media_upload(file: UploadFile):
    return await save_portfolio_image_upload(file)


async def save_booking_attachment_upload(booking_id: int, file: UploadFile):
    original_filename, extension, content_type = validate_booking_attachment_metadata(
        file
    )
    content = await file.read()
    validate_upload_content(content)

    stored_filename = f"{uuid4().hex}{extension}"
    upload_dir = get_booking_upload_dir(booking_id)
    stored_path = upload_dir / stored_filename
    stored_path.write_bytes(content)

    return {
        "original_file_name": original_filename,
        "file_name": stored_filename,
        "file_url": (
            f"/uploads/{BOOKING_UPLOAD_SUBDIR}/{booking_id}/{stored_filename}"
        ),
        "content_type": content_type,
        "size": len(content),
    }


async def save_chat_attachment_upload(chat_room_id: int, file: UploadFile):
    original_filename, extension, content_type = validate_chat_attachment_metadata(file)
    content = await file.read()
    validate_upload_content(content)

    stored_filename = f"{uuid4().hex}{extension}"
    upload_dir = get_chat_upload_dir(chat_room_id)
    stored_path = upload_dir / stored_filename
    stored_path.write_bytes(content)

    return {
        "original_file_name": original_filename,
        "file_name": stored_filename,
        "file_url": f"/uploads/{CHAT_UPLOAD_SUBDIR}/{chat_room_id}/{stored_filename}",
        "content_type": content_type,
        "size": len(content),
    }


async def save_avatar_upload(file: UploadFile):
    original_filename, extension, content_type = validate_avatar_metadata(file)
    content = await file.read()
    validate_upload_content(content)

    stored_filename = f"{uuid4().hex}{extension}"
    upload_dir = get_avatar_upload_dir()
    stored_path = upload_dir / stored_filename
    stored_path.write_bytes(content)

    return {
        "original_file_name": original_filename,
        "file_name": stored_filename,
        "file_url": f"/uploads/{AVATAR_UPLOAD_SUBDIR}/{stored_filename}",
        "content_type": content_type,
        "size": len(content),
    }


def delete_local_upload(file_url: str):
    upload_prefix = "/uploads/"

    if not file_url.startswith(upload_prefix):
        return False

    relative_path = file_url.removeprefix(upload_prefix)
    upload_root = Path(UPLOAD_DIR).resolve()
    local_path = (upload_root / relative_path).resolve()

    if upload_root not in local_path.parents:
        return False

    try:
        if local_path.exists() and local_path.is_file():
            local_path.unlink()
            return True
    except OSError:
        return False

    return False
