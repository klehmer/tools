"""FastAPI app: Calendar & Email Summary."""
import os
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

load_dotenv()

import auth
import config_manager
import scheduler
from google_service import GoogleService
from summarizer import summarize_emails, summarize_events
import checklist


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start_scheduler()
    yield
    scheduler.stop_scheduler()


app = FastAPI(title="Calendar & Email Summary", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Dependencies ----
def get_session_token(x_session_token: Optional[str] = Header(None)) -> str:
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return x_session_token


def get_google(session_token: str = Depends(get_session_token)) -> GoogleService:
    creds = auth.get_credentials(session_token)
    if not creds:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return GoogleService(creds)


# ---- Config ----
@app.get("/config/status")
def config_status():
    return {
        "configured": config_manager.is_configured(),
        "google_configured": config_manager.is_google_configured(),
    }


@app.get("/config")
def get_config():
    return config_manager.get_config()


class ConfigUpdate(BaseModel):
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    AI_PROVIDER: Optional[str] = None
    AI_MODEL: Optional[str] = None
    DEFAULT_PERIOD: Optional[str] = None
    DEFAULT_DIRECTION: Optional[str] = None
    PLANNER_COLUMN_WIDTH: Optional[str] = None
    BACKEND_URL: Optional[str] = None
    FRONTEND_URL: Optional[str] = None


@app.get("/config/defaults")
def config_defaults():
    return {
        "period": os.getenv("DEFAULT_PERIOD", "week"),
        "direction": os.getenv("DEFAULT_DIRECTION", "past"),
        "provider": os.getenv("AI_PROVIDER", "anthropic"),
    }


@app.post("/config")
def update_config(update: ConfigUpdate):
    config_manager.save_config(update.model_dump(exclude_none=True))
    return {"ok": True}


# ---- Auth ----
@app.get("/auth/url")
def auth_url():
    return {"url": auth.get_auth_url()}


@app.get("/auth/callback")
def auth_callback(code: str, state: str):
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5174")
    try:
        token = auth.exchange_code(code, state)
        return RedirectResponse(f"{frontend}/?session_token={token}")
    except Exception as e:
        return RedirectResponse(f"{frontend}/?error=auth_failed&detail={str(e)[:200]}")


@app.post("/auth/logout")
def logout(session_token: str = Depends(get_session_token)):
    auth.delete_session(session_token)
    return {"ok": True}


@app.get("/auth/me")
def me(g: GoogleService = Depends(get_google)):
    return g.get_user_profile()


# ---- Summarization ----
@app.get("/summary/emails")
def email_summary(
    period: str = Query("week", pattern="^(day|week|month|quarter)$"),
    g: GoogleService = Depends(get_google),
):
    emails = g.fetch_emails(period=period, max_results=200)
    result = summarize_emails(emails, period)
    result["count"] = len(emails)
    result["period"] = period
    return result


@app.get("/summary/calendar")
def calendar_summary(
    period: str = Query("week", pattern="^(day|week|month|quarter)$"),
    direction: str = Query("future", pattern="^(past|future)$"),
    g: GoogleService = Depends(get_google),
):
    events = g.fetch_events(period=period, direction=direction)
    result = summarize_events(events, period, direction)
    result["count"] = len(events)
    result["period"] = period
    result["direction"] = direction
    return result


# ---- Scheduled Jobs ----
@app.get("/jobs")
def list_jobs():
    return scheduler.get_jobs()


@app.post("/jobs")
def create_job(body: dict):
    return scheduler.create_job(body)


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.put("/jobs/{job_id}")
def update_job(job_id: str, body: dict):
    job = scheduler.update_job(job_id, body)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    if not scheduler.delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}


@app.post("/jobs/{job_id}/run")
def run_job_now(job_id: str):
    job = scheduler.run_job_now(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, "message": "Job started"}


# ---- Reports ----
@app.get("/reports")
def list_reports(job_id: Optional[str] = None, limit: int = Query(50, le=200)):
    return scheduler.get_reports(job_id=job_id, limit=limit)


@app.get("/reports/{report_id}")
def get_report(report_id: str):
    report = scheduler.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.delete("/reports/{report_id}")
def delete_report(report_id: str):
    if not scheduler.delete_report(report_id):
        raise HTTPException(status_code=404, detail="Report not found")
    return {"ok": True}


# ---- Checklist / Planner ----
class ChecklistCreate(BaseModel):
    text: str
    date: str  # YYYY-MM-DD
    sort_order: int = 0
    priority: bool = False


class ChecklistUpdate(BaseModel):
    text: Optional[str] = None
    date: Optional[str] = None
    done: Optional[bool] = None
    sort_order: Optional[int] = None
    priority: Optional[bool] = None


class ChecklistReorder(BaseModel):
    item_ids: list[str]


@app.get("/checklist")
def get_checklist(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    done: Optional[bool] = None,
):
    return checklist.list_items(date_from=date_from, date_to=date_to, done=done)


@app.post("/checklist")
def create_checklist_item(body: ChecklistCreate):
    return checklist.create_item(
        text=body.text, item_date=body.date,
        sort_order=body.sort_order, priority=body.priority,
    )


@app.put("/checklist/{item_id}")
def update_checklist_item(item_id: str, body: ChecklistUpdate):
    item = checklist.update_item(item_id, body.model_dump())
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/checklist/reorder")
def reorder_checklist(body: ChecklistReorder):
    return checklist.reorder_items(body.item_ids)


@app.delete("/checklist/{item_id}")
def delete_checklist_item(item_id: str):
    if not checklist.delete_item(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}
