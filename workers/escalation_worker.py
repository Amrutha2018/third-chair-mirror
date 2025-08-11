import os
import datetime
import asyncio
import logging
from utils.postgres import POSTGRES
from utils.email_sender import send_outreach_email
from email.message import EmailMessage

logging.basicConfig(
    level=logging.INFO,  
    format="%(asctime)s [%(levelname)s] %(message)s",
)


EMAIL_TEMPLATE_DIR = "email_templates/"
Z_EMAIL_FROM = os.getenv("Z_EMAIL_FROM")
SHARED_DIR = os.getenv("SHARED_DIR", "/app/shared")

# Time thresholds
THRESHOLDS = {
    "REPLIED_BY_US": int(os.getenv("REPLY_TO_NUDGE_1_DAYS", 5)),
    "NUDGED_AGAIN": int(os.getenv("NUDGE_1_TO_NUDGE_2_DAYS", 5)),
    "LEGAL_LETTER_READY": int(os.getenv("NUDGE_2_TO_LEGAL_DAYS", 3)),
    "LEGAL_LETTER_SENT": int(os.getenv("LEGAL_TO_COURT_DAYS", 7))
}

# Escalation transitions
ESCALATION_MAP = {
    "REPLIED_BY_US": ("NUDGED_AGAIN", "replied_by_us_nudge_1.txt"),
    "NUDGED_AGAIN": ("LEGAL_LETTER_READY", "nudged_again_nudge_2.txt"),
    "LEGAL_LETTER_READY": ("LEGAL_LETTER_SENT", "legal_letter_ready.txt"),
    "LEGAL_LETTER_SENT": ("COURT_READY", "legal_letter_sent_final.txt")
}

SHARED_DIR = os.getenv("SHARED_DIR", "/app/shared")

def load_template(filename: str):
    path = os.path.join(SHARED_DIR, f"email_templates/{filename}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    subject_line, body = content.split("\n", 1)
    subject = subject_line.replace("Subject:", "").strip()
    return subject, body.strip()


async def escalate_contact(contact, current_status):
    contact_id = contact["id"]
    email = contact["email"]
    updated_at = contact["updated_at"]

    next_status, template_file = ESCALATION_MAP[current_status]
    subject, body = load_template(template_file)

    msg = EmailMessage()
    msg["To"] = email
    msg["From"] = Z_EMAIL_FROM
    msg["Subject"] = subject
    msg.set_content(body)

    logging.info(f"[ESCALATION] Sending {next_status} to {email}...")
    result = await send_outreach_email(msg)

    if result == True:
        await POSTGRES.execute("""
            UPDATE outreach_contacts
            SET status = $1, updated_at = now()
            WHERE id = $2
        """, (next_status, contact_id))
        logging.info(f"[ESCALATION] ✅ Updated status to {next_status} for {email}")
    else:
        logging.warning(f"[ESCALATION] ❌ Failed to send to {email}")


async def check_and_escalate():
    for status, (next_status, _) in ESCALATION_MAP.items():
        threshold_days = THRESHOLDS[status]
        cutoff_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=threshold_days)

        contacts = await POSTGRES.fetch_all("""
            SELECT id, email, updated_at FROM outreach_contacts
            WHERE status = $1 AND updated_at <= $2
            LIMIT 10
        """, (status, cutoff_time))
        if not contacts:
            logging.info(f"[ESCALATION] No contacts to escalate for status {status}.")
            continue
        logging.info(f"[ESCALATION] Found {len(contacts)} contacts to escalate for status {status}.")
        for contact in contacts:
            await escalate_contact(contact, status)


async def escalation_worker_loop():
    logging.info("[ESCALATION] Starting escalation worker loop...")
    while True:
        logging.info("[ESCALATION] Checking for contacts to escalate...")
        try:
            await check_and_escalate()
            await asyncio.sleep(30)
        except Exception as e:
            logging.exception(f"[ESCALATION] Error: {e}")
            await asyncio.sleep(120)


if __name__ == "__main__":
    asyncio.run(escalation_worker_loop())
