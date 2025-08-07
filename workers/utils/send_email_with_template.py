import os
from email.message import EmailMessage
from utils.email_sender import send_outreach_email
from utils.postgres import POSTGRES
import datetime
import logging

TEMPLATE_DIR = "/Users/amruthae/Personal/Third Chair/Browser-agent/third-chair-mirror/outreach/email_templates"

STATUS_SEQUENCE = [
    ("NOT_CONTACTED", "SENT_1ST_MAIL"),
    ("SENT_1ST_MAIL", "SENT_2ND_MAIL"),
    ("SENT_2ND_MAIL", "SENT_3RD_MAIL"),
    ("SENT_3RD_MAIL", "SENT_4TH_MAIL"),
    ("SENT_4TH_MAIL", "LEGAL_LETTER_READY"),
    ("LEGAL_LETTER_READY", "COURT_READY")
]

SHARED_DIR = os.getenv("SHARED_DIR", "/app/shared")

def get_next_status(current_status: str) -> str:
    for curr, nxt in STATUS_SEQUENCE:
        if curr == current_status:
            return nxt
    return None

async def send_email_with_template(
        contact: dict,
):
    status = contact["status"]
    contact_id = contact["id"]
    to_email = contact["email"]
    crawl_result_id = contact["crawl_result_id"]
    # 1. Load the template
    next_status = get_next_status(status)
    template_path = os.path.join(SHARED_DIR, f"email_templates/{next_status.lower()}.txt")
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found for status: {next_status}")

    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "Subject:" not in content:
        raise ValueError("Template must start with 'Subject:'")

    subject_line, body = content.split("\n", 1)
    subject = subject_line.replace("Subject:", "").strip()

    # 3. Fetch screenshot_path, ots_path, snippet
    crawl_row = await POSTGRES.fetch_one("""
        SELECT screenshot_path, ots_path, matched_snippet
        FROM crawl_results
        WHERE id = $1
    """, (crawl_result_id,))

    if not crawl_row:
        raise ValueError("Crawl result not found.")

    screenshot_path = crawl_row["screenshot_path"]
    ots_path = crawl_row["ots_path"]
    snippet = crawl_row["matched_snippet"] or "No snippet available."

    # 4. Compose email
    msg = EmailMessage()
    msg["To"] = to_email
    msg["From"] = os.getenv("Z_EMAIL_FROM")
    msg["Subject"] = subject

    full_body = (
        f"{body.strip()}\n\n"
        f"---\nMatched Content Snippet:\n\"{snippet.strip()}\"\n\n"
        f"Timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}"
    )
    msg.set_content(full_body)

    # 5. Attach files
    for filepath, label in [(screenshot_path, "screenshot.png"), (ots_path, "evidence.ots")]:
        if filepath and os.path.exists(filepath):
            with open(filepath, "rb") as f:
                file_data = f.read()
                maintype, subtype = "application", "octet-stream"
                msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=label)
        else:
            print(f"[WARN] Missing attachment: {filepath}")

    # 6. Send the email 
    send_result = await send_outreach_email(msg) 
    if send_result == "BOUNCED":
        await POSTGRES.execute("""
            UPDATE outreach_contacts
            SET status = 'BOUNCED', is_processing = false, updated_at = now()
            WHERE id = $1
        """, (contact_id,))
        return
    elif send_result == "FAILED":
        logging.error(f"[OUTREACH] Failed to send email to {to_email}.")
        await POSTGRES.execute("""
            UPDATE outreach_contacts
            SET status = 'FAILED', is_processing = false, updated_at = now()
            WHERE id = $1
        """, (contact_id,))
        return
    elif send_result is True:
        # Email was successfully sent → update to next stage
        logging.info(f"[OUTREACH] Email sent to {to_email} for status {status}.")
        final_status = get_next_status(status)

        await POSTGRES.execute("""
            UPDATE outreach_contacts
            SET status = $1, is_processing = false, updated_at = now()
            WHERE id = $2
        """, (final_status, contact_id))