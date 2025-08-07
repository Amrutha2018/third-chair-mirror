import os
import aiosmtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")


async def send_outreach_email(msg) -> bool:

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASS,
            use_tls=True,
        )
        return True
    except aiosmtplib.SMTPRecipientsRefused as e:
        print(f"🚫 Invalid email: {e}")
        return "BOUNCED"
    except Exception as e:
        print(f"❌ Failed to send email : {e}")
        return "FAILED"


if __name__ == "__main__":
    import asyncio

    async def test():
        to = input("To email: ").strip()
        subject = "Test Mail from Thumbi 🐦"
        body = "This is a test email sent via Zoho SMTP using Thumbi's wings."
        await send_outreach_email(to, subject, body)

    asyncio.run(test())