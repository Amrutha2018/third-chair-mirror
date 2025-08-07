
import json
import logging
from uuid import UUID, uuid4
from datetime import datetime
import asyncpg
from fastapi.params import Header
from pydantic import BaseModel, Field
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.postgres import POSTGRES

router = APIRouter(tags=["create_filter"])


# --- Request model ---
class FilterOptions(BaseModel):
    include_domains: Optional[List[str]] = Field(default=None, description="Only crawl from these domains")
    exclude_domains: Optional[List[str]] = Field(default=None, description="Exclude results from these domains")

class CreateJobRequest(BaseModel):
    input_text: str
    filters: Optional[FilterOptions] = Field(default_factory=FilterOptions)
    test_email: Optional[str] = Field(default=None, description="If provided, all outreach emails will go to this test address")

# --- Response model ---
class CreateJobResponse(BaseModel):
    job_id: UUID
    status: str = "PENDING"
    created_at: datetime

# --- API Endpoint ---
@router.post("/jobs/create", response_model=CreateJobResponse)
async def create_job(
    req: CreateJobRequest,
    x_api_key: str = Header(...),
):
    """
    Create a new job and initialize its crawl event.

    - Accepts input text and optional filter parameters.
    - Generates a unique job ID (UUID) and stores the job in the `jobs` table with status 'PENDING'.
    - Immediately creates a corresponding 'CRAWL_READY' event in the `crawl_events` table.
    - Returns the job ID and creation timestamp.

    Raises:
    - 409 Conflict: If a job with the same UUID somehow exists (rare with auto-gen).
    - 500 Internal Server Error: For database or unexpected failures.
    """
    logger = logging.getLogger("create_job")
    logger.info(f"Received job creation request with input_text: {req.input_text}")
    
    job_id = str(uuid4())

    try:
        statements = [
            (
                "INSERT INTO jobs (id, input_text, filters, status) VALUES ($1, $2, $3, 'PENDING') RETURNING id, created_at",
                [job_id, req.input_text, json.dumps(req.filters.model_dump())],
                True
            ),
            (
                "INSERT INTO crawl_events (job_id) VALUES ($1) RETURNING id",
                [job_id],
                True
            )
        ]

        if req.test_email:
            statements.append((
                "INSERT INTO test_email_map (job_id, test_email) VALUES ($1, $2)",
                [job_id, req.test_email],
                False
            ))

        results = await POSTGRES.execute_transaction_with_results(statements)

        job_data = results[0]
        event_data = results[1]

        logger.info(f"Created job with ID: {job_data['id']} at {job_data['created_at']}")
        logger.info(f"Created job event with ID: {event_data['id']} for job ID: {job_data['id']} and event type: 'CRAWL_READY'")

        return CreateJobResponse(
            job_id=job_data["id"],
            created_at=job_data["created_at"]
        )

    except asyncpg.exceptions.UniqueViolationError as e:
        logger.error(f"Duplicate job ID error: {e}")
        raise HTTPException(status_code=409, detail="Job with this ID already exists.")

    except asyncpg.PostgresError as e:
        logger.exception("Database error during job creation")
        raise HTTPException(status_code=500, detail="Database error while creating job")

    except Exception as e:
        logger.exception("Unexpected error during job creation")
        raise HTTPException(status_code=500, detail="Unexpected server error")
