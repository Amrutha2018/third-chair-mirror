import os
import smtplib
import logging
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
Z_EMAIL_FROM = os.getenv("Z_EMAIL_FROM", SMTP_USER)

async def send_email(to_email: str, subject: str, body: str):
    msg = EmailMessage()
    msg["From"] = Z_EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        logging.info(f"[EMAIL] ✅ Sent email to {to_email}")
    except Exception as e:
        logging.exception(f"[EMAIL] ❌ Failed to send email to {to_email}: {e}")
