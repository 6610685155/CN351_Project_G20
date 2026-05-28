import requests
from django.conf import settings

MAILERSEND_API_URL = "https://api.mailersend.com/v1/email"


def send_email(to_email, subject, text_content):
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
