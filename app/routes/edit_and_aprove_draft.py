from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.params import Header
from pydantic import BaseModel
from app.postgres import POSTGRES

from app.utils.send_email import send_outreach_email

router = APIRouter()

class ApproveRequest(BaseModel):
    edited_text: Optional[str] = None

@router.post("/drafts/{draft_id}/approve")
async def approve_and_send_draft(
    draft_id: str = Path(..., description="UUID of the draft to approve"),
    body: ApproveRequest = None,
    x_api_key: str = Header(..., description="API Key for authentication")
):
    row = await POSTGRES.fetch_one("""
        SELECT pe.llm_draft as draft_text, oc.email, pe.contact_id as outreach_contact_id
        FROM replies pe
        JOIN outreach_contacts oc ON oc.id = pe.contact_id
        WHERE pe.id = $1 AND pe.status = 'DRAFTED'
    """, (draft_id,))

    if not row:
        raise HTTPException(status_code=404, detail="Draft not found or already sent")

    final_text = body.edited_text.strip() if body and body.edited_text else row["draft_text"]

    # Send email
    await send_outreach_email(row["email"], final_text)

    # Update statuses
    await POSTGRES.execute(
        "UPDATE replies SET status = 'SENT' WHERE id = $1",
        (draft_id,)
    )

    await POSTGRES.execute(
        "UPDATE outreach_contacts SET status = 'REPLIED_BY_US', updated_at = now() WHERE id = $1",
        (row["outreach_contact_id"],)
    )

    return {"status": "sent", "email": row["email"]}
