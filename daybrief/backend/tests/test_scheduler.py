"""Tests for scheduler module."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scheduler


@pytest.fixture(autouse=True)
def isolate_data(tmp_path, monkeypatch):
    """Redirect scheduler data to tmp dir."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    reports_dir = data_dir / "reports"
    reports_dir.mkdir()
    monkeypatch.setattr(scheduler, "_DATA_DIR", data_dir)
    monkeypatch.setattr(scheduler, "_JOBS_FILE", data_dir / "scheduled_jobs.json")
    monkeypatch.setattr(scheduler, "_REPORTS_DIR", reports_dir)
    monkeypatch.setattr(scheduler, "_scheduler", None)


class TestJobCRUD:
    def test_create_job(self):
        job = scheduler.create_job({"name": "Test Job", "tasks": [{"type": "email", "period": "day"}]})
        assert job["name"] == "Test Job"
        assert job["enabled"] is True
        assert job["run_missed"] is False
        assert job["send_to_slack"] is False
        assert job["last_run"] is None

    def test_get_jobs(self):
        scheduler.create_job({"name": "Job 1"})
        scheduler.create_job({"name": "Job 2"})
        jobs = scheduler.get_jobs()
        assert len(jobs) == 2

    def test_get_job(self):
        job = scheduler.create_job({"name": "Find Me"})
        found = scheduler.get_job(job["id"])
        assert found["name"] == "Find Me"

    def test_get_job_not_found(self):
        assert scheduler.get_job("nonexistent") is None

    def test_update_job(self):
        job = scheduler.create_job({"name": "Original"})
        updated = scheduler.update_job(job["id"], {"name": "Updated", "run_missed": True, "send_to_slack": True})
        assert updated["name"] == "Updated"
        assert updated["run_missed"] is True
        assert updated["send_to_slack"] is True

    def test_update_job_not_found(self):
        assert scheduler.update_job("nonexistent", {"name": "x"}) is None

    def test_delete_job(self):
        job = scheduler.create_job({"name": "Delete Me"})
        assert scheduler.delete_job(job["id"]) is True
        assert scheduler.get_job(job["id"]) is None

    def test_delete_job_not_found(self):
        assert scheduler.delete_job("nonexistent") is False


class TestReports:
    def test_save_adhoc_report(self):
        report = scheduler.save_adhoc_report("Test", {"email": {"summary": "hi"}})
        assert report["job_id"] == "adhoc"
        assert report["job_name"] == "Test"

    def test_get_reports(self):
        scheduler.save_adhoc_report("R1", {"email": {"summary": "a"}})
        scheduler.save_adhoc_report("R2", {"calendar": {"summary": "b"}})
        reports = scheduler.get_reports()
        assert len(reports) == 2

    def test_get_report(self):
        report = scheduler.save_adhoc_report("Find", {"email": {"summary": "x"}})
        found = scheduler.get_report(report["id"])
        assert found["job_name"] == "Find"

    def test_get_report_not_found(self):
        assert scheduler.get_report("nonexistent") is None

    def test_delete_report(self):
        report = scheduler.save_adhoc_report("Del", {"email": {"summary": "x"}})
        assert scheduler.delete_report(report["id"]) is True
        assert scheduler.get_report(report["id"]) is None

    def test_delete_report_not_found(self):
        assert scheduler.delete_report("nonexistent") is False

    def test_reports_exclude_analytics(self):
        scheduler.save_adhoc_report("Regular", {"email": {"summary": "x"}})
        scheduler.save_analytics_report("Analytics", {"overall_summary": "y"}, ["r1"])
        reports = scheduler.get_reports()
        assert len(reports) == 1
        assert reports[0]["job_name"] == "Regular"


class TestAnalyticsReports:
    def test_save_analytics_report(self):
        report = scheduler.save_analytics_report("Weekly", {"overall_summary": "ok"}, ["r1", "r2"])
        assert report["type"] == "analytics"
        assert report["name"] == "Weekly"
        assert report["source_report_ids"] == ["r1", "r2"]

    def test_get_analytics_reports(self):
        scheduler.save_analytics_report("A1", {"summary": "a"}, ["r1"])
        scheduler.save_analytics_report("A2", {"summary": "b"}, ["r2"])
        reports = scheduler.get_analytics_reports()
        assert len(reports) == 2

    def test_get_analytics_report(self):
        report = scheduler.save_analytics_report("Find", {"summary": "x"}, ["r1"])
        found = scheduler.get_analytics_report(report["id"])
        assert found["name"] == "Find"

    def test_get_analytics_report_not_found(self):
        assert scheduler.get_analytics_report("nonexistent") is None

    def test_delete_analytics_report(self):
        report = scheduler.save_analytics_report("Del", {"summary": "x"}, ["r1"])
        assert scheduler.delete_analytics_report(report["id"]) is True
        assert scheduler.get_analytics_report(report["id"]) is None

    def test_delete_analytics_report_not_found(self):
        assert scheduler.delete_analytics_report("nonexistent") is False


