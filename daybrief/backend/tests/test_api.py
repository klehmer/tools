"""Tests for FastAPI routes (main.py)."""
import json
from unittest.mock import MagicMock, patch

import pytest


class TestConfigRoutes:
    def test_config_status(self, client):
        resp = client.get("/config/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data
        assert "google_configured" in data
        assert "ai_configured" in data

    def test_get_config(self, client):
        resp = client.get("/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "GOOGLE_CLIENT_ID" in data

    @patch("config_manager.save_config")
    def test_post_config(self, mock_save, client):
        resp = client.post("/config", json={"GOOGLE_CLIENT_ID": "new-id"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_save.assert_called_once()


class TestAuthRoutes:
    @patch("auth.get_auth_url", return_value="https://accounts.google.com/auth?state=abc")
    def test_auth_url(self, mock_url, client):
        resp = client.get("/auth/url")
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://accounts.google.com/auth?state=abc"

    @patch("auth.exchange_code", return_value="session-token-123")
    def test_auth_callback_success(self, mock_exchange, client):
        resp = client.get("/auth/callback?code=authcode&state=s1", follow_redirects=False)
        assert resp.status_code == 307
        assert "session_token=session-token-123" in resp.headers["location"]

    @patch("auth.exchange_code", side_effect=Exception("token exchange failed"))
    def test_auth_callback_failure(self, mock_exchange, client):
        resp = client.get("/auth/callback?code=bad&state=s1", follow_redirects=False)
        assert resp.status_code == 307
        assert "error=auth_failed" in resp.headers["location"]

    def test_logout_requires_token(self, client):
        resp = client.post("/auth/logout")
        assert resp.status_code == 401

    @patch("auth.delete_session")
    def test_logout_with_token(self, mock_del, client):
        resp = client.post("/auth/logout", headers={"X-Session-Token": "tok1"})
        assert resp.status_code == 200
        mock_del.assert_called_once_with("tok1")


class TestMeRoute:
    def test_me_returns_profile(self, client, mock_google_service):
        resp = client.get("/auth/me", headers={"X-Session-Token": "valid"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@gmail.com"

    def test_me_requires_auth(self, raw_client):
        resp = raw_client.get("/auth/me")
        assert resp.status_code == 401


class TestSummaryRoutes:
    @patch("main.summarize_emails")
    def test_email_summary_default_period(self, mock_summarize, client, mock_google_service):
        mock_summarize.return_value = {
            "summary": "A busy week.",
            "highlights": [{"title": "Important email"}],
            "themes": ["work"],
            "action_items": [],
        }
        resp = client.get("/summary/emails", headers={"X-Session-Token": "valid"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == "A busy week."
        assert data["count"] == 2  # mock_google_service returns 2 emails
        assert data["period"] == "week"
        mock_google_service.fetch_emails.assert_called_once_with(period="week", max_results=200)

    @patch("main.summarize_emails")
    def test_email_summary_custom_period(self, mock_summarize, client, mock_google_service):
        mock_summarize.return_value = {"summary": "Quiet day.", "highlights": []}
        resp = client.get("/summary/emails?period=day", headers={"X-Session-Token": "valid"})
        assert resp.status_code == 200
        assert resp.json()["period"] == "day"
        mock_google_service.fetch_emails.assert_called_once_with(period="day", max_results=200)

    def test_email_summary_invalid_period(self, client):
        resp = client.get("/summary/emails?period=year", headers={"X-Session-Token": "valid"})
        assert resp.status_code == 422

    def test_email_summary_requires_auth(self, raw_client):
        resp = raw_client.get("/summary/emails")
        assert resp.status_code == 401

    @patch("main.summarize_events")
    def test_calendar_summary_future(self, mock_summarize, client, mock_google_service):
        mock_summarize.return_value = {
            "summary": "Busy week ahead.",
            "highlights": [],
            "stats": {"total_events": 1, "total_hours": 0.5},
        }
        resp = client.get("/summary/calendar?period=week&direction=future", headers={"X-Session-Token": "valid"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["direction"] == "future"
        assert data["count"] == 1  # mock returns 1 event
        mock_google_service.fetch_events.assert_called_once_with(period="week", direction="future")

    @patch("main.summarize_events")
    def test_calendar_summary_past(self, mock_summarize, client, mock_google_service):
        mock_summarize.return_value = {"summary": "Last month was quiet.", "highlights": []}
        resp = client.get("/summary/calendar?period=month&direction=past", headers={"X-Session-Token": "valid"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["direction"] == "past"
        assert data["period"] == "month"

    def test_calendar_summary_invalid_direction(self, client):
        resp = client.get("/summary/calendar?direction=sideways", headers={"X-Session-Token": "valid"})
        assert resp.status_code == 422

    def test_calendar_summary_requires_auth(self, raw_client):
        resp = raw_client.get("/summary/calendar")
        assert resp.status_code == 401

    @patch("main.summarize_events")
    def test_calendar_summary_current_direction(self, mock_summarize, client, mock_google_service):
        mock_summarize.return_value = {"summary": "Today is busy.", "highlights": []}
        resp = client.get("/summary/calendar?period=day&direction=current", headers={"X-Session-Token": "valid"})
        assert resp.status_code == 200
        assert resp.json()["direction"] == "current"


class TestSlackRoutes:
    @patch("slack_notifier.send_to_slack", return_value=True)
    def test_slack_send_success(self, mock_send, client, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/x")
        resp = client.post("/slack/send", json={
            "summary": {"summary": "test", "count": 1},
            "mode": "emails",
            "period": "day",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_slack_send_no_webhook(self, client, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
        resp = client.post("/slack/send", json={
            "summary": {"summary": "test"},
            "mode": "emails",
            "period": "day",
        })
        assert resp.status_code == 400

    @patch("slack_notifier.send_to_slack", return_value=False)
    def test_slack_send_failure(self, mock_send, client, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/x")
        resp = client.post("/slack/send", json={
            "summary": {"summary": "test"},
            "mode": "emails",
            "period": "day",
        })
        assert resp.status_code == 502


class TestReportRoutes:
    @patch("scheduler.save_adhoc_report")
    def test_save_adhoc_report(self, mock_save, client):
        mock_save.return_value = {
            "id": "abc",
            "job_id": "adhoc",
            "job_name": "Test Report",
            "created_at": "2026-04-16T12:00:00",
            "results": {"email": {"summary": "test"}},
        }
        resp = client.post("/reports", json={
            "name": "Test Report",
            "results": {"email": {"summary": "test"}},
        })
        assert resp.status_code == 200
        assert resp.json()["job_id"] == "adhoc"
        mock_save.assert_called_once()


class TestAnalyticsRoutes:
    @patch("analytics.generate")
    @patch("scheduler.get_report")
    def test_generate_analytics(self, mock_get_report, mock_generate, client):
        mock_get_report.return_value = {
            "id": "r1",
            "results": {"email": {"summary": "test"}},
        }
        mock_generate.return_value = {
            "overall_summary": "Analysis complete.",
            "cross_insights": [],
        }
        resp = client.post("/analytics", json={"report_ids": ["r1"]})
        assert resp.status_code == 200
        assert resp.json()["overall_summary"] == "Analysis complete."

    @patch("scheduler.get_report", return_value=None)
    def test_generate_analytics_no_valid_reports(self, mock_get, client):
        resp = client.post("/analytics", json={"report_ids": ["bad-id"]})
        assert resp.status_code == 400

    @patch("scheduler.save_analytics_report")
    def test_save_analytics_report(self, mock_save, client):
        mock_save.return_value = {
            "id": "a1",
            "type": "analytics",
            "name": "Weekly Analysis",
            "analytics": {"overall_summary": "ok"},
            "source_report_ids": ["r1"],
            "created_at": "2026-04-16T12:00:00",
        }
        resp = client.post("/analytics/reports", json={
            "name": "Weekly Analysis",
            "analytics": {"overall_summary": "ok"},
            "source_report_ids": ["r1"],
        })
        assert resp.status_code == 200
        assert resp.json()["type"] == "analytics"

    @patch("scheduler.get_analytics_reports")
    def test_list_analytics_reports(self, mock_list, client):
        mock_list.return_value = [{"id": "a1", "name": "test"}]
        resp = client.get("/analytics/reports")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @patch("scheduler.delete_analytics_report", return_value=True)
    def test_delete_analytics_report(self, mock_del, client):
        resp = client.delete("/analytics/reports/a1")
        assert resp.status_code == 200

    @patch("scheduler.delete_analytics_report", return_value=False)
    def test_delete_analytics_report_not_found(self, mock_del, client):
        resp = client.delete("/analytics/reports/bad")
        assert resp.status_code == 404
