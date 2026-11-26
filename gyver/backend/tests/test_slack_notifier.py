"""Tests for slack_notifier module."""
import json
from unittest.mock import MagicMock, patch

from slack_notifier import format_summary_for_slack, send_to_slack


class TestFormatSummaryForSlack:
    def test_email_summary_basic(self):
        summary = {
            "summary": "You had 10 emails.",
            "count": 10,
            "highlights": [{"title": "Important", "why": "urgent", "from": "boss@co.com", "subject": "Review"}],
            "themes": ["finance", "planning"],
            "action_items": ["Reply to boss"],
        }
        payload = format_summary_for_slack(summary, "emails", "week")
        blocks = payload["blocks"]
        assert blocks[0]["type"] == "header"
        assert "Email Summary" in blocks[0]["text"]["text"]
        assert any("You had 10 emails" in b.get("text", {}).get("text", "") for b in blocks if b["type"] == "section")
        assert any("finance" in b.get("text", {}).get("text", "") for b in blocks if b["type"] == "section")
        assert blocks[-1]["type"] == "context"

    def test_calendar_summary_with_direction(self):
        summary = {
            "summary": "Busy week ahead.",
            "count": 15,
            "stats": {"total_events": 15, "total_hours": 20},
            "highlights": [],
            "themes": [],
            "action_items": [],
        }
        payload = format_summary_for_slack(summary, "calendar", "week", "future")
        header_text = payload["blocks"][0]["text"]["text"]
        assert "upcoming" in header_text

    def test_calendar_past_direction(self):
        summary = {"summary": "Quiet week.", "count": 2}
        payload = format_summary_for_slack(summary, "calendar", "week", "past")
        assert "previous" in payload["blocks"][0]["text"]["text"]

    def test_calendar_current_direction(self):
        summary = {"summary": "Normal day.", "count": 5}
        payload = format_summary_for_slack(summary, "calendar", "day", "current")
        assert "current" in payload["blocks"][0]["text"]["text"]

    def test_empty_summary(self):
        summary = {"summary": "", "count": 0}
        payload = format_summary_for_slack(summary, "emails", "day")
        assert len(payload["blocks"]) >= 2  # header + context at minimum

    def test_highlights_truncated(self):
        highlights = [{"title": f"Item {i}", "why": "x" * 300} for i in range(15)]
        summary = {"summary": "Lots of stuff", "highlights": highlights}
        payload = format_summary_for_slack(summary, "emails", "week")
        # Should not exceed block limits
        assert len(payload["blocks"]) <= 50

    def test_action_items_included(self):
        summary = {
            "summary": "test",
            "action_items": ["Do thing A", "Do thing B"],
        }
        payload = format_summary_for_slack(summary, "emails", "day")
        text = json.dumps(payload)
        assert "Do thing A" in text
        assert "Do thing B" in text


class TestSendToSlack:
    @patch("slack_notifier.urllib.request.urlopen")
    def test_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = send_to_slack("https://hooks.slack.com/services/T/B/x", {"blocks": []})
        assert result is True

    @patch("slack_notifier.urllib.request.urlopen")
    def test_failure(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("timeout")

        result = send_to_slack("https://hooks.slack.com/services/T/B/x", {"blocks": []})
        assert result is False
