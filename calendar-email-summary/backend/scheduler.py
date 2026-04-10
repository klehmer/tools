"""Scheduled job management with APScheduler."""
import json
import logging
import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import auth
from google_service import GoogleService
from summarizer import summarize_emails, summarize_events

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent / "data"
_JOBS_FILE = _DATA_DIR / "scheduled_jobs.json"
_REPORTS_DIR = _DATA_DIR / "reports"
_DATA_DIR.mkdir(exist_ok=True)
_REPORTS_DIR.mkdir(exist_ok=True)

_scheduler: Optional[BackgroundScheduler] = None


# ---------------------------------------------------------------------------
# Job storage
# ---------------------------------------------------------------------------

def _load_jobs() -> list[dict]:
    if not _JOBS_FILE.exists():
        return []
    try:
        return json.loads(_JOBS_FILE.read_text())
    except Exception:
        return []


def _save_jobs(jobs: list[dict]) -> None:
    _JOBS_FILE.write_text(json.dumps(jobs, indent=2, default=str))


def get_jobs() -> list[dict]:
    return _load_jobs()


def get_job(job_id: str) -> Optional[dict]:
    for j in _load_jobs():
        if j["id"] == job_id:
            return j
    return None


def create_job(data: dict) -> dict:
    job = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", "Untitled Job"),
        "enabled": data.get("enabled", True),
        "schedule": data.get("schedule", {"type": "daily", "time": "08:00"}),
        "tasks": data.get("tasks", []),
        "notification": data.get("notification", {"enabled": False, "style": "banner"}),
        "session_token": data.get("session_token", ""),
        "created_at": datetime.now().isoformat(),
        "last_run": None,
        "last_status": None,
        "last_message": "",
    }
    jobs = _load_jobs()
    jobs.append(job)
    _save_jobs(jobs)
    if job["enabled"]:
        _schedule_job(job)
    return job


def update_job(job_id: str, updates: dict) -> Optional[dict]:
    jobs = _load_jobs()
    for i, j in enumerate(jobs):
        if j["id"] == job_id:
            _unschedule_job(job_id)
            # Apply updates but protect internal fields
            for key in ("name", "enabled", "schedule", "tasks", "notification", "session_token"):
                if key in updates:
                    j[key] = updates[key]
            jobs[i] = j
            _save_jobs(jobs)
            if j.get("enabled", True):
                _schedule_job(j)
            return j
    return None


def delete_job(job_id: str) -> bool:
    jobs = _load_jobs()
    new_jobs = [j for j in jobs if j["id"] != job_id]
    if len(new_jobs) == len(jobs):
        return False
    _unschedule_job(job_id)
    _save_jobs(new_jobs)
    return True


# ---------------------------------------------------------------------------
# APScheduler lifecycle
# ---------------------------------------------------------------------------

def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.start()
    for job in _load_jobs():
        if job.get("enabled", True):
            _schedule_job(job)
    logger.info("Scheduler started with %d jobs", len(_load_jobs()))


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")


def _build_trigger(schedule: dict) -> CronTrigger:
    stype = schedule.get("type", "daily")
    time_str = schedule.get("time", "08:00")
    hour, minute = (int(x) for x in time_str.split(":"))

    if stype == "hourly":
        return CronTrigger(minute=minute)
    elif stype == "daily":
        return CronTrigger(hour=hour, minute=minute)
    elif stype == "weekdays":
        return CronTrigger(day_of_week="mon-fri", hour=hour, minute=minute)
    elif stype == "weekly":
        dow = schedule.get("day_of_week", "mon")
        return CronTrigger(day_of_week=dow, hour=hour, minute=minute)
    elif stype == "monthly":
        dom = schedule.get("day_of_month", 1)
        return CronTrigger(day=dom, hour=hour, minute=minute)
    else:
        return CronTrigger(hour=hour, minute=minute)


def _schedule_job(job: dict) -> None:
    if _scheduler is None:
        return
    trigger = _build_trigger(job.get("schedule", {}))
    _scheduler.add_job(
        _execute_job,
        trigger=trigger,
        id=job["id"],
        args=[job["id"]],
        replace_existing=True,
        misfire_grace_time=3600,
    )


def _unschedule_job(job_id: str) -> None:
    if _scheduler is None:
        return
    try:
        _scheduler.remove_job(job_id)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Job execution
