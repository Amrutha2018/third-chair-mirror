import os
import asyncio
import datetime
from utils.postgres import POSTGRES  # asyncpg wrapper
from utils.send_email_with_template import send_email_with_template  # your SMTP function
import logging

logging.basicConfig(
    level=logging.INFO,  # Show INFO and above
    format="%(asctime)s [%(levelname)s] %(message)s",
)

STATUS_SEQUENCE = [
    ("NOT_CONTACTED", "SENT_1ST_MAIL", int(os.getenv("MAIL_1_DELAY_DAYS", 0))),
    ("SENT_1ST_MAIL", "SENT_2ND_MAIL", int(os.getenv("MAIL_2_DELAY_DAYS", 3))),
    ("SENT_2ND_MAIL", "SENT_3RD_MAIL", int(os.getenv("MAIL_3_DELAY_DAYS", 6))),
    ("SENT_3RD_MAIL", "SENT_4TH_MAIL", int(os.getenv("MAIL_4_DELAY_DAYS", 10))),
    ("SENT_4TH_MAIL", "LEGAL_LETTER_READY", int(os.getenv("LEGAL_DELAY_DAYS", 14))),
]


async def process_contact(contact: dict):
    contact_id = contact["id"]
    email = contact["email"]
    logging.info(f"[OUTREACH] Processing contact {contact_id} for email {email}...")
    try:
        await send_email_with_template(contact)
    except Exception as e:
        print(f"[ERROR] Failed for {email}: {e}")
        await POSTGRES.execute("""
            UPDATE outreach_contacts
            SET is_processing = false, updated_at = now()
            WHERE id = $1
        """, (contact_id,))


async def outreach_worker_loop():
    logging.info("[OUTREACH] Starting outreach worker loop...")
    while True:
        now = datetime.datetime.now(datetime.timezone.utc)

        for current_status, next_status, delay_days in STATUS_SEQUENCE:
            cutoff = now - datetime.timedelta(minutes=delay_days)

            contacts = await POSTGRES.fetch_all("""
                SELECT * FROM outreach_contacts
                WHERE status = $1 AND updated_at <= $2 AND is_processing = false
                ORDER BY updated_at ASC
                LIMIT 20
            """, (current_status, cutoff))
            if not contacts:
                logging.info(f"[OUTREACH] No contacts to process for status {current_status}.")
                continue
            logging.info(f"[OUTREACH] Processing {len(contacts)} contacts for status {current_status}...")
            for contact in contacts:
                contact_id = contact["id"]

                # Lock the contact
                await POSTGRES.execute("""
                    UPDATE outreach_contacts
                    SET is_processing = true
                    WHERE id = $1
                """, (contact_id,))

                asyncio.create_task(process_contact(contact))

        await asyncio.sleep(5)  # sleep for 5 minutes


if __name__ == "__main__":
    asyncio.run(outreach_worker_loop())
