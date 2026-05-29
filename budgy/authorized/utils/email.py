import os
import requests
from django.conf import settings


MAILERSEND_API_URL = "https://api.mailersend.com/v1/email"


def send_email(to_email, subject, text_content):
    """
    Send an email. Uses local SMTP when USE_LOCAL_SMTP is set (for testing
    with the mock email server), otherwise falls back to the MailerSend API.
    """

    # ── Local SMTP mode (for vul4 testing) ──
    if getattr(settings, "USE_LOCAL_SMTP", False):
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(text_content)
        msg["Subject"] = subject
        msg["From"] = settings.DEFAULT_FROM_EMAIL
        msg["To"] = to_email

        smtp_host = getattr(settings, "EMAIL_HOST", "127.0.0.1")
        smtp_port = getattr(settings, "EMAIL_PORT", 1025)

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.send_message(msg)

        return

    # ── MailerSend API mode (production) ──
    headers = {
        "Authorization": f"Bearer {settings.MAILERSEND_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "from": {
            "email": settings.DEFAULT_FROM_EMAIL,
            "name": "Budgy: Manage Your Finances",
        },
        "to": [
            {
                "email": to_email,
            }
        ],
        "subject": subject,
        "text": text_content,
    }

    response = requests.post(MAILERSEND_API_URL, json=data, headers=headers, timeout=10)

    response.raise_for_status()
