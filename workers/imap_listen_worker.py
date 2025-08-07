import os
import email
import asyncio
import datetime
import logging
from imapclient import IMAPClient
from email.header import decode_header
from utils.postgres import POSTGRES
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_PORT = int(os.getenv("IMAP_PORT", 993))
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASS = os.getenv("IMAP_PASS")

async def check_replies():
    logging.info("[IMAP] Connecting to mailbox...")
    with IMAPClient(IMAP_HOST, port=IMAP_PORT, use_uid=True, ssl=True) as client:
        client.login(IMAP_USER, IMAP_PASS)
        client.select_folder("INBOX")

        messages = client.search(['UNSEEN'])
        if not messages:
            logging.info("[IMAP] No new messages found.")
            return

        logging.info(f"[IMAP] Found {len(messages)} new messages.")

        for uid in messages:
            raw_msg = client.fetch([uid], ['RFC822'])[uid][b'RFC822']
            msg = email.message_from_bytes(raw_msg)

            from_email = email.utils.parseaddr(msg.get('From'))[1]
            subject = decode_header(msg.get('Subject'))[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode(errors='ignore')

            # Extract body
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors='ignore')
                        break
                else:
                    body = "[No text/plain part found]"
            else:
                body = msg.get_payload(decode=True).decode(errors='ignore')

            logging.info(f"[IMAP] Reply from: {from_email} | Subject: {subject}")

            # Update outreach_contacts if email matches
            query = """
            UPDATE outreach_contacts
            SET status = 'REPLIED',
                last_reply_text = $1,
                reply_received_at = $2,
                is_processing = false
            WHERE email = $3
            RETURNING id
            """
            updated = await POSTGRES.fetch_one(query, (body, datetime.datetime.now(datetime.timezone.utc), from_email))

            if updated:
                logging.info(f"[IMAP] ✅ Reply matched. Updated contact ID: {updated['id']}")
            else:
                logging.info(f"[IMAP] ⚠️ No matching contact found for: {from_email}")

            client.add_flags(uid, [r'\Seen'])
        client.logout()

async def start_imap_loop():
    logging.info("[IMAP] Starting IMAP listener...")
    while True:
        try:
            await check_replies()
            await asyncio.sleep(5)
        except Exception as e:
            logging.exception(f"[IMAP] Unexpected error: {e}")
            await asyncio.sleep(120)

if __name__ == "__main__":
    asyncio.run(start_imap_loop())