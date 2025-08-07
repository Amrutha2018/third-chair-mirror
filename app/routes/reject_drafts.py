from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.params import Header
from app.postgres import POSTGRES

router = APIRouter(tags=["Reject Drafts"])

@router.post("/drafts/reject")
async def reject_draft(
    draft_id: str = Query(..., description="UUID of the draft to reject"),
    x_api_key: str = Header(..., description="API Key for authentication")    
):  
    """
    Reject a drafted LLM-generated outreach reply.

    This endpoint allows you to mark a specific draft as rejected. It updates the draft’s status 
    from `DRAFTED` to `REJECTED` in the database. Rejected drafts will not be sent and are considered finalized decisions.

    ### Query Parameters:
    - **draft_id** (`str`, required): The UUID of the draft to be rejected.

    ### Headers:
    - **x-api-key** (`str`, required): API Key used to authenticate the request.

    ### Behavior:
    - Only drafts currently in `DRAFTED` state are eligible for rejection.
    - If the draft is not found or already processed, a `404 Not Found` error is returned.

    ### Response:
    A JSON object indicating the rejection status:
    ```json
    {
    "status": "rejected",
    "draft_id": "e9d7c2b6-2c4f-4bbf-b3f1-f23a7b1f42d0"
    }
    """
    updated = await POSTGRES.execute("""
        UPDATE personalized_emails
        SET status = 'REJECTED'
        WHERE id = $1 AND status = 'DRAFTED'
    """, (draft_id,))

    if updated == 0:
        raise HTTPException(status_code=404, detail="Draft not found or not in DRAFTED state")

    return {"status": "rejected", "draft_id": draft_id}
