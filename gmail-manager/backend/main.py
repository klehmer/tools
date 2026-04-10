import io
import os
import zipfile
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel

load_dotenv()

import approvals
import auth
import config_manager
import rules_manager
from agent import GmailAnalysisAgent
from gmail_service import GmailService
from models import (
    AnalysisResult,
    BlockRequest,
    DeleteRequest,
    DownloadRequest,
    UnsubscribeRequest,
    UserProfile,
)

app = FastAPI(title="Gmail Manager API")

# Allow all origins — this is a local-only tool
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:5173")


# ------------------------------------------------------------------ #
# Dependencies                                                         #
# ------------------------------------------------------------------ #


def get_session_token(x_session_token: Optional[str] = Header(None)) -> str:
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return x_session_token


def get_gmail(session_token: str = Depends(get_session_token)) -> GmailService:
    credentials = auth.get_credentials(session_token)
    if not credentials:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return GmailService(credentials)


# ------------------------------------------------------------------ #
# Config (no auth required — needed before first login)               #
# ------------------------------------------------------------------ #


class ConfigUpdate(BaseModel):
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    BACKEND_URL: Optional[str] = None
    FRONTEND_URL: Optional[str] = None


@app.get("/config/status")
def config_status():
    return {"configured": config_manager.is_configured()}


@app.get("/config")
def get_config():
    return config_manager.get_config()


