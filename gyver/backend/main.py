"""FastAPI app: Gyver."""
import asyncio
import os
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

load_dotenv()

import config_manager

# Decode multiline env vars that load_dotenv read as raw escaped strings
for _f in config_manager._MULTILINE_FIELDS:
    _raw = os.getenv(_f, "")
    if _raw:
        os.environ[_f] = config_manager._decode_multiline(_f, _raw)

import auth
import scheduler
from google_service import GoogleService
from summarizer import summarize_emails, summarize_events
import analytics
import checklist
import claude_mcp_service
import notes
import links
import app_launcher
import agents
import artifacts
import slack_notifier


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start_scheduler()
    yield
    scheduler.stop_scheduler()
    agents.kill_all()


app = FastAPI(title="Gyver", lifespan=lifespan)

# The frontend talks to us through the Vite proxy; only it (and direct
# localhost use) should be able to read responses such as /auth/restore.
ALLOWED_ORIGINS = [
    os.getenv("FRONTEND_URL", "http://localhost:5174"),
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Dependencies ----
def get_session_token(x_session_token: Optional[str] = Header(None)) -> str:
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return x_session_token


def get_google(session_token: str = Depends(get_session_token)):
    if session_token == claude_mcp_service.SESSION_TOKEN:
        if not claude_mcp_service.available():
            raise HTTPException(status_code=401, detail="Claude CLI not available")
        return claude_mcp_service.ClaudeMcpService()
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
        "ai_configured": config_manager.is_ai_configured(),
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
    DEFAULT_TAB: Optional[str] = None
    EMAIL_PROMPT_RULES: Optional[str] = None
    CALENDAR_PROMPT_RULES: Optional[str] = None
    SLACK_WEBHOOK_URL: Optional[str] = None
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


@app.get("/auth/restore")
def auth_restore():
    """Hand the frontend a working session without a new Google sign-in.

    Prefers a stored Google session; falls back to the Claude connectors.
    """
    token = auth.latest_valid_session()
    if token:
        return {"session_token": token, "source": "google"}
    if claude_mcp_service.available():
        return {"session_token": claude_mcp_service.SESSION_TOKEN, "source": "claude_mcp"}
    raise HTTPException(status_code=404, detail="No session to restore")


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
    direction: str = Query("future", pattern="^(past|current|future)$"),
    g: GoogleService = Depends(get_google),
):
    events = g.fetch_events(period=period, direction=direction)
    result = summarize_events(events, period, direction)
    result["count"] = len(events)
    result["period"] = period
    result["direction"] = direction
    return result


# ---- Slack ----
class SlackSendRequest(BaseModel):
    summary: dict
    mode: str  # "emails" or "calendar"
    period: str
    direction: Optional[str] = None


@app.post("/slack/send")
def slack_send(body: SlackSendRequest):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="Slack webhook URL not configured. Add it in Settings.")
    payload = slack_notifier.format_summary_for_slack(
        body.summary, body.mode, body.period, body.direction,
    )
    if not slack_notifier.send_to_slack(webhook_url, payload):
        raise HTTPException(status_code=502, detail="Failed to send to Slack. Check your webhook URL.")
    return {"ok": True}


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


class SaveReportRequest(BaseModel):
    name: str
    results: dict


@app.post("/reports")
def save_report(body: SaveReportRequest):
    return scheduler.save_adhoc_report(body.name, body.results)


@app.delete("/reports/{report_id}")
def delete_report(report_id: str):
    if not scheduler.delete_report(report_id):
        raise HTTPException(status_code=404, detail="Report not found")
    return {"ok": True}


# ---- Analytics ----
class AnalyticsRequest(BaseModel):
    report_ids: list[str]


@app.post("/analytics")
def generate_analytics(body: AnalyticsRequest):
    reports = [scheduler.get_report(rid) for rid in body.report_ids]
    reports = [r for r in reports if r is not None]
    if not reports:
        raise HTTPException(status_code=400, detail="No valid reports selected")
    return analytics.generate(reports)


class SaveAnalyticsRequest(BaseModel):
    name: str
    analytics: dict
    source_report_ids: list[str]


@app.post("/analytics/reports")
def save_analytics_report(body: SaveAnalyticsRequest):
    return scheduler.save_analytics_report(body.name, body.analytics, body.source_report_ids)


