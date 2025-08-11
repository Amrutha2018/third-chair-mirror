from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
import os

router = APIRouter(tags=["Get File"])

SHARED_DIR = os.getenv("SHARED_DIR", "/app/shared")

@router.get("/files")
async def get_public_file(
    filename: str,
    type: str = Header(..., description="Type of file to retrieve (image or ots)"),
    x_api_key: str = Header(..., description="API Key for authentication")
):
    """
    Serve screenshot or OTS file by filename.
    Take file path from list drafts API
    """
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(SHARED_DIR, type, safe_filename)

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)
