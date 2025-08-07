from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.params import Header
from app.postgres import POSTGRES

router = APIRouter()

@router.post("/drafts/{draft_id}/reject")
async def reject_draft(
    draft_id: str = Path(..., description="UUID of the draft to reject"),
    x_api_key: str = Header(..., description="API Key for authentication")    
):
    updated = await POSTGRES.execute("""
        UPDATE personalized_emails
        SET status = 'REJECTED'
        WHERE id = $1 AND status = 'DRAFTED'
    """, (draft_id,))

    if updated == 0:
        raise HTTPException(status_code=404, detail="Draft not found or not in DRAFTED state")

    return {"status": "rejected", "draft_id": draft_id}