@app.get("/analytics/reports")
def list_analytics_reports():
    return scheduler.get_analytics_reports()


@app.get("/analytics/reports/{report_id}")
def get_analytics_report(report_id: str):
    report = scheduler.get_analytics_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Analytics report not found")
    return report


@app.delete("/analytics/reports/{report_id}")
def delete_analytics_report(report_id: str):
    if not scheduler.delete_analytics_report(report_id):
        raise HTTPException(status_code=404, detail="Analytics report not found")
    return {"ok": True}


# ---- Checklist / Planner ----
class ChecklistCreate(BaseModel):
    text: str
    date: str  # YYYY-MM-DD
    sort_order: int = 0
    priority: bool = False
    private: bool = False


class ChecklistUpdate(BaseModel):
    text: Optional[str] = None
    date: Optional[str] = None
    done: Optional[bool] = None
    sort_order: Optional[int] = None
    priority: Optional[bool] = None
    private: Optional[bool] = None


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
        private=body.private,
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


# ---- Notes ----
class NoteCreate(BaseModel):
    title: str
    content: str = ""


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    archived: Optional[bool] = None


@app.get("/notes")
def get_notes(archived: Optional[bool] = None):
    return notes.list_notes(archived=archived)


@app.get("/notes/{note_id}")
def get_note(note_id: str):
    note = notes.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@app.post("/notes")
def create_note(body: NoteCreate):
    return notes.create_note(title=body.title, content=body.content)


@app.put("/notes/{note_id}")
def update_note(note_id: str, body: NoteUpdate):
    note = notes.update_note(note_id, body.model_dump())
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@app.delete("/notes/{note_id}")
def delete_note(note_id: str):
    if not notes.delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}


# ---- Links / Bookmarks ----
class LinkCreate(BaseModel):
    url: str
    title: str = ""


class LinkUpdate(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None


@app.get("/links")
def get_links():
    return links.list_links()


@app.post("/links")
def create_link(body: LinkCreate):
    return links.create_link(url=body.url, title=body.title)


@app.put("/links/{link_id}")
def update_link(link_id: str, body: LinkUpdate):
    link = links.update_link(link_id, body.model_dump())
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    return link


@app.delete("/links/{link_id}")
def delete_link(link_id: str):
    if not links.delete_link(link_id):
        raise HTTPException(status_code=404, detail="Link not found")
    return {"ok": True}


# ---- File Browser (for app launcher) ----
@app.get("/browse")
def browse_directory(path: str = Query("~")):
    """List directory contents for the file browser UI."""
    resolved = os.path.expanduser(path)
    if not os.path.isdir(resolved):
        # If it's a file, browse its parent
        resolved = os.path.dirname(resolved)
    if not os.path.isdir(resolved):
        raise HTTPException(status_code=400, detail="Invalid directory")

    try:
        entries = []
        for name in sorted(os.listdir(resolved)):
            if name.startswith("."):
                continue  # skip hidden by default
            full = os.path.join(resolved, name)
            entries.append({
                "name": name,
                "path": full,
                "is_dir": os.path.isdir(full),
            })
        return {
            "current": resolved,
            "parent": os.path.dirname(resolved),
            "entries": entries,
        }
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")


# ---- App Launcher ----
class AppCreate(BaseModel):
    name: str
    start_script: str
    stop_script: str = ""
    url: str = ""
    working_dir: str = ""


class AppUpdate(BaseModel):
    name: Optional[str] = None
    start_script: Optional[str] = None
    stop_script: Optional[str] = None
    url: Optional[str] = None
    working_dir: Optional[str] = None


@app.get("/apps")
def get_apps():
    return app_launcher.list_apps()


@app.get("/apps/{app_id}")
def get_app_detail(app_id: str):
    a = app_launcher.get_app(app_id)
    if not a:
        raise HTTPException(status_code=404, detail="App not found")
    return a


@app.post("/apps")
def create_app(body: AppCreate):
    return app_launcher.create_app(
        name=body.name, start_script=body.start_script,
        stop_script=body.stop_script, url=body.url,
        working_dir=body.working_dir,
    )


@app.put("/apps/{app_id}")
def update_app_config(app_id: str, body: AppUpdate):
    a = app_launcher.update_app(app_id, body.model_dump())
    if not a:
        raise HTTPException(status_code=404, detail="App not found")
    return a


@app.post("/apps/{app_id}/start")
def start_app(app_id: str):
    a = app_launcher.start_app(app_id)
    if not a:
        raise HTTPException(status_code=404, detail="App not found or no start script")
    return a


@app.post("/apps/{app_id}/stop")
def stop_app(app_id: str):
    a = app_launcher.stop_app(app_id)
    if not a:
        raise HTTPException(status_code=404, detail="App not found")
    return a


@app.delete("/apps/{app_id}")
def delete_app(app_id: str):
    if not app_launcher.delete_app(app_id):
        raise HTTPException(status_code=404, detail="App not found")
    return {"ok": True}


# ---- Agents ----
def require_local_origin(origin: Optional[str] = Header(None)) -> None:
    """Agents run local commands, so refuse requests sent by other websites."""
    if origin and origin not in ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail="Origin not allowed")


