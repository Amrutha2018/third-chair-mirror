from fastapi import APIRouter

from app.routes.create_jobs import router as create_filter_router
from app.routes.edit_and_aprove_draft import router as edit_and_approve_draft_router
from app.routes.get_file import router as get_file_router
from app.routes.list_drafts import router as list_drafts_router
from app.routes.reject_drafts import router as reject_drafts_router

master_router = APIRouter()

master_router.include_router(create_filter_router)
master_router.include_router(edit_and_approve_draft_router)
master_router.include_router(get_file_router)
master_router.include_router(list_drafts_router)
master_router.include_router(reject_drafts_router)