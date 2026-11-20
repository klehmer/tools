"""Tests for analytics module."""
import json
from unittest.mock import patch

from analytics import generate


class TestGenerate:
    @patch("analytics._call_llm")
    def test_with_calendar_reports(self, mock_llm):
        mock_llm.return_value = json.dumps({
            "calendar_analytics": {
                "hours_by_category": [{"category": "1:1s", "hours": 3}],
                "busiest_days": [{"day": "Monday", "event_count": 5, "hours": 4}],
                "recurring_patterns": ["Daily standup"],
                "top_attendees": [{"name": "Alice", "meeting_count": 8}],
                "meeting_load": {"total_events": 20, "total_hours": 15, "avg_per_day": 3},
                "summary": "Busy week.",
            },
            "cross_insights": ["Most meetings on Monday"],
            "overall_summary": "Packed schedule.",
        })

        reports = [
            {
                "id": "r1",
                "job_name": "Daily summary",
                "created_at": "2026-04-15T08:00:00",
                "results": {
                    "calendar": {
                        "summary": "5 meetings today",
                        "highlights": [{"title": "Board meeting"}],
                        "count": 5,
                    }
                },
            }
        ]
        result = generate(reports)
        assert "calendar_analytics" in result
        assert result["calendar_analytics"]["hours_by_category"][0]["category"] == "1:1s"
        assert result["overall_summary"] == "Packed schedule."

        prompt = mock_llm.call_args[0][0]
        assert "CALENDAR REPORTS" in prompt
        assert "Board meeting" in prompt

    @patch("analytics._call_llm")
    def test_with_email_reports(self, mock_llm):
        mock_llm.return_value = json.dumps({
            "email_analytics": {
                "top_senders": [{"sender": "github@github.com", "count": 50}],
                "categories": [{"category": "Automated", "pct": 70}],
                "response_needed": [],
                "volume_trend": [{"period": "Apr 15", "count": 80}],
                "summary": "Mostly automated.",
            },
            "cross_insights": [],
            "overall_summary": "High email volume.",
        })

        reports = [
            {
                "id": "r2",
                "job_name": "Email digest",
                "created_at": "2026-04-15T08:00:00",
                "results": {
                    "email": {
                        "summary": "80 emails",
                        "count": 80,
                    }
                },
            }
        ]
        result = generate(reports)
        assert "email_analytics" in result
        assert result["email_analytics"]["top_senders"][0]["sender"] == "github@github.com"

        prompt = mock_llm.call_args[0][0]
        assert "EMAIL REPORTS" in prompt

    def test_empty_reports(self):
        result = generate([{"id": "x", "job_name": "empty", "created_at": "2026-04-15", "results": {}}])
        assert "overall_summary" in result
        assert "No email or calendar data" in result["overall_summary"]

    @patch("analytics._call_llm")
    def test_mixed_reports(self, mock_llm):
        mock_llm.return_value = json.dumps({
            "calendar_analytics": {"summary": "ok", "hours_by_category": [], "busiest_days": [], "recurring_patterns": [], "top_attendees": []},
            "email_analytics": {"summary": "ok", "top_senders": [], "categories": [], "response_needed": [], "volume_trend": []},
            "cross_insights": ["Meetings follow email spikes"],
            "overall_summary": "Mixed data.",
        })

        reports = [
            {"id": "1", "job_name": "r1", "created_at": "2026-04-15", "results": {"calendar": {"summary": "a", "count": 1}}},
            {"id": "2", "job_name": "r2", "created_at": "2026-04-15", "results": {"email": {"summary": "b", "count": 2}}},
        ]
        result = generate(reports)
        assert result["cross_insights"] == ["Meetings follow email spikes"]

        prompt = mock_llm.call_args[0][0]
        assert "CALENDAR REPORTS" in prompt
        assert "EMAIL REPORTS" in prompt

    @patch("analytics._call_llm")
    def test_caps_at_20_reports(self, mock_llm):
        mock_llm.return_value = '{"overall_summary": "ok", "cross_insights": []}'

        reports = [
            {"id": str(i), "job_name": f"r{i}", "created_at": "2026-04-15",
             "results": {"email": {"summary": f"email {i}", "count": i}}}
            for i in range(30)
        ]
        generate(reports)
        prompt = mock_llm.call_args[0][0]
        assert "20 reports" in prompt
