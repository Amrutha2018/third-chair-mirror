import os
import asyncio
import logging
from utils.postgres import POSTGRES
from utils.email_sender import send_outreach_email
from datetime import datetime
from email.message import EmailMessage
import mimetypes

Z_EMAIL_FROM = os.getenv("Z_EMAIL_FROM")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def file_exists(path: str) -> bool:
    return os.path.isfile(path) and os.path.getsize(path) > 0

def build_email_message(to: str, subject: str, body: str, attachments: list[str] = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = Z_EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    if attachments:
        for file_path in attachments:
            mime_type, _ = mimetypes.guess_type(file_path)
            maintype, subtype = mime_type.split("/") if mime_type else ("application", "octet-stream")

            with open(file_path, "rb") as f:
                file_data = f.read()
                file_name = os.path.basename(file_path)
                msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=file_name)

    return msg

async def send_court_ready_email(contact):
    contact_email = contact["email"]
    crawl_result_id = contact["crawl_result_id"]
    job_id = contact["job_id"]

    crawl_result = await POSTGRES.fetch_one("""
        SELECT url, screenshot_path, ots_path, matched_snippet
        FROM crawl_results
        WHERE id = $1
    """, (crawl_result_id,))

    if not crawl_result:
        logging.warning(f"No crawl result found for contact {contact['id']}")
        return

    screenshot_path = crawl_result["screenshot_path"]
    ots_path = crawl_result["ots_path"]
    url = crawl_result["url"]
    snippet = crawl_result["matched_snippet"] or "<No snippet captured>"

    subject = f"New court-ready case: {url}"
    body = f"""
    Dear Client,

    A contact has reached COURT_READY status.

    Details:
    Email: {contact_email}
    URL: {url}
    Snippet: {snippet}

    Please find attached the screenshot and OTS timestamp.

    Regards,
    Third Chair Bot
    """

    attachments = []
    if file_exists(screenshot_path):
        attachments.append(screenshot_path)
    if file_exists(ots_path):
        attachments.append(ots_path)

    msg = build_email_message(to=contact_email, subject=subject, body=body, attachments=attachments)

    success = await send_outreach_email(msg)

    if success:
        await POSTGRES.execute("""
            UPDATE jobs SET status = 'COURT_NOTICE_SENT', updated_at = now() WHERE id = $1
        """, [job_id])
        await POSTGRES.execute("""
            UPDATE outreach_contacts
            SET status = 'COURT_NOTICE_SENT', is_processing = false, updated_at = now()
            WHERE id = $1
        """, [contact["id"]])
    else:
        logging.error(f"[COURT] Failed to notify client for contact={contact['id']}")


async def court_ready_worker():
    logging.info("[COURT] Starting court-ready monitor...")

    while True:
        logging.info("[COURT] Checking for court-ready contacts...")
        try:
            contacts = await POSTGRES.fetch_all("""
                SELECT * FROM outreach_contacts
                WHERE status = 'COURT_READY' AND is_processing = false
                LIMIT 5
            """)

            if not contacts:
                logging.info("[COURT] No court-ready contacts found. Retrying in 30 seconds...")
                await asyncio.sleep(30)
                continue
            logging.info(f"[COURT] Found {len(contacts)} court-ready contacts.")
            for contact in contacts:
                await POSTGRES.execute("""
                    UPDATE outreach_contacts SET is_processing = true WHERE id = $1
                """, [contact["id"]])

                try:
                    await send_court_ready_email(contact)
                except Exception as e:
                    logging.error(f"[COURT] Failed to process contact {contact['id']}: {e}")
                    await POSTGRES.execute("""
                        UPDATE outreach_contacts SET is_processing = false WHERE id = $1
                    """, [contact["id"]])

        except Exception as e:
            logging.exception(f"[COURT] Worker error: {e}")
            await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(court_ready_worker())
