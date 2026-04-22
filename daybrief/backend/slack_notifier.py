"""Send formatted summaries to Slack via Incoming Webhooks."""
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone


def format_summary_for_slack(
    summary: dict,
    mode: str,
    period: str,
    direction: str | None = None,
) -> dict:
    """Build a Slack Block Kit payload from a summary result."""
    blocks: list[dict] = []

    # Header
    if mode == "emails":
        title = f"Email Summary — past {period}"
    else:
        dir_label = {"past": "previous", "current": "current", "future": "upcoming"}.get(
            direction or "future", direction or "future"
        )
        title = f"Calendar Summary — {dir_label} {period}"

    blocks.append({"type": "header", "text": {"type": "plain_text", "text": title}})

    # Summary text
    text = summary.get("summary", "")
    if text:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

    # Stats
    stats = summary.get("stats") or {}
    count = summary.get("count")
    parts = []
    if count is not None:
        parts.append(f"*Items:* {count}")
    if stats.get("total_events"):
        parts.append(f"*Events:* {stats['total_events']}")
    if stats.get("total_hours"):
        parts.append(f"*Hours:* {stats['total_hours']}")
    if parts:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "  |  ".join(parts)},
        })

    # Highlights
    highlights = summary.get("highlights") or []
    if highlights:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Highlights*"},
        })
        lines = []
        for h in highlights[:10]:
            line = f"• *{h.get('title', '')}*"
            if h.get("why"):
                line += f" — {h['why']}"
            meta = []
            if h.get("from"):
                meta.append(f"From: {h['from']}")
            if h.get("subject"):
                meta.append(f"Subject: {h['subject']}")
            if h.get("when"):
                meta.append(h["when"])
            if meta:
                line += f"\n   _{' | '.join(meta)}_"
            lines.append(line)
        # Slack has 3000 char limit per text block — split if needed
        text = "\n".join(lines)
        if len(text) > 2900:
            text = text[:2900] + "\n…"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

    # Themes
    themes = summary.get("themes") or []
    if themes:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Themes:* {' · '.join(themes)}"},
        })

    # Action items
    action_items = summary.get("action_items") or []
    if action_items:
        blocks.append({"type": "divider"})
        items_text = "\n".join(f"• {a}" for a in action_items[:10])
        if len(items_text) > 2900:
            items_text = items_text[:2900] + "\n…"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Action Items*\n{items_text}"},
        })

    # Footer
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"Sent from DayBrief · {now}"}],
    })

    return {"blocks": blocks}


def send_to_slack(webhook_url: str, payload: dict, timeout: int = 10) -> bool:
    """POST a Block Kit payload to a Slack webhook. Returns True on success."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return False
