import uvicorn
from decouple import config, UndefinedValueError
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.routes import master_router
from app.postgres import POSTGRES

import logging

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    await POSTGRES.init()
    setup_logging()
    logger = logging.getLogger("startup")
    logger.info("Starting FastAPI application")
    yield
    logger.info("Shutting down FastAPI application")
    await POSTGRES.close()

app = FastAPI(
    lifespan=lifespan,
    title="Third Chair Mirror",
    description="""
        ---

        ## 🌿 Third Chair Portfolio Demo

        **An end-to-end system to detect IP infringement, gather evidence, and automate respectful outreach — grounded in clarity, care, and lawful precision.**

        ---

        ### 🧭 Purpose

        This is not just a demo.
        It is a **reflection** of Third Chair’s own mission — to bring automation, scale, and strategy to in-house legal operations — without losing sight of truth, nuance, or human presence.

        ---

        ### 🔍 What This System Does

        1. **IP Infringement Detection**

        * Accepts a user-submitted text (poem, paragraph, product copy, etc.)
        * Crawls the web to detect possible content matches

        2. **Evidence Gathering**

        * Screenshots of the matched page
        * OTS-stamped tamper-proof evidence
        * Snippet of the matched content for review

        3. **Automated Outreach**

        * Emails are sent in staged sequences:

            * Initial gentle nudge
            * Follow-ups
            * Final legal letter
        * Email templates are customizable and human

        4. **LLM-Aware Reply System**

        * If a recipient replies, the system:

            * Logs the reply
            * Drafts a respectful follow-up using an LLM
            * Awaits human approval before sending

        5. **Court Escalation Flow**

        * If a case remains unresolved, it moves toward legal escalation
        * Human-readable logs + all evidence are bundled and shared with the client

        ---

        ### 🪶 Crafted With Presence

        * No spam.
        * No pressure.
        * Just **clear signals** and **truthful steps**, delivered with care.

        This system is not aggressive.
        It is **disciplined**, **attentive**, and **structured**,
        yet open to human review at every sensitive point.

        ---

        ### 🧪 Demo Mode (No Real Outreach Sent)

        To allow safe exploration:

        * Every job can include a **test email address**
        * All outreach and replies go **only** to this test inbox
        * Ideal for live demos and evaluation without disturbing real site owners

        ---

        ### 📚 Tech Stack

        * **FastAPI** – Lightweight backend for job submission and review
        * **PostgreSQL** – Event-driven, clear relational schema
        * **Async Workers** – Background outreach + escalation flows
        * **Zoho SMTP** – For real-world mail sending
        * **OpenRouter (LLM)** – Reply drafting that reflects tone + context
        * **OTS** – Tamper-proof timestamping of web matches

        ---

        ### 🧘 Why This Matters

        Legal tech often becomes noise:
        Too many tools, too many dashboards, too little clarity.

        This project is an offering —
        to show that **automation can serve presence**,
        and **scale can still honor care**.

        ---

        ### ✉️ One Last Thing

        This was not built to impress.

        It was built because I see the soul of what Third Chair is doing.
        And I wanted to meet that soul — not with promises, but with presence.

        If this resonates, I'm ready to build alongside you.

        ---
    """,
    version="1.0.0",
    docs_url="/docs",         
    redoc_url="/redoc", 
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_api_key(x_api_key: str = Header(...)):
    try:
        API_KEY = config("API_KEY")
    except UndefinedValueError:
        raise HTTPException(500, "Server misconfigured: API_KEY missing")
    if x_api_key != API_KEY:
        raise HTTPException(401, "Unauthorized")
    return True

app.include_router(
    master_router,
    prefix="/api/v1",
    dependencies=[Depends(verify_api_key)], 
)

if __name__ == "__main__":
    APP_PORT = config("APP_PORT", default=8000, cast=int)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=APP_PORT, 
        reload=True 
    )

# Use "python -m app.main" for running the app