"""Mailed one-time codes that prove control of an email address.

Used before an account exists (registration), to verify a signed-in user's
address, and to change it. A code is six random digits, stored only as a
salted hash, valid for CODE_TTL and for MAX_ATTEMPTS guesses. Sending a new
code spends the previous one for the same purpose and owner.

Registration codes have no user yet, so they are owned by the email address
and also limited per client IP, since anyone can ask for one.
"""

import hashlib
import hmac
import math
import secrets
from datetime import timedelta
from enum import Enum

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_now
from backend.core.clock import parse_dt
from backend.services.email_service import EmailDeliveryError, send_email

CODE_TTL = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_SENDS_PER_HOUR = 5
MAX_REGISTER_SENDS_PER_IP_PER_HOUR = 20
MAX_ATTEMPTS = 5


class EmailCodePurpose(str, Enum):
    register = "register"
    verify_email = "verify_email"
    change_email = "change_email"


def _hash_code(salt: str, code: str) -> str:
    return hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()


def _owned_codes(
    db: Session,
    user: models.User | None,
    purpose: EmailCodePurpose,
    email: str,
):
    """Codes for this purpose and owner: the user, or the email before sign-up."""
    query = db.query(models.EmailVerificationCode).filter(
        models.EmailVerificationCode.purpose == purpose.value,
    )
    if user is not None:
        return query.filter(models.EmailVerificationCode.user_id == user.id)
    return query.filter(
        models.EmailVerificationCode.user_id.is_(None),
        models.EmailVerificationCode.email == email,
    )


def _enforce_send_limits(
    db: Session,
    user: models.User | None,
    purpose: EmailCodePurpose,
    email: str,
    requested_ip: str | None,
    now,
):
    hour_ago = now - timedelta(hours=1)

    if purpose == EmailCodePurpose.register and requested_ip:
        from_ip = (
            db.query(models.EmailVerificationCode)
            .filter(
                models.EmailVerificationCode.purpose == purpose.value,
                models.EmailVerificationCode.requested_ip == requested_ip,
                models.EmailVerificationCode.created_at >= hour_ago,
            )
            .count()
        )
        if from_ip >= MAX_REGISTER_SENDS_PER_IP_PER_HOUR:
            raise HTTPException(
                status_code=429,
                detail="Too many codes requested. Try again in an hour",
            )

    recent = (
        _owned_codes(db, user, purpose, email)
        .filter(models.EmailVerificationCode.created_at >= hour_ago)
        .order_by(models.EmailVerificationCode.created_at.desc())
        .all()
    )
    if not recent:
        return

    wait = parse_dt(recent[0].created_at) + RESEND_COOLDOWN - now
    if wait.total_seconds() > 0:
        seconds = math.ceil(wait.total_seconds())
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {seconds} seconds before requesting another code",
        )

    if len(recent) >= MAX_SENDS_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail="Too many codes requested. Try again in an hour",
        )


def send_email_code(
    db: Session,
    user: models.User | None,
    purpose: EmailCodePurpose,
    email: str,
    requested_ip: str | None = None,
) -> dict:
    """Mail a fresh code to `email`. `user` is None before registration.
    The caller commits on success."""
    now = get_now()
    _enforce_send_limits(db, user, purpose, email, requested_ip, now)

    active = _owned_codes(db, user, purpose, email).filter(
        models.EmailVerificationCode.consumed_at.is_(None)
    )
    for previous in active:
        previous.consumed_at = now

    code = f"{secrets.randbelow(1_000_000):06d}"
    salt = secrets.token_hex(16)
    db.add(
        models.EmailVerificationCode(
            user_id=user.id if user is not None else None,
            purpose=purpose.value,
            email=email,
            requested_ip=requested_ip,
            code_salt=salt,
            code_hash=_hash_code(salt, code),
            attempts=0,
            created_at=now,
            expires_at=now + CODE_TTL,
        )
    )
    db.flush()

    minutes = int(CODE_TTL.total_seconds() // 60)
    if purpose == EmailCodePurpose.register:
        subject = "Your Workshop AI sign-up code"
        reason = "to finish creating your Workshop AI account"
    elif purpose == EmailCodePurpose.change_email:
        subject = "Confirm your new Workshop AI email"
        reason = "to make this address your Workshop AI sign-in email"
    else:
        subject = "Your Workshop AI verification code"
        reason = "to verify your Workshop AI email address"

    greeting = f"Hi {user.first_name or user.name}," if user is not None else "Hi,"
    body = (
        f"{greeting}\n\n"
        f"Your code is {code}. Enter it {reason}.\n\n"
        f"It expires in {minutes} minutes. If you did not ask for this code, "
        "you can ignore this email.\n\n"
        "Workshop AI"
    )

    try:
        send_email(email, subject, body)
    except EmailDeliveryError as exc:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="We could not send the verification email. Please try again later",
        ) from exc

    return {
        "sent_to": email,
        "expires_in_seconds": int(CODE_TTL.total_seconds()),
        "resend_after_seconds": int(RESEND_COOLDOWN.total_seconds()),
    }


def consume_email_code(
    db: Session,
    user: models.User | None,
    purpose: EmailCodePurpose,
    email: str,
    code: str,
) -> None:
    """Spend a matching code or raise 400. `user` is None before registration.
    The caller commits on success; failed attempts are committed here."""
    now = get_now()
    record = (
        _owned_codes(db, user, purpose, email)
        .filter(models.EmailVerificationCode.consumed_at.is_(None))
        .order_by(models.EmailVerificationCode.created_at.desc())
        .first()
    )

    if record is None or record.email != email:
        raise HTTPException(
            status_code=400,
            detail="No active code for this email. Request a new code",
        )

    if parse_dt(record.expires_at) <= now:
        record.consumed_at = now
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="This code has expired. Request a new code",
        )

    if not hmac.compare_digest(record.code_hash, _hash_code(record.code_salt, code)):
        record.attempts += 1
        remaining = MAX_ATTEMPTS - record.attempts
        if remaining <= 0:
            record.consumed_at = now
        db.commit()
        if remaining <= 0:
            raise HTTPException(
                status_code=400,
                detail="Too many wrong attempts. Request a new code",
            )
        raise HTTPException(
            status_code=400,
            detail=f"Incorrect code. {remaining} attempts left",
        )

    record.consumed_at = now
