"""Tests for summarizer module."""
import json
from unittest.mock import patch

import pytest

from summarizer import _extract_json, summarize_emails, summarize_events


class TestExtractJson:
    def test_valid_json(self):
        text = '{"summary": "hello", "highlights": []}'
        result = _extract_json(text)
        assert result["summary"] == "hello"

    def test_json_with_surrounding_text(self):
        text = 'Here is the result:\n{"summary": "test", "highlights": [{"title": "a"}]}\nDone.'
        result = _extract_json(text)
        assert result["summary"] == "test"
        assert len(result["highlights"]) == 1

    def test_no_json_returns_fallback(self):
        text = "No JSON here"
        result = _extract_json(text)
        assert result["summary"] == text
        assert result["highlights"] == []

    def test_invalid_json_returns_fallback(self):
        text = "{invalid json content}"
        result = _extract_json(text)
        assert "summary" in result

    def test_nested_json(self):
        inner = {"summary": "ok", "stats": {"total_events": 5, "total_hours": 3}}
        text = json.dumps(inner)
        result = _extract_json(text)
        assert result["stats"]["total_events"] == 5

    def test_empty_string(self):
        result = _extract_json("")
        assert result["summary"] == ""
        assert result["highlights"] == []


class TestSummarizeEmails:
    def test_empty_emails_returns_summary(self):
        result = summarize_emails([], "week")
        assert "No emails" in result["summary"]
        assert result["highlights"] == []

    @patch("summarizer._call_llm")
    def test_calls_llm_with_emails(self, mock_llm):
        mock_llm.return_value = json.dumps({
            "summary": "You had 2 emails this week.",
            "highlights": [{"title": "Q1 review", "why": "time-sensitive", "from": "boss@co.com", "subject": "Q1"}],
            "themes": ["finance"],
            "action_items": ["Review Q1 numbers"],
        })

        emails = [
            {"from": "boss@co.com", "subject": "Q1 review", "date": "2026-04-07", "snippet": "Please review"},
            {"from": "spam@shop.com", "subject": "Sale!", "date": "2026-04-07", "snippet": "Buy now"},
        ]
        result = summarize_emails(emails, "week")

        assert result["summary"] == "You had 2 emails this week."
        assert len(result["highlights"]) == 1
        assert result["themes"] == ["finance"]
        assert len(result["action_items"]) == 1

        prompt = mock_llm.call_args[0][0]
        assert "2 total" in prompt
        assert "boss@co.com" in prompt

    @patch("summarizer._call_llm")
    def test_handles_empty_response(self, mock_llm):
        mock_llm.return_value = ""

        result = summarize_emails([{"from": "a", "subject": "b", "date": "c", "snippet": "d"}], "day")
        assert "summary" in result

    @patch("summarizer._call_llm")
    def test_handles_malformed_json_response(self, mock_llm):
        mock_llm.return_value = "Sorry, I can't do that."

        result = summarize_emails([{"from": "a", "subject": "b", "date": "c", "snippet": "d"}], "day")
        assert "summary" in result

    @patch("summarizer._call_llm")
    def test_email_prompt_rules_injected(self, mock_llm):
        mock_llm.return_value = '{"summary": "ok", "highlights": []}'

        with patch.dict("os.environ", {"EMAIL_PROMPT_RULES": "Ignore emails from github.com"}):
            summarize_emails(
                [{"from": "a", "subject": "b", "date": "c", "snippet": "d"}], "day"
            )
        prompt = mock_llm.call_args[0][0]
        assert "Ignore emails from github.com" in prompt
        assert "ADDITIONAL USER RULES" in prompt

    @patch("summarizer._call_llm")
    def test_no_rules_when_empty(self, mock_llm):
        mock_llm.return_value = '{"summary": "ok", "highlights": []}'

        with patch.dict("os.environ", {"EMAIL_PROMPT_RULES": ""}):
            summarize_emails(
                [{"from": "a", "subject": "b", "date": "c", "snippet": "d"}], "day"
            )
        prompt = mock_llm.call_args[0][0]
        assert "ADDITIONAL USER RULES" not in prompt


class TestSummarizeEvents:
    def test_empty_events_future(self):
        result = summarize_events([], "week", "future")
        assert "No upcoming" in result["summary"]

    def test_empty_events_past(self):
        result = summarize_events([], "month", "past")
        assert "No past" in result["summary"]

    def test_empty_events_current(self):
        result = summarize_events([], "day", "current")
        assert "No current" in result["summary"]

    @patch("summarizer._call_llm")
    def test_calls_llm_with_events(self, mock_llm):
        mock_llm.return_value = json.dumps({
            "summary": "Busy week with 5 meetings.",
            "highlights": [{"title": "Board review", "when": "Monday 10am", "why": "quarterly review", "attendees": ["ceo@co.com"]}],
            "themes": ["planning"],
            "action_items": ["Prep slide deck"],
            "stats": {"total_events": 5, "total_hours": 8},
        })

        events = [
            {
                "summary": "Board review",
                "start": "2026-04-09T10:00:00",
                "end": "2026-04-09T11:00:00",
                "location": "Room A",
                "attendees": ["ceo@co.com"],
                "organizer": "test@gmail.com",
                "description": "Quarterly board review",
            }
        ]
        result = summarize_events(events, "week", "future")

        assert "Busy week" in result["summary"]
        assert result["stats"]["total_events"] == 5
        assert len(result["action_items"]) == 1

        prompt = mock_llm.call_args[0][0]
        assert "upcoming" in prompt
        assert "Board review" in prompt

    @patch("summarizer._call_llm")
    def test_past_direction_uses_past_wording(self, mock_llm):
        mock_llm.return_value = '{"summary": "Last week was quiet.", "highlights": []}'

        events = [{"summary": "1:1", "start": "2026-04-02", "end": "2026-04-02",
                    "location": None, "attendees": [], "organizer": "a@b.com", "description": ""}]
        summarize_events(events, "week", "past")

        prompt = mock_llm.call_args[0][0]
        assert "past" in prompt.lower()

    @patch("summarizer._call_llm")
    def test_current_direction_uses_current_wording(self, mock_llm):
        mock_llm.return_value = '{"summary": "Today is busy.", "highlights": []}'

        events = [{"summary": "Standup", "start": "2026-04-16", "end": "2026-04-16",
                    "location": None, "attendees": [], "organizer": "a@b.com", "description": ""}]
        summarize_events(events, "day", "current")

        prompt = mock_llm.call_args[0][0]
        assert "current" in prompt.lower()

    @patch("summarizer._call_llm")
    def test_calendar_prompt_rules_injected(self, mock_llm):
        mock_llm.return_value = '{"summary": "ok", "highlights": []}'

        with patch.dict("os.environ", {"CALENDAR_PROMPT_RULES": "Ignore standups"}):
            summarize_events(
                [{"summary": "x", "start": "a", "end": "b", "location": None,
                  "attendees": [], "organizer": "a@b.com", "description": ""}],
                "day", "future"
            )
        prompt = mock_llm.call_args[0][0]
        assert "Ignore standups" in prompt
