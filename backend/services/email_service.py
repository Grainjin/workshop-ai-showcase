"""Outgoing email.

WORKSHOP_EMAIL_BACKEND picks the transport:
- "console" (default) logs the message, for local runs without a mailbox.
- "memory" keeps messages in OUTBOX, for tests.
- "smtp" sends through WORKSHOP_SMTP_HOST with STARTTLS (Gmail: an App Password).
"""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr

from backend import config

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    pass


@dataclass
class SentEmail:
    to: str
    subject: str
    body: str


OUTBOX: list[SentEmail] = []


def send_email(to: str, subject: str, body: str) -> None:
    backend = config.EMAIL_BACKEND.lower()

    if backend == "smtp":
        _send_with_smtp(to, subject, body)
        return

    if backend == "memory":
        OUTBOX.append(SentEmail(to=to, subject=subject, body=body))
        return

    logger.warning("Email not sent (console backend) to=%s subject=%s\n%s", to, subject, body)


def _send_with_smtp(to: str, subject: str, body: str) -> None:
    if not config.SMTP_USERNAME or not config.SMTP_PASSWORD or not config.EMAIL_FROM:
        raise EmailDeliveryError(
            "SMTP is not configured: set WORKSHOP_SMTP_USERNAME, "
            "WORKSHOP_SMTP_PASSWORD and WORKSHOP_EMAIL_FROM"
        )

    message = EmailMessage()
    message["From"] = formataddr((config.EMAIL_FROM_NAME, config.EMAIL_FROM))
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(
            config.SMTP_HOST,
            config.SMTP_PORT,
            timeout=config.SMTP_TIMEOUT_SECONDS,
        ) as smtp:
            smtp.starttls()
            smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("SMTP delivery to %s failed", to)
        raise EmailDeliveryError(str(exc)) from exc