# ---------------------------------------------------------------------------

def _execute_job(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return

    session_token = job.get("session_token")
    if not session_token:
        _update_job_status(job_id, "error", "No session token configured")
        return

    creds = auth.get_credentials(session_token)
    if not creds:
        _update_job_status(job_id, "error", "Session expired — please re-authenticate and update the job")
        return

    try:
        google = GoogleService(creds)
        results: dict = {}

        for task in job.get("tasks", []):
            task_type = task.get("type")
            period = task.get("period", "week")

            if task_type == "email":
                emails = google.fetch_emails(period=period, max_results=200)
                result = summarize_emails(emails, period)
                result["count"] = len(emails)
                result["period"] = period
                results["email"] = result

            elif task_type == "calendar":
                direction = task.get("direction", "future")
                events = google.fetch_events(period=period, direction=direction)
                result = summarize_events(events, period, direction)
                result["count"] = len(events)
                result["period"] = period
                result["direction"] = direction
                results["calendar"] = result

        report = _save_report(job, results)
        _update_job_status(job_id, "success")

        notification = job.get("notification", {})
        if notification.get("enabled", False):
            _send_notification(job, results, notification)

    except Exception as e:
        logger.exception("Job %s failed", job_id)
        _update_job_status(job_id, "error", str(e)[:500])


def _update_job_status(job_id: str, status: str, message: str = "") -> None:
    jobs = _load_jobs()
    for j in jobs:
        if j["id"] == job_id:
            j["last_run"] = datetime.now().isoformat()
            j["last_status"] = status
            j["last_message"] = message
            break
    _save_jobs(jobs)


def run_job_now(job_id: str) -> Optional[dict]:
    """Run a job immediately in a background thread. Returns the job or None."""
    job = get_job(job_id)
    if not job:
        return None
    Thread(target=_execute_job, args=(job_id,), daemon=True).start()
    return job


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def _save_report(job: dict, results: dict) -> dict:
    report = {
        "id": str(uuid.uuid4()),
        "job_id": job["id"],
        "job_name": job.get("name", "Unnamed Job"),
        "created_at": datetime.now().isoformat(),
        "results": results,
    }
    report_file = _REPORTS_DIR / f"{report['id']}.json"
    report_file.write_text(json.dumps(report, indent=2, default=str))
    return report


def get_reports(job_id: Optional[str] = None, limit: int = 50) -> list[dict]:
    """Return reports, newest first. Optionally filter by job_id."""
    reports: list[dict] = []
    if not _REPORTS_DIR.exists():
        return reports
    for f in sorted(_REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            report = json.loads(f.read_text())
            if job_id and report.get("job_id") != job_id:
                continue
            reports.append(report)
            if len(reports) >= limit:
                break
        except Exception:
            continue
    return reports


def get_report(report_id: str) -> Optional[dict]:
    report_file = _REPORTS_DIR / f"{report_id}.json"
    if not report_file.exists():
        return None
    try:
        return json.loads(report_file.read_text())
    except Exception:
        return None


def delete_report(report_id: str) -> bool:
    report_file = _REPORTS_DIR / f"{report_id}.json"
    if not report_file.exists():
        return False
    report_file.unlink()
    return True


# ---------------------------------------------------------------------------
# macOS notifications
# ---------------------------------------------------------------------------

def _send_notification(job: dict, results: dict, notification: dict) -> None:
    style = notification.get("style", "banner")
    title = job.get("name", "Summary Report")

    parts: list[str] = []
    if "email" in results:
        r = results["email"]
        parts.append(f"Emails ({r.get('count', 0)}): {r.get('summary', '')[:120]}")
    if "calendar" in results:
        r = results["calendar"]
        parts.append(f"Calendar ({r.get('count', 0)}): {r.get('summary', '')[:120]}")

    body = "\n".join(parts) if parts else "Report generated successfully."

    try:
        if style == "popup":
            escaped_body = body.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
            script = (
                f'display dialog "{escaped_body}" '
                f'with title "{escaped_title}" '
                f'buttons {{"OK"}} default button "OK"'
            )
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=300)
        else:
            escaped_body = body.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " | ")
            escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
            script = f'display notification "{escaped_body}" with title "{escaped_title}"'
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
    except Exception:
        logger.exception("Failed to send macOS notification")