class TestScheduleInterval:
    def test_hourly(self):
        assert scheduler._schedule_interval({"type": "hourly"}) == timedelta(hours=1)

    def test_daily(self):
        assert scheduler._schedule_interval({"type": "daily"}) == timedelta(days=1)

    def test_weekdays(self):
        assert scheduler._schedule_interval({"type": "weekdays"}) == timedelta(days=1)

    def test_weekly(self):
        assert scheduler._schedule_interval({"type": "weekly"}) == timedelta(weeks=1)

    def test_monthly(self):
        assert scheduler._schedule_interval({"type": "monthly"}) == timedelta(days=30)

    def test_unknown_defaults_daily(self):
        assert scheduler._schedule_interval({"type": "unknown"}) == timedelta(days=1)


class TestRunMissedJobs:
    def test_skips_disabled_jobs(self):
        jobs = [{"id": "j1", "enabled": False, "run_missed": True, "last_run": None}]
        with patch.object(scheduler, "_execute_job") as mock_exec:
            scheduler._run_missed_jobs(jobs)
            mock_exec.assert_not_called()

    def test_skips_run_missed_false(self):
        jobs = [{"id": "j1", "enabled": True, "run_missed": False, "last_run": None}]
        with patch.object(scheduler, "_execute_job") as mock_exec:
            scheduler._run_missed_jobs(jobs)
            mock_exec.assert_not_called()

    def test_runs_never_run_job(self):
        jobs = [{"id": "j1", "enabled": True, "run_missed": True, "last_run": None, "schedule": {"type": "daily"}}]
        with patch("scheduler.Thread") as mock_thread:
            scheduler._run_missed_jobs(jobs)
            mock_thread.assert_called_once()

    def test_runs_missed_job(self):
        old_time = (datetime.now() - timedelta(days=2)).isoformat()
        jobs = [{
            "id": "j1", "enabled": True, "run_missed": True,
            "last_run": old_time, "schedule": {"type": "daily"},
        }]
        with patch("scheduler.Thread") as mock_thread:
            scheduler._run_missed_jobs(jobs)
            mock_thread.assert_called_once()

    def test_skips_recent_job(self):
        recent = (datetime.now() - timedelta(hours=1)).isoformat()
        jobs = [{
            "id": "j1", "enabled": True, "run_missed": True,
            "last_run": recent, "schedule": {"type": "daily"},
        }]
        with patch("scheduler.Thread") as mock_thread:
            scheduler._run_missed_jobs(jobs)
            mock_thread.assert_not_called()


class TestUpdateJobStatus:
    def test_updates_status(self):
        job = scheduler.create_job({"name": "Status Test"})
        scheduler._update_job_status(job["id"], "success", "All good")
        updated = scheduler.get_job(job["id"])
        assert updated["last_status"] == "success"
        assert updated["last_message"] == "All good"
        assert updated["last_run"] is not None


class TestRunJobNow:
    def test_returns_none_for_nonexistent(self):
        assert scheduler.run_job_now("nonexistent") is None

    def test_returns_job_and_starts_thread(self):
        job = scheduler.create_job({"name": "Run Now"})
        with patch("scheduler.Thread") as mock_thread:
            result = scheduler.run_job_now(job["id"])
            assert result["name"] == "Run Now"
            mock_thread.assert_called_once()


