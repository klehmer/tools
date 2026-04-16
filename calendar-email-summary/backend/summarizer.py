"""AI-powered summarization of emails and calendar events.

Supports three providers:
  - anthropic  : Anthropic API (requires ANTHROPIC_API_KEY)
  - claude-code: Claude Code CLI (requires `claude` on PATH)
  - openai     : OpenAI API (requires OPENAI_API_KEY)
"""
import json
import os
import subprocess
from typing import Optional


# ---------------------------------------------------------------------------
# Provider dispatch
# ---------------------------------------------------------------------------

def _get_provider() -> str:
    return os.getenv("AI_PROVIDER", "anthropic")


def _get_model() -> str:
    provider = _get_provider()
    default = {
        "anthropic": "claude-haiku-4-5",
        "claude-code": "",  # not used
        "openai": "gpt-4o-mini",
    }
    return os.getenv("AI_MODEL", default.get(provider, ""))


def _call_llm(prompt: str) -> str:
    provider = _get_provider()
    if provider == "anthropic":
        return _call_anthropic(prompt)
    elif provider == "claude-code":
        return _call_claude_code(prompt)
    elif provider == "codex":
        return _call_codex(prompt)
    elif provider == "openai":
        return _call_openai(prompt)
    else:
        raise ValueError(f"Unknown AI_PROVIDER: {provider}")


def _call_anthropic(prompt: str) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=_get_model() or "claude-haiku-4-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text if resp.content else ""


def _call_claude_code(prompt: str) -> str:
    model = _get_model()
    cmd = ["claude", "-p", prompt, "--output-format", "text"]
    if model:
        cmd.extend(["--model", model])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr[:500]}")
    return result.stdout


def _call_codex(prompt: str) -> str:
    result = subprocess.run(
        ["codex", "exec", prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"codex CLI failed: {result.stderr[:500]}")
    return result.stdout


def _call_openai(prompt: str) -> str:
    import openai
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model=_get_model() or "gpt-4o-mini",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {"summary": text, "highlights": [], "items": []}
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return {"summary": text, "highlights": [], "items": []}


# ---------------------------------------------------------------------------
# Summarization functions
# ---------------------------------------------------------------------------

def summarize_emails(emails: list[dict], period: str) -> dict:
    if not emails:
        return {"summary": f"No emails found for the previous {period}.", "highlights": [], "items": []}

    compact = [
        {"from": e["from"], "subject": e["subject"], "date": e["date"], "snippet": e["snippet"]}
        for e in emails
    ]
    user_rules = os.getenv("EMAIL_PROMPT_RULES", "").strip()
    rules_block = f"\n\nADDITIONAL USER RULES (follow these strictly):\n{user_rules}\n" if user_rules else ""
    prompt = f"""You are an executive assistant. Summarize the user's emails from the previous {period}.

Return a single JSON object with this shape:
{{
  "summary": "2-4 sentence high-level overview",
  "highlights": [
    {{"title": "short title", "why": "why this matters", "from": "sender", "subject": "subject"}}
  ],
  "themes": ["theme1", "theme2"],
  "action_items": ["actionable thing the user should do"]
}}

Identify the MOST IMPORTANT emails (action required, personal, time-sensitive, from real people).
Skip routine newsletters/promotions unless notably important. Include up to 10 highlights.{rules_block}

EMAILS ({len(compact)} total):
{json.dumps(compact, indent=2)[:60000]}

Respond with ONLY the JSON object."""

    text = _call_llm(prompt)
    return _extract_json(text)


def summarize_events(events: list[dict], period: str, direction: str) -> dict:
    when = "upcoming" if direction == "future" else "current" if direction == "current" else "past"
    if not events:
        return {"summary": f"No {when} events for the {period}.", "highlights": [], "items": []}

    compact = [
        {
            "summary": e["summary"],
            "start": e["start"],
            "end": e["end"],
            "location": e["location"],
            "attendees": e["attendees"][:10],
            "organizer": e["organizer"],
            "description": e["description"][:200],
        }
        for e in events
    ]
    user_rules = os.getenv("CALENDAR_PROMPT_RULES", "").strip()
    rules_block = f"\n\nADDITIONAL USER RULES (follow these strictly):\n{user_rules}\n" if user_rules else ""
    prompt = f"""You are an executive assistant. Summarize the user's {when} calendar over the {period}.

Return a single JSON object:
{{
  "summary": "2-4 sentence overview of the user's schedule",
  "highlights": [
    {{"title": "meeting title", "when": "human-readable time", "why": "why important", "attendees": ["..."]}}
  ],
  "themes": ["theme1"],
  "action_items": ["prep needed before key meetings"],
  "stats": {{"total_events": 0, "total_hours": 0}}
}}

Highlight the most important meetings (external attendees, leadership, decisions, interviews, prep needed).
Up to 10 highlights. Be concise.{rules_block}

EVENTS ({len(compact)} total):
{json.dumps(compact, indent=2, default=str)[:60000]}

Respond with ONLY the JSON object."""

    text = _call_llm(prompt)
    return _extract_json(text)
