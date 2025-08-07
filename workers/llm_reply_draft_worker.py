import os
import logging
import datetime
import asyncio
from utils.postgres import POSTGRES
from utils.llm import generate_followup_reply  # your LLM wrapper


logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

async def draft_llm_followups():
    logging.info("[LLM] Looking for replied contacts without drafts...")

    # Step 1: Find REPLIED contacts with no replies yet
    contacts = await POSTGRES.fetch_all("""
        SELECT oc.id as contact_id, oc.email, oc.last_reply_text, cr.matched_snippet
        FROM outreach_contacts oc
        LEFT JOIN replies pe ON pe.contact_id = oc.id
        LEFT JOIN crawl_results cr ON cr.id = oc.crawl_result_id
        WHERE oc.status = 'REPLIED' AND (pe.id IS NULL or pe.status != 'DRAFTED')
        LIMIT 10
    """)

    for c in contacts:
        reply_text = c["last_reply_text"]
        matched_snippet = c["matched_snippet"] or ""
        email = c["email"]
        contact_id = c["contact_id"]
        if not reply_text or reply_text.lower().startswith("on ") or "auto-reply" in reply_text.lower():
            reply_text = "The user didn't write anything meaningful. It may be an automatic response or an empty reply."

        prompt = f"""
        You are a respectful legal assistant following up with a site owner.

        We previously contacted them about content that resembles material under our intellectual property rights.

        ---

        🔹 Here's the snippet of content we flagged:
        \"\"\"
        {matched_snippet.strip()}
        \"\"\"

        🔹 Here's their reply (if any):
        \"\"\"
        {reply_text.strip()}
        \"\"\"

        Now please write a follow-up email. Keep it polite, professional, and brief. Do not sound robotic or threatening. Use a human tone. Use only plain English.

        End with: “Best regards,\nThird Chair Bot”
        """

        logging.info(f"[LLM] Drafting for contact {email}")
        draft = await generate_followup_reply(prompt)
        now = datetime.datetime.now(datetime.timezone.utc)
        await POSTGRES.execute("""
            INSERT INTO replies (
                contact_id, original_reply, llm_draft, created_at, updated_at, status
            ) VALUES ($1, $2, $3, $4, $5, $6)
        """, (contact_id, reply_text, draft.strip() ,now, now, 'DRAFTED' ))

        logging.info(f"[LLM] Draft saved for contact {email}")

async def run_drafter_periodically():
    logging.info("[LLM] Starting periodic drafter loop...")
    while True:
        logging.info("[LLM] Drafting follow-up replies...")
        try:
            await draft_llm_followups()
        except Exception as e:
            logging.exception(f"[LLM] Error while drafting replies: {e}")
        await asyncio.sleep(5)  # 5 minutes

if __name__ == "__main__":
    asyncio.run(run_drafter_periodically())