@app.post("/config")
def update_config(body: ConfigUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    config_manager.save_config(updates)
    return {"ok": True, "configured": config_manager.is_configured()}


# ------------------------------------------------------------------ #
# Rules                                                               #
# ------------------------------------------------------------------ #


class RulesUpdate(BaseModel):
    require_approval: Optional[bool] = None
    download_before_delete: Optional[bool] = None
    protected_senders: Optional[list[str]] = None
    protected_keywords: Optional[list[str]] = None
    custom_instructions: Optional[str] = None


@app.get("/rules")
def get_rules():
    return rules_manager.get_rules()


@app.post("/rules")
def update_rules(body: RulesUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return rules_manager.save_rules(updates)


# ------------------------------------------------------------------ #
# Auth                                                                 #
# ------------------------------------------------------------------ #


@app.get("/auth/url")
def get_auth_url():
    return {"url": auth.get_auth_url()}


@app.get("/auth/callback")
def auth_callback(code: str, state: Optional[str] = None):
    try:
        session_token = auth.exchange_code(code, state or "")
    except Exception as e:
        import logging, traceback
        logging.error("OAuth callback error: %s\n%s", e, traceback.format_exc())
        return RedirectResponse(
            f"{_frontend_url()}?error=auth_failed&detail={str(e)[:200]}"
        )
    return RedirectResponse(f"{_frontend_url()}?session_token={session_token}")


@app.get("/auth/me", response_model=UserProfile)
def get_me(gmail: GmailService = Depends(get_gmail)):
    profile = gmail.get_user_profile()
    overview = gmail.get_inbox_overview()
    return UserProfile(
        email=profile.get("email", ""),
        name=profile.get("name"),
        picture=profile.get("picture"),
        total_messages=overview.get("total_messages", 0),
        storage_used_bytes=overview.get("storage_used_bytes"),
        storage_limit_bytes=overview.get("storage_limit_bytes"),
    )


@app.post("/auth/logout")
def logout(session_token: str = Depends(get_session_token)):
    auth.delete_session(session_token)
    return {"ok": True}


# ------------------------------------------------------------------ #
# Agent Analysis                                                       #
# ------------------------------------------------------------------ #


# ------------------------------------------------------------------ #
# Gmail tool endpoints (for external agents: Claude Code, Codex, etc.) #
# ------------------------------------------------------------------ #


@app.get("/gmail/overview")
def gmail_overview(gmail: GmailService = Depends(get_gmail)):
    return gmail.get_inbox_overview()


@app.get("/gmail/top-senders")
def gmail_top_senders(limit: int = 30, gmail: GmailService = Depends(get_gmail)):
    return gmail.get_top_senders(limit)


@app.get("/gmail/search")
def gmail_search(query: str, limit: int = 50, gmail: GmailService = Depends(get_gmail)):
    return gmail.search_emails(query, min(limit, 500))


@app.get("/gmail/unsubscribe-candidates")
def gmail_unsubscribe_candidates(limit: int = 50, gmail: GmailService = Depends(get_gmail)):
    return gmail.get_emails_with_unsubscribe(limit)


class MessagesQuery(BaseModel):
    email_ids: list[str]


@app.post("/gmail/messages")
def gmail_messages(body: MessagesQuery, gmail: GmailService = Depends(get_gmail)):
    return {"messages": gmail.get_messages_metadata(body.email_ids)}


# ------------------------------------------------------------------ #
# Approvals (human-in-the-loop for autonomous agents)                  #
# ------------------------------------------------------------------ #


class ApprovalRequest(BaseModel):
    email_ids: list[str]
    sender: str = ""
    reason: str = ""
    suggested_action: str = "delete"


class ApprovalDecision(BaseModel):
    status: str  # "approved" | "denied"


@app.post("/approvals/request")
def approvals_request(body: ApprovalRequest):
    approvals.cleanup_old()
    return approvals.request_approval(
        email_ids=body.email_ids,
        sender=body.sender,
        reason=body.reason,
        suggested_action=body.suggested_action,
    )


@app.get("/approvals")
def approvals_list(status: Optional[str] = None):
    return {"approvals": approvals.list_approvals(status)}


@app.get("/approvals/{aid}")
def approvals_get(aid: str):
    rec = approvals.get_approval(aid)
    if not rec:
        raise HTTPException(status_code=404, detail="Approval not found")
    return rec


@app.post("/approvals/{aid}/decide")
def approvals_decide(aid: str, body: ApprovalDecision):
    rec = approvals.decide(aid, body.status)
    if not rec:
        raise HTTPException(status_code=404, detail="Approval not found")
    return rec


# ------------------------------------------------------------------ #
# Agent report (live summary the autonomous runner posts to)           #
# ------------------------------------------------------------------ #

import json
import tempfile
import time
from pathlib import Path

import threading

_REPORT_FILE = Path(tempfile.gettempdir()) / "gmail_manager_agent_report.json"
_REPORT_LOCK = threading.Lock()


class ReportGroup(BaseModel):
    sender: str
    count: int
    estimated_size_mb: Optional[float] = None
    suggested_action: str  # "delete" | "block" | "unsubscribe" | "keep"
    reason: str
    query: Optional[str] = None  # gmail search query to materialise the IDs at action time
    email_ids: Optional[list[str]] = None  # explicit IDs (if the agent already has them)
    unsubscribe_link: Optional[str] = None  # populate when the agent already knows the link


class AgentReport(BaseModel):
    runner: str = "external"  # claude-code | codex | builtin
    status: str = "running"  # running | done
    summary: str = ""
    starting_total: Optional[int] = None
    current_total: Optional[int] = None
    deleted_so_far: int = 0
    groups: list[ReportGroup] = []
    actioned_keys: list[str] = []  # group keys the user has acted on (persisted across refreshes)


def _read_report_unlocked() -> Optional[dict]:
    if _REPORT_FILE.exists():
        try:
            return json.loads(_REPORT_FILE.read_text())
        except Exception:
            return None
    return None


def _write_report_unlocked(data: dict) -> None:
    data["updated_at"] = time.time()
    _REPORT_FILE.write_text(json.dumps(data))


def _read_report() -> Optional[dict]:
    with _REPORT_LOCK:
        return _read_report_unlocked()


def _write_report(data: dict) -> None:
    with _REPORT_LOCK:
        _write_report_unlocked(data)


class ActionMark(BaseModel):
    key: str
    deleted_count: int = 0
    freed_mb: float = 0.0


@app.post("/agent/report/action")
def mark_report_action(body: ActionMark):
    with _REPORT_LOCK:
        data = _read_report_unlocked() or {}
        keys = set(data.get("actioned_keys") or [])
        keys.add(body.key)
        data["actioned_keys"] = sorted(keys)
        if body.deleted_count:
            data["deleted_so_far"] = int(data.get("deleted_so_far") or 0) + body.deleted_count
            if data.get("current_total") is not None:
                data["current_total"] = max(0, int(data["current_total"]) - body.deleted_count)
        _write_report_unlocked(data)
        return data


@app.get("/agent/report")
def get_agent_report():
    if _REPORT_FILE.exists():
        try:
            return json.loads(_REPORT_FILE.read_text())
        except Exception:
            pass
    return None


def _norm_sender(s: str) -> str:
    """Normalise a sender for dedupe — extract bare email if possible."""
    import re
    m = re.search(r"<([^>]+)>", s or "")
    return (m.group(1) if m else (s or "")).strip().lower()


def _merge_groups(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Merge incoming groups with existing ones, keyed by (sender, suggested_action).
    Keeps the highest count and a union of email_ids; later wins on reason/query."""
    by_key: dict[tuple[str, str], dict] = {}
    for g in (existing or []) + (incoming or []):
        k = (_norm_sender(g.get("sender", "")), g.get("suggested_action", ""))
        if k not in by_key:
            by_key[k] = dict(g)
            by_key[k]["email_ids"] = list(g.get("email_ids") or [])
            continue
        cur = by_key[k]
        # Take the larger count and size estimate
        cur["count"] = max(int(cur.get("count") or 0), int(g.get("count") or 0))
        if g.get("estimated_size_mb") is not None:
            cur["estimated_size_mb"] = max(
                float(cur.get("estimated_size_mb") or 0),
                float(g.get("estimated_size_mb") or 0),
            )
        # Union the email_ids
        ids = set(cur.get("email_ids") or [])
        ids.update(g.get("email_ids") or [])
        cur["email_ids"] = sorted(ids)
        # Newer reason/query/link wins if present
        for f in ("reason", "query", "unsubscribe_link"):
            if g.get(f):
                cur[f] = g[f]
    return list(by_key.values())


@app.post("/agent/report")
def post_agent_report(body: AgentReport):
    with _REPORT_LOCK:
        data = body.model_dump()
        existing = _read_report_unlocked() or {}
        # Preserve actioned_keys across runs unless caller explicitly sent some
        if not data.get("actioned_keys"):
            data["actioned_keys"] = existing.get("actioned_keys", [])
        # Merge incoming groups with whatever's already on disk so re-posts and
        # multiple agent runs accumulate rather than overwrite each other.
        data["groups"] = _merge_groups(existing.get("groups") or [], data.get("groups") or [])
        _write_report_unlocked(data)
        return data


# ------------------------------------------------------------------ #
# Unsubscribed senders memory (don't recommend again)                  #
# ------------------------------------------------------------------ #

_UNSUB_FILE = Path(tempfile.gettempdir()) / "gmail_manager_unsubscribed.json"


def _load_unsubscribed() -> list[str]:
    if _UNSUB_FILE.exists():
        try:
            return json.loads(_UNSUB_FILE.read_text())
        except Exception:
            return []
    return []


def _save_unsubscribed(items: list[str]) -> None:
    _UNSUB_FILE.write_text(json.dumps(sorted(set(items))))


class UnsubMark(BaseModel):
    sender_email: str


@app.get("/agent/unsubscribed")
def list_unsubscribed():
    return {"senders": _load_unsubscribed()}


@app.post("/agent/unsubscribed")
def add_unsubscribed(body: UnsubMark):
    items = _load_unsubscribed()
    items.append(body.sender_email.lower().strip())
    _save_unsubscribed(items)
    return {"senders": sorted(set(items))}


# ------------------------------------------------------------------ #
# Agent log tail (for live UI monitoring)                              #
# ------------------------------------------------------------------ #

# NOTE: hardcoded to /tmp (not tempfile.gettempdir()) so it matches what the
# wrapper script and the agent prompt write to. On macOS gettempdir() returns
# a per-user /var/folders path, which causes a silent UI/file mismatch.
_LOG_FILE = Path("/tmp/gmail_manager_agent.log")


@app.get("/agent/logs")
def get_agent_logs(lines: int = 200):
    if not _LOG_FILE.exists():
        return {"path": str(_LOG_FILE), "lines": []}
    try:
        text = _LOG_FILE.read_text(errors="replace")
        tail = text.splitlines()[-max(1, min(lines, 2000)):]
        return {"path": str(_LOG_FILE), "lines": tail}
    except Exception as e:
        return {"path": str(_LOG_FILE), "lines": [f"<error reading log: {e}>"]}


@app.get("/agent/runner-script")
def get_runner_script(
    runner: str = "codex",
    session_token: str = Depends(get_session_token),
):
    """Return a bash wrapper that runs the given CLI agent in a forever-loop,
    sleeping on errors so it survives rate limits without manual restarts."""
    backend = os.getenv("BACKEND_URL", "http://localhost:8000")
    runner = runner if runner in ("codex", "claude-code") else "codex"

    if runner == "codex":
        cli_cmd = (
            'codex exec --dangerously-bypass-approvals-and-sandbox '
            '"$(cat "$PROMPT_FILE")"'
        )
    else:
        cli_cmd = (
            'claude -p "$(cat "$PROMPT_FILE")" --dangerously-skip-permissions'
        )

    script = f"""#!/usr/bin/env bash
# Gmail Manager — autonomous cleanup runner
# Generated for runner: {runner}
#
# Usage:
#   1. Save the agent prompt to ~/gmail-prompt.txt (click "Get prompt" in the dashboard).
#   2. chmod +x this script.
#   3. nohup ./run-cleanup.sh > /tmp/gmail-runner.out 2>&1 &
#   4. Watch progress in the dashboard log panel, or: tail -f /tmp/gmail_manager_agent.log
#   5. Stop with: pkill -f run-cleanup.sh

set -u
PROMPT_FILE="${{PROMPT_FILE:-$HOME/gmail-prompt.txt}}"
LOG="/tmp/gmail_manager_agent.log"
BACKEND="{backend}"
SESSION_TOKEN="{session_token}"

if [ ! -f "$PROMPT_FILE" ]; then
  echo "Prompt file not found: $PROMPT_FILE" >&2
  echo "Click 'Get prompt' in the dashboard and save it to that path." >&2
  exit 1
fi

backoff=900   # start with 15 minutes after a failure
max_backoff=21600  # cap at 6 hours

while true; do
  echo "[$(date -u +%FT%TZ)] runner: starting agent pass" >> "$LOG"

  {cli_cmd} >> "$LOG" 2>&1
  rc=$?

  echo "[$(date -u +%FT%TZ)] runner: agent exited rc=$rc" >> "$LOG"

  # Check if the inbox is fully cleaned by querying current_total
  CURRENT=$(curl -fsS -H "X-Session-Token: $SESSION_TOKEN" "$BACKEND/agent/report" \\
    | python3 -c 'import sys,json; d=json.load(sys.stdin) or {{}}; print(d.get("current_total") or "")' 2>/dev/null || echo "")

  if [ $rc -eq 0 ]; then
    backoff=900  # reset backoff on success
    echo "[$(date -u +%FT%TZ)] runner: success, sleeping 60s before next pass (current_total=$CURRENT)" >> "$LOG"
    sleep 60
  elif [ $rc -eq 130 ] || [ $rc -eq 137 ] || [ $rc -eq 143 ]; then
    # SIGINT/SIGKILL/SIGTERM — someone (or us) killed codex on purpose.
    # Short sleep and retry so we don't punish a manual nudge with a 15-min wait.
    echo "[$(date -u +%FT%TZ)] runner: killed (rc=$rc), retrying in 10s" >> "$LOG"
    sleep 10
  else
    echo "[$(date -u +%FT%TZ)] runner: failure (probably rate-limit), sleeping ${{backoff}}s" >> "$LOG"
    sleep "$backoff"
    if [ "$backoff" -lt "$max_backoff" ]; then
      backoff=$((backoff * 2))
      [ "$backoff" -gt "$max_backoff" ] && backoff=$max_backoff
    fi
  fi
done
"""

    return Response(
        content=script,
        media_type="text/x-shellscript",
        headers={
            "Content-Disposition": f'attachment; filename="run-cleanup-{runner}.sh"',
        },
    )


@app.delete("/agent/logs")
def clear_agent_logs():
    if _LOG_FILE.exists():
        _LOG_FILE.write_text("")
    return {"ok": True}


@app.delete("/agent/report")
def clear_agent_report():
    if _REPORT_FILE.exists():
        _REPORT_FILE.unlink()
    return {"ok": True}


@app.get("/agent/processes")
def list_agent_processes():
    """Return currently running runner/CLI agent processes."""
    import subprocess
    r = subprocess.run(["ps", "-eo", "pid,etime,command"], capture_output=True, text=True)
    procs = []
    for line in r.stdout.splitlines()[1:]:
        if any(p in line for p in ("run-cleanup-", "codex exec", "claude -p")):
            parts = line.strip().split(None, 2)
            if len(parts) == 3:
                procs.append({"pid": parts[0], "etime": parts[1], "command": parts[2]})
    return {"processes": procs}


@app.post("/agent/kill-all")
def kill_all_agents():
    """Kill any running cleanup runner wrappers and the CLI agents they spawn.
    Matches the bash wrapper (run-cleanup-*.sh), `codex exec`, and `claude -p`."""
    import subprocess
    patterns = ["run-cleanup-", "codex exec", "claude -p"]
    killed = []
    for pat in patterns:
        r = subprocess.run(["pkill", "-9", "-f", pat], capture_output=True)
        killed.append({"pattern": pat, "rc": r.returncode})
    try:
        with _LOG_FILE.open("a") as f:
            f.write(f"[{__import__('datetime').datetime.utcnow().isoformat()}Z] kill-all invoked from dashboard\n")
    except Exception:
        pass
    return {"ok": True, "results": killed}


class InstallFilesRequest(BaseModel):
    prompt: str
    runner: str  # "codex" | "claude-code"


@app.post("/agent/install-files")
def install_cleanup_files(
    req: InstallFilesRequest,
    session_token: str = Depends(get_session_token),
):
    """Write the agent prompt and runner script directly to the user's home
    directory so they don't have to move files out of ~/Downloads manually.
    Backend runs locally, so this is fine."""
    home = Path(os.path.expanduser("~"))
    prompt_path = home / "gmail-prompt.txt"
    runner = req.runner if req.runner in ("codex", "claude-code") else "codex"
    script_path = home / f"run-cleanup-{runner}.sh"

    prompt_path.write_text(req.prompt)

    # Reuse the runner-script generator so we stay in sync with one source of truth.
    script_response = get_runner_script(runner=runner, session_token=session_token)
    script_body = script_response.body.decode() if hasattr(script_response, "body") else str(script_response)
    script_path.write_text(script_body)
    script_path.chmod(0o755)

    return {
        "ok": True,
        "prompt_path": str(prompt_path),
        "script_path": str(script_path),
    }


class StartAgentRequest(BaseModel):
    runner: str = "codex"


@app.post("/agent/start")
def start_agent(req: StartAgentRequest):
    """Launch the runner script in the background via nohup.
    Requires install-files to have been called first."""
    import subprocess
    home = Path(os.path.expanduser("~"))
    runner = req.runner if req.runner in ("codex", "claude-code") else "codex"
    script_path = home / f"run-cleanup-{runner}.sh"
    if not script_path.exists():
        raise HTTPException(400, f"Runner script not found: {script_path}. Click 'Install to ~/' first.")
    prompt_path = home / "gmail-prompt.txt"
    if not prompt_path.exists():
        raise HTTPException(400, f"Prompt file not found: {prompt_path}. Click 'Install to ~/' first.")

    # Launch detached from this process
    subprocess.Popen(
        ["nohup", str(script_path)],
        stdout=open("/tmp/gmail-runner.out", "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        with _LOG_FILE.open("a") as f:
            f.write(f"[{__import__('datetime').datetime.utcnow().isoformat()}Z] agent started from dashboard ({runner})\n")
    except Exception:
        pass
    return {"ok": True, "script": str(script_path)}


@app.post("/agent/analyze", response_model=AnalysisResult)
async def analyze_inbox(gmail: GmailService = Depends(get_gmail)):
    """
    Run the LLM agent to analyse the inbox.
    May take 30-90 seconds — the agent performs several Gmail API calls
    before returning structured recommendations.
    """
    agent = GmailAnalysisAgent(gmail)
    try:
        result = await agent.analyze()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
    return result


# ------------------------------------------------------------------ #
# Actions                                                              #
# ------------------------------------------------------------------ #


def _check_approval(x_approved: Optional[str]) -> None:
    rules = rules_manager.get_rules()
    if rules.get("require_approval") and x_approved != "1":
        raise HTTPException(
            status_code=403,
            detail="require_approval is enabled. Send X-Approved: 1 to confirm a user-approved action.",
        )


@app.post("/actions/delete")
def delete_emails(
    body: DeleteRequest,
    gmail: GmailService = Depends(get_gmail),
    x_approved: Optional[str] = Header(None),
):
    _check_approval(x_approved)
    result = gmail.delete_emails(body.email_ids)
    return result


@app.post("/actions/unsubscribe")
def unsubscribe(body: UnsubscribeRequest, gmail: GmailService = Depends(get_gmail)):
    if body.unsubscribe_link:
        if body.unsubscribe_link.startswith("mailto:"):
            success = gmail.send_unsubscribe_email(body.unsubscribe_link)
            return {"method": "email", "success": success}
        else:
            # Return the HTTP link for the user to open in a browser
            return {"method": "http", "url": body.unsubscribe_link}

    # Fallback: delete all emails from sender
    search = gmail.search_emails(f"from:{body.sender_email}", limit=200)
    ids = [e["id"] for e in search.get("emails", [])]
    if ids:
        gmail.delete_emails(ids)
    return {"method": "delete", "deleted": len(ids)}


@app.post("/actions/block")
def block_sender(
    body: BlockRequest,
    gmail: GmailService = Depends(get_gmail),
    x_approved: Optional[str] = Header(None),
):
    if rules_manager.is_sender_protected(body.sender_email):
        raise HTTPException(status_code=403, detail=f"{body.sender_email} is in protected_senders")
    _check_approval(x_approved)
    # Create filter to send future emails to Trash
    filter_result = gmail.create_block_filter(body.sender_email)
    # Also delete existing emails from sender
    search = gmail.search_emails(f"from:{body.sender_email}", limit=200)
    ids = [e["id"] for e in search.get("emails", [])]
    if ids:
        gmail.delete_emails(ids)
    return {
        "filter": filter_result,
        "deleted_existing": len(ids),
    }


# ------------------------------------------------------------------ #
# Download                                                             #
# ------------------------------------------------------------------ #


import asyncio
from concurrent.futures import ThreadPoolExecutor

# Module-level pool reused across requests so we don't pay startup cost per call
# and so the threads don't get GC'd before they finish.
_DOWNLOAD_POOL = ThreadPoolExecutor(max_workers=20, thread_name_prefix="dlbulk")


@app.post("/emails/download-bulk")
async def download_bulk(
    body: DownloadRequest,
    session_token: str = Depends(get_session_token),
):
    """Package selected emails (and optionally attachments) as a ZIP, in parallel.
    Async wrapper so the parallel fetches don't block the event loop."""
    credentials = auth.get_credentials(session_token)
    if not credentials:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    include_atts = body.include_attachments

    def fetch_one(email_id: str):
        # Each thread builds its own GmailService — googleapiclient's discovery
        # objects share an httplib2.Http that is NOT thread-safe.
        try:
            svc = GmailService(credentials)
            eml = svc.download_email_as_eml(email_id)
            atts: list[tuple[str, bytes]] = []
            if include_atts:
                for att in svc.get_attachments(email_id):
                    try:
                        data = svc.download_attachment(email_id, att["attachment_id"])
                        atts.append((att["filename"], data))
                    except Exception:
                        pass
            return email_id, eml, atts
        except Exception:
            return email_id, None, []

    loop = asyncio.get_running_loop()
    tasks = [loop.run_in_executor(_DOWNLOAD_POOL, fetch_one, eid) for eid in body.email_ids]
    results = await asyncio.gather(*tasks)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for email_id, eml, atts in results:
            if eml is None:
                continue
            zf.writestr(f"emails/{email_id}.eml", eml)
            for filename, data in atts:
                safe_name = filename.replace("/", "_").replace("..", "_")
                zf.writestr(f"attachments/{email_id}/{safe_name}", data)

    buf.seek(0)
    safe_name = (body.filename or "emails").replace("/", "_").replace("..", "_").strip() or "emails"
    if not safe_name.lower().endswith(".zip"):
        safe_name = f"{safe_name}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@app.get("/emails/{email_id}/download")
def download_single_email(email_id: str, gmail: GmailService = Depends(get_gmail)):
    eml = gmail.download_email_as_eml(email_id)
    return Response(
        content=eml,
        media_type="message/rfc822",
        headers={"Content-Disposition": f'attachment; filename="{email_id}.eml"'},
    )


@app.get("/emails/{email_id}/attachments")
def list_attachments(email_id: str, gmail: GmailService = Depends(get_gmail)):
    return {"attachments": gmail.get_attachments(email_id)}


@app.get("/emails/{email_id}/attachments/{attachment_id}/download")
def download_attachment(
    email_id: str,
    attachment_id: str,
    filename: str = "attachment",
    gmail: GmailService = Depends(get_gmail),
):
    data = gmail.download_attachment(email_id, attachment_id)
    safe = filename.replace("/", "_").replace("..", "_")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )
