import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import Settings


class EmailDeliveryUnavailable(RuntimeError):
    pass


async def send_report_email(
    settings: Settings,
    *,
    recipient: str,
    title: str,
    report_url: str,
    expires_in_seconds: int,
) -> None:
    if not settings.smtp_enabled or not settings.smtp_host or not settings.smtp_from_email:
        raise EmailDeliveryUnavailable("Report email is not configured.")

    message = EmailMessage()
    message["Subject"] = f"Your VitaPulse report: {title}"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(
        f"Your requested VitaPulse report is ready.\n\n"
        f"Open the private report link: {report_url}\n"
        f"This link expires in {expires_in_seconds // 60} minutes. Do not forward it."
    )
    await asyncio.to_thread(_send, settings, message)


def _send(settings: Settings, message: EmailMessage) -> None:
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
            client.ehlo()
            if settings.smtp_use_tls:
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise EmailDeliveryUnavailable("Report email could not be delivered.") from error
