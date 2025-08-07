from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from typing import Optional, List
from app.postgres import POSTGRES
import datetime
from uuid import UUID

router = APIRouter()

class DraftResponse(BaseModel):
    draft_id: UUID
    email: str
    reply_text: str
    draft_text: str
    llm_generated_at: datetime.datetime

@router.get("/drafts", response_model=List[DraftResponse])
async def list_drafts(limit: int = Query(10, ge=1, le=50),
                      x_api_key: str = Header(..., description="API Key for authentication")
                      ):
    rows = await POSTGRES.fetch_all("""
        SELECT pe.id AS draft_id, 
                oc.email, 
                pe.original_reply AS reply_text,
                pe.llm_draft as draft_text, 
                pe.created_at AS llm_generated_at
        FROM replies pe
        JOIN outreach_contacts oc ON oc.id = pe.contact_id
        WHERE pe.status = 'DRAFTED'
        ORDER BY pe.created_at ASC
        LIMIT $1
    """, (limit,))
    return [dict(row) for row in rows]

