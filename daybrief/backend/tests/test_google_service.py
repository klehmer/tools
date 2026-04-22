"""Tests for google_service module."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from google_service import GoogleService, _period_to_timedelta


class TestPeriodToTimedelta:
    def test_day(self):
        assert _period_to_timedelta("day") == timedelta(days=1)

    def test_week(self):
        assert _period_to_timedelta("week") == timedelta(days=7)

    def test_month(self):
        assert _period_to_timedelta("month") == timedelta(days=30)

    def test_quarter(self):
        assert _period_to_timedelta("quarter") == timedelta(days=90)

    def test_unknown_defaults_to_week(self):
        assert _period_to_timedelta("invalid") == timedelta(days=7)
        assert _period_to_timedelta("") == timedelta(days=7)


class TestGoogleServiceInit:
    @patch("google_service.build")
    def test_refreshes_expired_creds(self, mock_build):
        creds = MagicMock()
        creds.expired = True
        creds.refresh_token = "rt"
        GoogleService(creds)
        creds.refresh.assert_called_once()

    @patch("google_service.build")
    def test_does_not_refresh_valid_creds(self, mock_build):
        creds = MagicMock()
        creds.expired = False
        creds.refresh_token = "rt"
        GoogleService(creds)
        creds.refresh.assert_not_called()

    @patch("google_service.build")
    def test_builds_gmail_and_calendar(self, mock_build):
        creds = MagicMock(expired=False)
        svc = GoogleService(creds)
        # build called 2 times: gmail v1 + calendar v3
        assert mock_build.call_count == 2
        calls = [c.kwargs or dict(zip(["serviceName", "version"], c.args[:2])) for c in mock_build.call_args_list]
        service_names = [c[0][0] if c[0] else c[1].get("serviceName") for c in mock_build.call_args_list]
        assert "gmail" in service_names
        assert "calendar" in service_names


class TestGetUserProfile:
    @patch("google_service.build")
    def test_returns_profile_dict(self, mock_build):
        creds = MagicMock(expired=False)
        oauth_svc = MagicMock()
        oauth_svc.userinfo.return_value.get.return_value.execute.return_value = {
            "email": "test@gmail.com",
            "name": "Test User",
            "picture": "https://photo.url/pic.jpg",
        }
        # First two calls are __init__ (gmail, calendar), third is in get_user_profile
        mock_build.side_effect = [MagicMock(), MagicMock(), oauth_svc]

        svc = GoogleService(creds)
        profile = svc.get_user_profile()
        assert profile["email"] == "test@gmail.com"
        assert profile["name"] == "Test User"
        assert profile["picture"] == "https://photo.url/pic.jpg"


class TestFetchEmails:
    @patch("google_service.build")
    def test_returns_parsed_emails(self, mock_build):
        creds = MagicMock(expired=False)

        gmail_mock = MagicMock()
        list_resp = {
            "messages": [{"id": "m1"}, {"id": "m2"}],
        }
        gmail_mock.users.return_value.messages.return_value.list.return_value.execute.return_value = list_resp

        def get_msg(userId, id, format, metadataHeaders):
            return MagicMock(execute=MagicMock(return_value={
                "id": id,
                "snippet": f"snippet-{id}",
                "labelIds": ["INBOX"],
                "payload": {
                    "headers": [
                        {"name": "From", "value": f"sender-{id}@test.com"},
                        {"name": "Subject", "value": f"Subject {id}"},
                        {"name": "Date", "value": "Mon, 07 Apr 2026 09:00:00"},
                        {"name": "To", "value": "me@test.com"},
                    ]
                },
            }))

        gmail_mock.users.return_value.messages.return_value.get.side_effect = get_msg
        mock_build.side_effect = [gmail_mock, MagicMock()]  # gmail, calendar

        svc = GoogleService(creds)
        emails = svc.fetch_emails("week", max_results=10)

        assert len(emails) == 2
        assert emails[0]["id"] == "m1"
        assert emails[0]["from"] == "sender-m1@test.com"
        assert emails[0]["subject"] == "Subject m1"
        assert emails[1]["snippet"] == "snippet-m2"

    @patch("google_service.build")
    def test_respects_max_results(self, mock_build):
        creds = MagicMock(expired=False)
        gmail_mock = MagicMock()
        list_resp = {
            "messages": [{"id": f"m{i}"} for i in range(50)],
        }
        gmail_mock.users.return_value.messages.return_value.list.return_value.execute.return_value = list_resp
        gmail_mock.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "id": "x", "snippet": "", "labelIds": [],
            "payload": {"headers": []},
        }
        mock_build.side_effect = [gmail_mock, MagicMock()]

        svc = GoogleService(creds)
        emails = svc.fetch_emails("week", max_results=5)
        assert len(emails) == 5

    @patch("google_service.build")
    def test_handles_empty_inbox(self, mock_build):
        creds = MagicMock(expired=False)
        gmail_mock = MagicMock()
        gmail_mock.users.return_value.messages.return_value.list.return_value.execute.return_value = {}
        mock_build.side_effect = [gmail_mock, MagicMock()]

        svc = GoogleService(creds)
        assert svc.fetch_emails("day") == []


class TestFetchEvents:
    @patch("google_service.build")
    def test_returns_parsed_events(self, mock_build):
        creds = MagicMock(expired=False)
        cal_mock = MagicMock()
        cal_mock.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "e1",
                    "summary": "Team standup",
                    "description": "Daily sync",
                    "location": "Room A",
                    "start": {"dateTime": "2026-04-09T09:00:00-07:00"},
                    "end": {"dateTime": "2026-04-09T09:30:00-07:00"},
                    "attendees": [{"email": "bob@test.com"}],
                    "organizer": {"email": "me@test.com"},
                    "hangoutLink": "https://meet.google.com/abc",
                    "status": "confirmed",
                }
            ],
        }
        mock_build.side_effect = [MagicMock(), cal_mock]

        svc = GoogleService(creds)
        events = svc.fetch_events("week", "future")

        assert len(events) == 1
        assert events[0]["summary"] == "Team standup"
        assert events[0]["attendees"] == ["bob@test.com"]
        assert events[0]["organizer"] == "me@test.com"
        assert events[0]["hangoutLink"] == "https://meet.google.com/abc"

    @patch("google_service.build")
    def test_handles_all_day_events(self, mock_build):
        creds = MagicMock(expired=False)
        cal_mock = MagicMock()
        cal_mock.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "e2",
                    "summary": "Holiday",
                    "start": {"date": "2026-04-10"},
                    "end": {"date": "2026-04-11"},
                }
            ],
        }
        mock_build.side_effect = [MagicMock(), cal_mock]

        svc = GoogleService(creds)
        events = svc.fetch_events("week", "future")
        assert events[0]["start"] == "2026-04-10"
        assert events[0]["end"] == "2026-04-11"

    @patch("google_service.build")
    def test_empty_calendar(self, mock_build):
        creds = MagicMock(expired=False)
        cal_mock = MagicMock()
        cal_mock.events.return_value.list.return_value.execute.return_value = {"items": []}
        mock_build.side_effect = [MagicMock(), cal_mock]

        svc = GoogleService(creds)
        assert svc.fetch_events("day", "past") == []

    @patch("google_service.build")
    def test_current_day_uses_local_midnight_boundaries(self, mock_build):
        creds = MagicMock(expired=False)
        cal_mock = MagicMock()
        cal_mock.events.return_value.list.return_value.execute.return_value = {"items": []}
        mock_build.side_effect = [MagicMock(), cal_mock]

        svc = GoogleService(creds)
        svc.fetch_events("day", "current")

        call_kwargs = cal_mock.events.return_value.list.return_value.execute.call_args
        list_call = cal_mock.events.return_value.list.call_args
        time_min = list_call.kwargs["timeMin"]
        time_max = list_call.kwargs["timeMax"]
        # Should be midnight-to-midnight boundaries (T00:00:00)
        assert "T00:00:00" in time_min

    @patch("google_service.build")
    def test_current_week_spans_monday_to_sunday(self, mock_build):
        creds = MagicMock(expired=False)
        cal_mock = MagicMock()
        cal_mock.events.return_value.list.return_value.execute.return_value = {"items": []}
        mock_build.side_effect = [MagicMock(), cal_mock]

        svc = GoogleService(creds)
        svc.fetch_events("week", "current")

        list_call = cal_mock.events.return_value.list.call_args
        time_min = list_call.kwargs["timeMin"]
        time_max = list_call.kwargs["timeMax"]
        # Parse the dates and check they span 7 days
        min_dt = datetime.fromisoformat(time_min)
        max_dt = datetime.fromisoformat(time_max)
        assert (max_dt - min_dt).days == 7
        assert min_dt.weekday() == 0  # Monday

    @patch("google_service.build")
    def test_past_day_is_yesterday(self, mock_build):
        creds = MagicMock(expired=False)
        cal_mock = MagicMock()
        cal_mock.events.return_value.list.return_value.execute.return_value = {"items": []}
        mock_build.side_effect = [MagicMock(), cal_mock]

        svc = GoogleService(creds)
        svc.fetch_events("day", "past")

        list_call = cal_mock.events.return_value.list.call_args
        time_min = list_call.kwargs["timeMin"]
        time_max = list_call.kwargs["timeMax"]
        min_dt = datetime.fromisoformat(time_min)
        max_dt = datetime.fromisoformat(time_max)
        assert (max_dt - min_dt).days == 1
        assert "T00:00:00" in time_min
        assert "T00:00:00" in time_max

    @patch("google_service.build")
    def test_future_day_is_tomorrow(self, mock_build):
        creds = MagicMock(expired=False)
        cal_mock = MagicMock()
        cal_mock.events.return_value.list.return_value.execute.return_value = {"items": []}
        mock_build.side_effect = [MagicMock(), cal_mock]

        svc = GoogleService(creds)
        svc.fetch_events("day", "future")

        list_call = cal_mock.events.return_value.list.call_args
        time_min = list_call.kwargs["timeMin"]
        time_max = list_call.kwargs["timeMax"]
        min_dt = datetime.fromisoformat(time_min)
        max_dt = datetime.fromisoformat(time_max)
        assert (max_dt - min_dt).days == 1
        # tomorrow starts after today
        local_now = datetime.now().astimezone()
        today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        assert min_dt >= today_start + timedelta(days=1) - timedelta(seconds=1)

    @patch("google_service.build")
    def test_current_month_boundaries(self, mock_build):
        creds = MagicMock(expired=False)
        cal_mock = MagicMock()
        cal_mock.events.return_value.list.return_value.execute.return_value = {"items": []}
        mock_build.side_effect = [MagicMock(), cal_mock]

        svc = GoogleService(creds)
        svc.fetch_events("month", "current")

        list_call = cal_mock.events.return_value.list.call_args
        min_dt = datetime.fromisoformat(list_call.kwargs["timeMin"])
        max_dt = datetime.fromisoformat(list_call.kwargs["timeMax"])
        assert min_dt.day == 1
        assert max_dt.day == 1
        # Next month
        if min_dt.month == 12:
            assert max_dt.month == 1
        else:
            assert max_dt.month == min_dt.month + 1

    @patch("google_service.build")
    def test_current_quarter_boundaries(self, mock_build):
        creds = MagicMock(expired=False)
        cal_mock = MagicMock()
        cal_mock.events.return_value.list.return_value.execute.return_value = {"items": []}
        mock_build.side_effect = [MagicMock(), cal_mock]

        svc = GoogleService(creds)
        svc.fetch_events("quarter", "current")

        list_call = cal_mock.events.return_value.list.call_args
        min_dt = datetime.fromisoformat(list_call.kwargs["timeMin"])
        max_dt = datetime.fromisoformat(list_call.kwargs["timeMax"])
        assert min_dt.day == 1
        assert min_dt.month in (1, 4, 7, 10)
        # Quarter spans ~90 days
        assert 89 <= (max_dt - min_dt).days <= 92

    @patch("google_service.build")
    def test_past_week_boundaries(self, mock_build):
        creds = MagicMock(expired=False)
        cal_mock = MagicMock()
        cal_mock.events.return_value.list.return_value.execute.return_value = {"items": []}
        mock_build.side_effect = [MagicMock(), cal_mock]

        svc = GoogleService(creds)
        svc.fetch_events("week", "past")

        list_call = cal_mock.events.return_value.list.call_args
        min_dt = datetime.fromisoformat(list_call.kwargs["timeMin"])
        max_dt = datetime.fromisoformat(list_call.kwargs["timeMax"])
        assert (max_dt - min_dt).days == 7
        assert min_dt.weekday() == 0  # Monday
        assert max_dt.weekday() == 0  # Monday

    @patch("google_service.build")
    def test_future_week_boundaries(self, mock_build):
        creds = MagicMock(expired=False)
        cal_mock = MagicMock()
        cal_mock.events.return_value.list.return_value.execute.return_value = {"items": []}
        mock_build.side_effect = [MagicMock(), cal_mock]

        svc = GoogleService(creds)
        svc.fetch_events("week", "future")

        list_call = cal_mock.events.return_value.list.call_args
        min_dt = datetime.fromisoformat(list_call.kwargs["timeMin"])
        max_dt = datetime.fromisoformat(list_call.kwargs["timeMax"])
        assert (max_dt - min_dt).days == 7
        assert min_dt.weekday() == 0  # Monday

    @patch("google_service.build")
    def test_past_month_boundaries(self, mock_build):
        creds = MagicMock(expired=False)
        cal_mock = MagicMock()
        cal_mock.events.return_value.list.return_value.execute.return_value = {"items": []}
        mock_build.side_effect = [MagicMock(), cal_mock]

        svc = GoogleService(creds)
        svc.fetch_events("month", "past")

        list_call = cal_mock.events.return_value.list.call_args
        min_dt = datetime.fromisoformat(list_call.kwargs["timeMin"])
        max_dt = datetime.fromisoformat(list_call.kwargs["timeMax"])
        assert min_dt.day == 1
        assert max_dt.day == 1

    @patch("google_service.build")
    def test_future_month_boundaries(self, mock_build):
        creds = MagicMock(expired=False)
        cal_mock = MagicMock()
        cal_mock.events.return_value.list.return_value.execute.return_value = {"items": []}
        mock_build.side_effect = [MagicMock(), cal_mock]

        svc = GoogleService(creds)
        svc.fetch_events("month", "future")

        list_call = cal_mock.events.return_value.list.call_args
        min_dt = datetime.fromisoformat(list_call.kwargs["timeMin"])
        max_dt = datetime.fromisoformat(list_call.kwargs["timeMax"])
        assert min_dt.day == 1
        assert max_dt.day == 1

    @patch("google_service.build")
    def test_truncates_long_descriptions(self, mock_build):
        creds = MagicMock(expired=False)
        cal_mock = MagicMock()
        cal_mock.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "e3",
                    "summary": "Long desc event",
                    "description": "x" * 1000,
                    "start": {"dateTime": "2026-04-09T10:00:00"},
                    "end": {"dateTime": "2026-04-09T11:00:00"},
                }
            ],
        }
        mock_build.side_effect = [MagicMock(), cal_mock]

        svc = GoogleService(creds)
        events = svc.fetch_events("week")
        assert len(events[0]["description"]) == 500
