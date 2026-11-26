"""Fallback Gmail/Calendar reader that goes through the Claude Code CLI.

Used when this app's own Google OAuth session is unavailable. Each call runs
`claude -p` headless and has it invoke one claude.ai connector (MCP) tool; the
raw tool result is parsed straight out of the CLI's stream, so the model never
re-types (or summarizes) the data. Exposes the same interface as GoogleService.
"""
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from google_service import _period_to_timedelta, event_time_range

# Pseudo session token the frontend holds while running in fallback mode.
SESSION_TOKEN = "claude-mcp"

_GMAIL_SEARCH = "mcp__claude_ai_Gmail__search_threads"
_CALENDAR_LIST = "mcp__claude_ai_Google_Calendar__list_events"

_WORK_DIR = Path(__file__).parent / "data" / "claude_mcp"
_TIMEOUT_SECONDS = 180
# Large tool results are spilled to a file and only the path is returned inline.
_SAVED_RE = re.compile(r"saved to (/\S+?\.(?:txt|json))")

_profile_cache: Optional[dict] = None


class ClaudeMcpError(RuntimeError):
    pass


def _claude_bin() -> Optional[str]:
    return os.getenv("CLAUDE_BIN") or shutil.which("claude")


def available() -> bool:
    return _claude_bin() is not None


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "") for block in content or []
        if isinstance(block, dict) and block.get("type") == "text"
    )


def _call_tool(tool: str, args: dict) -> dict:
    """Have the Claude CLI call one MCP tool once and return its JSON result."""
    binary = _claude_bin()
    if not binary:
        raise ClaudeMcpError("Claude CLI not found (set CLAUDE_BIN or install `claude`)")

    prompt = (
        f"Call the tool `{tool}` exactly once with exactly these arguments and no others:\n"
        f"{json.dumps(args)}\n"
        "Do not call any other tool and do not retry. Then reply with only: done"
    )
    # The connectors belong to the claude.ai login; an API key in the
    # environment would make the CLI authenticate without them.
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    _WORK_DIR.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [binary, "-p", prompt, "--allowedTools", tool,
             "--output-format", "stream-json", "--verbose",
             "--model", os.getenv("CLAUDE_MCP_MODEL", "haiku")],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=_TIMEOUT_SECONDS, cwd=_WORK_DIR, env=env,
        )
    except subprocess.TimeoutExpired:
        raise ClaudeMcpError(f"Claude CLI timed out calling {tool}")

    tool_use_id = None
    for line in proc.stdout.splitlines():
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if msg.get("type") not in ("assistant", "user"):
            continue
        content = (msg.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == tool:
                tool_use_id = block.get("id")
            elif block.get("type") == "tool_result" and block.get("tool_use_id") == tool_use_id:
                text = _result_text(block.get("content"))
                saved = _SAVED_RE.search(text)
                if saved:
                    text = Path(saved.group(1)).read_text()
                elif block.get("is_error"):
                    raise ClaudeMcpError(f"{tool} failed: {text[:300]}")
                try:
                    return json.loads(text)
                except ValueError:
                    raise ClaudeMcpError(f"{tool} returned non-JSON: {text[:300]}")

    raise ClaudeMcpError(
        f"Claude CLI never called {tool} (exit {proc.returncode}): {(proc.stderr or proc.stdout)[-300:]}"
    )


class ClaudeMcpService:
    # ---- Profile ----
    def get_user_profile(self) -> dict:
        global _profile_cache
        if _profile_cache is None:
            # The primary calendar's name is the account's email address.
            now = datetime.now()
            resp = _call_tool(_CALENDAR_LIST, {
                "startTime": now.strftime("%Y-%m-%dT%H:%M:%S"),
                "pageSize": 1,
            })
            _profile_cache = {
                "email": resp.get("summary") or "Claude connectors",
                "name": "via Claude connectors",
                "picture": None,
            }
        return _profile_cache

    # ---- Gmail ----
    def fetch_emails(self, period: str, max_results: int = 100) -> list[dict]:
        delta = _period_to_timedelta(period)
        after = int((datetime.now(tz=timezone.utc) - delta).timestamp())
        msgs: list[dict] = []
        page_token: Optional[str] = None
        while len(msgs) < max_results:
            args = {
                "query": f"in:inbox after:{after}",
                "pageSize": min(50, max_results - len(msgs)),
                # One entry (the latest message) per thread
                "view": "THREAD_VIEW_SUMMARY",
            }
            if page_token:
                args["pageToken"] = page_token
            resp = _call_tool(_GMAIL_SEARCH, args)
            threads = resp.get("threads", [])
            if not threads:
                break
            for thread in threads:
                latest = (thread.get("messages") or [{}])[-1]
                names = {
                    a.get("emailAddress"): a.get("displayName")
                    for a in latest.get("addressDisplayNames", [])
                }
                sender = latest.get("sender", "")
                msgs.append({
                    "id": latest.get("id") or thread.get("id"),
                    "from": f"{names[sender]} <{sender}>" if names.get(sender) else sender,
                    "to": ", ".join(latest.get("toRecipients", [])),
                    "subject": latest.get("subject", ""),
                    "date": latest.get("date", ""),
                    "snippet": latest.get("snippet", ""),
                    "labels": latest.get("labelIds", []),
                })
                if len(msgs) >= max_results:
                    break
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return msgs

    # ---- Calendar ----
    def fetch_events(self, period: str, direction: str = "future") -> list[dict]:
        time_min, time_max = event_time_range(period, direction)
        events: list[dict] = []
        page_token: Optional[str] = None
        while True:
            args = {
                # The connector wants local time with no UTC offset
                "startTime": time_min.strftime("%Y-%m-%dT%H:%M:%S"),
                "endTime": time_max.strftime("%Y-%m-%dT%H:%M:%S"),
                "orderBy": "startTime",
                "pageSize": 250,
            }
            if page_token:
                args["pageToken"] = page_token
            resp = _call_tool(_CALENDAR_LIST, args)
            for ev in resp.get("events", []):
                start = ev.get("start", {})
                end = ev.get("end", {})
                events.append({
                    "id": ev.get("id"),
                    "summary": ev.get("summary", "(no title)"),
                    "description": (ev.get("description") or "")[:500],
                    "location": ev.get("location"),
                    "start": start.get("dateTime") or start.get("date"),
                    "end": end.get("dateTime") or end.get("date"),
                    "attendees": [a.get("email") for a in ev.get("attendees", []) if a.get("email")],
                    "organizer": (ev.get("organizer") or {}).get("email"),
                    "hangoutLink": ev.get("hangoutLink"),
                    "status": ev.get("status"),
                })
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return events