class TestExecuteJob:
    def test_no_session_token(self):
        job = scheduler.create_job({"name": "No Token", "session_token": ""})
        scheduler._execute_job(job["id"])
        updated = scheduler.get_job(job["id"])
        assert updated["last_status"] == "error"

    @patch("scheduler.auth.get_credentials", return_value=None)
    def test_expired_session(self, mock_creds):
        job = scheduler.create_job({"name": "Expired", "session_token": "tok"})
        scheduler._execute_job(job["id"])
        updated = scheduler.get_job(job["id"])
        assert updated["last_status"] == "error"
        assert "expired" in updated["last_message"].lower()

    @patch("scheduler._send_slack")
    @patch("scheduler._send_notification")
    @patch("scheduler.summarize_emails", return_value={"summary": "ok"})
    @patch("scheduler.GoogleService")
    @patch("scheduler.auth.get_credentials")
    def test_successful_email_job(self, mock_creds, mock_gs_cls, mock_summarize, mock_notify, mock_slack):
        mock_creds.return_value = MagicMock()
        mock_gs = MagicMock()
        mock_gs.fetch_emails.return_value = [{"from": "a", "subject": "b"}]
        mock_gs_cls.return_value = mock_gs

        job = scheduler.create_job({
            "name": "Email Job",
            "session_token": "tok",
            "tasks": [{"type": "email", "period": "day"}],
            "notification": {"enabled": True, "style": "banner"},
            "send_to_slack": True,
        })
        scheduler._execute_job(job["id"])

        updated = scheduler.get_job(job["id"])
        assert updated["last_status"] == "success"
        mock_notify.assert_called_once()
        mock_slack.assert_called_once()

    @patch("scheduler._send_slack")
    @patch("scheduler.summarize_events", return_value={"summary": "ok"})
    @patch("scheduler.GoogleService")
    @patch("scheduler.auth.get_credentials")
    def test_successful_calendar_job(self, mock_creds, mock_gs_cls, mock_summarize, mock_slack):
        mock_creds.return_value = MagicMock()
        mock_gs = MagicMock()
        mock_gs.fetch_events.return_value = [{"summary": "mtg"}]
        mock_gs_cls.return_value = mock_gs

        job = scheduler.create_job({
            "name": "Cal Job",
            "session_token": "tok",
            "tasks": [{"type": "calendar", "period": "week", "direction": "current"}],
        })
        scheduler._execute_job(job["id"])
        updated = scheduler.get_job(job["id"])
        assert updated["last_status"] == "success"

    @patch("scheduler.GoogleService")
    @patch("scheduler.auth.get_credentials")
    def test_job_exception(self, mock_creds, mock_gs_cls):
        mock_creds.return_value = MagicMock()
        mock_gs_cls.side_effect = Exception("boom")

        job = scheduler.create_job({"name": "Fail", "session_token": "tok", "tasks": [{"type": "email", "period": "day"}]})
        scheduler._execute_job(job["id"])
        updated = scheduler.get_job(job["id"])
        assert updated["last_status"] == "error"
        assert "boom" in updated["last_message"]


class TestSendSlack:
    @patch("scheduler.slack_notifier.send_to_slack", return_value=True)
    @patch("scheduler.slack_notifier.format_summary_for_slack", return_value={"blocks": []})
    def test_sends_for_each_task(self, mock_format, mock_send, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
        job = {
            "id": "j1",
            "tasks": [
                {"type": "email", "period": "day"},
                {"type": "calendar", "period": "week", "direction": "current"},
            ],
        }
        results = {
            "email": {"summary": "emails ok", "count": 5},
            "calendar": {"summary": "cal ok", "count": 3},
        }
        scheduler._send_slack(job, results)
        assert mock_format.call_count == 2
        assert mock_send.call_count == 2

    def test_skips_when_no_webhook(self, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
        with patch("scheduler.slack_notifier.send_to_slack") as mock_send:
            scheduler._send_slack({"id": "j1", "tasks": [{"type": "email", "period": "day"}]}, {"email": {"summary": "x"}})
            mock_send.assert_not_called()


class TestBuildTrigger:
    def test_hourly(self):
        trigger = scheduler._build_trigger({"type": "hourly", "time": "00:30"})
        assert trigger is not None

    def test_daily(self):
        trigger = scheduler._build_trigger({"type": "daily", "time": "08:00"})
        assert trigger is not None

    def test_weekdays(self):
        trigger = scheduler._build_trigger({"type": "weekdays", "time": "09:00"})
        assert trigger is not None

    def test_weekly(self):
        trigger = scheduler._build_trigger({"type": "weekly", "time": "08:00", "day_of_week": "mon"})
        assert trigger is not None

    def test_monthly(self):
        trigger = scheduler._build_trigger({"type": "monthly", "time": "08:00", "day_of_month": 15})
        assert trigger is not None

    def test_unknown_defaults(self):
        trigger = scheduler._build_trigger({"type": "unknown", "time": "12:00"})
        assert trigger is not None
