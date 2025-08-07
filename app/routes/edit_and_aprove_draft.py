from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.params import Header, Query
from pydantic import BaseModel
from app.postgres import POSTGRES

from app.utils.send_email import send_outreach_email

router = APIRouter(tags=["Edit and Approve Drafts"])

class ApproveRequest(BaseModel):
    edited_text: Optional[str] = None

@router.post("/drafts/approve")
async def approve_and_send_draft(
    draft_id: str = Query(..., description="UUID of the draft to approve"),
    body: ApproveRequest = None,
    x_api_key: str = Header(..., description="API Key for authentication")
):
    """
    Approve and send an outreach email draft.

    This endpoint finalizes and sends a drafted outreach email. It allows optional editing of the draft before sending. 
    Once approved, the email is sent to the contact and the system updates the statuses accordingly.

    ### Query Parameters:
    - **draft_id** (`str`, required): UUID of the draft to approve. Must reference a reply with `status = 'DRAFTED'`.

    ### Headers:
    - **x-api-key** (`str`, required): API Key for authenticating the request.

    ### Request Body (optional):
    - **edited_text** (`str`, optional): Custom version of the draft text. If not provided, the original draft will be used.

    ### Behavior:
    - Fetches the draft content and associated contact email.
    - If found and in the correct status, sends the email (using `send_outreach_email`).
    - Updates:
        - `replies.status` to `'SENT'`
        - `outreach_contacts.status` to `'REPLIED_BY_US'` with a new `updated_at` timestamp.
    - If the draft is not found or already sent, returns a 404 error.

    ### Response:
    ```json
    {
    "status": "sent",
    "email": "recipient@example.com"
    }
    """
    row = await POSTGRES.fetch_one("""
        SELECT pe.llm_draft as draft_text, oc.email, pe.contact_id as outreach_contact_id
        FROM replies pe
        JOIN outreach_contacts oc ON oc.id = pe.contact_id
        WHERE pe.id = $1 AND pe.status = 'DRAFTED'
    """, (draft_id,))

    if not row:
        raise HTTPException(status_code=404, detail="Draft not found or already sent")

    final_text = body.edited_text.strip() if body and body.edited_text else row["draft_text"]

    await send_outreach_email(row["email"], final_text)

    await POSTGRES.execute(
        "UPDATE replies SET status = 'SENT' WHERE id = $1",
        (draft_id,)
    )

    await POSTGRES.execute(
        "UPDATE outreach_contacts SET status = 'REPLIED_BY_US', updated_at = now() WHERE id = $1",
        (row["outreach_contact_id"],)
    )

    return {"status": "sent", "email": row["email"]}
