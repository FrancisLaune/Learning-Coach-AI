"""Authentication email delivery with safe local-development modes."""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from core.config import (
    get_auth_email_from_address,
    get_auth_email_mode,
    get_auth_email_output_dir,
    get_smtp_settings,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EmailDeliveryResult:
    delivered: bool
    mode: str
    detail: str


def deliver_auth_email(*, recipient: str, subject: str, body: str) -> EmailDeliveryResult:
    mode = get_auth_email_mode()
    if mode == "disabled":
        return EmailDeliveryResult(False, mode, "email delivery disabled")
    if mode == "console":
        LOGGER.info("AUTH EMAIL to=%s subject=%s\n%s", recipient, subject, body)
        print(f"[AUTH EMAIL] to={recipient}\nSubject: {subject}\n{body}")
        return EmailDeliveryResult(True, mode, "logged to console")
    if mode == "file":
        output_dir = get_auth_email_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = recipient.replace("@", "_at_").replace("/", "_")
        path = output_dir / f"{safe_name}.txt"
        path.write_text(f"To: {recipient}\nSubject: {subject}\n\n{body}", encoding="utf-8")
        return EmailDeliveryResult(True, mode, str(path))
    if mode == "smtp":
        host, port, username, password, use_tls = get_smtp_settings()
        if not host:
            return EmailDeliveryResult(False, mode, "smtp host not configured")
        message = EmailMessage()
        message["From"] = get_auth_email_from_address()
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(host, port, timeout=20) as client:
            if use_tls:
                client.starttls()
            if username and password:
                client.login(username, password)
            client.send_message(message)
        return EmailDeliveryResult(True, mode, "sent via smtp")
    return EmailDeliveryResult(False, mode, f"unsupported mode {mode}")