class AgentCreate(BaseModel):
    name: str
    runtime: str = "claude"
    model: str = ""
    prompt: str = ""
    working_dir: str = ""
    command: str = ""


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    runtime: Optional[str] = None
    model: Optional[str] = None
    prompt: Optional[str] = None
    working_dir: Optional[str] = None
    command: Optional[str] = None


@app.get("/artifacts")
def get_artifacts():
    return artifacts.get_list()


class AgentReorder(BaseModel):
    agent_ids: list[str]


@app.get("/agents")
def get_agents():
    return agents.list_agents()


@app.get("/agents/runtimes")
def get_agent_runtimes():
    return agents.RUNTIMES


@app.get("/agents/models")
def get_agent_models(runtime: str):
    return agents.list_models(runtime)


@app.get("/agents/runs")
def get_agent_runs():
    return agents.list_runs()


@app.post("/agents", dependencies=[Depends(require_local_origin)])
def create_agent(body: AgentCreate):
    return agents.create_agent(**body.model_dump())


@app.post("/agents/reorder", dependencies=[Depends(require_local_origin)])
def reorder_agents(body: AgentReorder):
    return agents.reorder_agents(body.agent_ids)


@app.put("/agents/{agent_id}", dependencies=[Depends(require_local_origin)])
def update_agent(agent_id: str, body: AgentUpdate):
    a = agents.update_agent(agent_id, body.model_dump())
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    return a


@app.delete("/agents/{agent_id}", dependencies=[Depends(require_local_origin)])
def delete_agent(agent_id: str):
    if not agents.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"ok": True}


@app.post("/agents/{agent_id}/launch", dependencies=[Depends(require_local_origin)])
def launch_agent(agent_id: str):
    try:
        return agents.launch(agent_id).to_dict()
    except LookupError:
        raise HTTPException(status_code=404, detail="Agent not found")
    except (ValueError, OSError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/agents/runs/{run_id}/kill", dependencies=[Depends(require_local_origin)])
def kill_agent_run(run_id: str):
    run = agents.kill_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.delete("/agents/runs/{run_id}", dependencies=[Depends(require_local_origin)])
def remove_agent_run(run_id: str):
    if not agents.remove_run(run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    return {"ok": True}


@app.websocket("/agents/runs/{run_id}/ws")
async def agent_run_ws(ws: WebSocket, run_id: str):
    """Live terminal: binary frames carry output, JSON frames carry control."""
    origin = ws.headers.get("origin")
    run = agents.get_run(run_id)
    if (origin and origin not in ALLOWED_ORIGINS) or not run:
        await ws.close(code=1008)
        return
    await ws.accept()

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def listener(data: Optional[bytes]) -> None:  # called from the run's reader thread
        loop.call_soon_threadsafe(queue.put_nowait, data)

    backlog = run.attach(listener)

    async def send_output() -> None:
        if backlog:
            await ws.send_bytes(backlog)
        while run.running:
            data = await queue.get()
            if data is None:
                break
            await ws.send_bytes(data)
        await ws.send_json({"type": "exit", "code": run.exit_code})

    sender = asyncio.create_task(send_output())
    first_resize = True
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "input":
                run.write(str(msg.get("data", "")).encode())
            elif msg.get("type") == "resize":
                # Force a repaint on attach so a replayed full-screen UI settles
                run.resize(int(msg.get("rows", 0)), int(msg.get("cols", 0)), redraw=first_resize)
                first_resize = False
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        sender.cancel()
        run.detach(listener)
