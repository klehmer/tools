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
    return {"configured": config_manager.is_configured()}


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
