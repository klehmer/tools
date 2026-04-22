"""Read-only wrapper around Gmail and Google Calendar."""
import base64
from datetime import datetime, timedelta, timezone, date
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


def _period_to_timedelta(period: str) -> timedelta:
    return {
        "day": timedelta(days=1),
        "week": timedelta(days=7),
        "month": timedelta(days=30),
        "quarter": timedelta(days=90),
    }.get(period, timedelta(days=7))


class GoogleService:
    def __init__(self, credentials: Credentials):
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        self.creds = credentials
        self.gmail = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        self.calendar = build("calendar", "v3", credentials=credentials, cache_discovery=False)

    # ---- Profile ----
    def get_user_profile(self) -> dict:
        oauth = build("oauth2", "v2", credentials=self.creds, cache_discovery=False)
        info = oauth.userinfo().get().execute()
        return {
            "email": info.get("email"),
            "name": info.get("name"),
            "picture": info.get("picture"),
        }

    # ---- Gmail ----
    def fetch_emails(self, period: str, max_results: int = 100) -> list[dict]:
        delta = _period_to_timedelta(period)
        # Gmail accepts unix-timestamp queries via after:
        after = int((datetime.now(tz=timezone.utc) - delta).timestamp())
        query = f"in:inbox after:{after}"
        msgs: list[dict] = []
        next_token: Optional[str] = None
        fetched = 0
        while fetched < max_results:
            resp = (
                self.gmail.users()
                .messages()
                .list(userId="me", q=query, maxResults=min(100, max_results - fetched), pageToken=next_token)
                .execute()
            )
            ids = resp.get("messages", [])
            if not ids:
                break
            for m in ids:
                full = (
                    self.gmail.users()
                    .messages()
                    .get(userId="me", id=m["id"], format="metadata",
                         metadataHeaders=["From", "Subject", "Date", "To"])
                    .execute()
                )
                headers = {h["name"]: h["value"] for h in full.get("payload", {}).get("headers", [])}
                msgs.append({
                    "id": m["id"],
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                    "snippet": full.get("snippet", ""),
                    "labels": full.get("labelIds", []),
                })
                fetched += 1
                if fetched >= max_results:
                    break
            next_token = resp.get("nextPageToken")
            if not next_token:
                break
        return msgs

    # ---- Calendar ----
    def fetch_events(self, period: str, direction: str = "future") -> list[dict]:
        delta = _period_to_timedelta(period)
        # Use local time for calendar day boundaries so "today" matches the user's timezone
        local_now = datetime.now().astimezone()
        local_tz = local_now.tzinfo
        today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)

        if direction == "current":
            if period == "day":
                time_min, time_max = today_start, tomorrow_start
            elif period == "week":
                weekday = today_start.weekday()  # Mon=0
                week_start = today_start - timedelta(days=weekday)
                time_min, time_max = week_start, week_start + timedelta(days=7)
            elif period == "month":
                month_start = today_start.replace(day=1)
                next_month = (month_start.month % 12) + 1
                next_year = month_start.year + (1 if next_month == 1 else 0)
                month_end = month_start.replace(year=next_year, month=next_month)
                time_min, time_max = month_start, month_end
            elif period == "quarter":
                q_month = ((today_start.month - 1) // 3) * 3 + 1
                q_start = today_start.replace(month=q_month, day=1)
                q_end_month = q_month + 3
                q_end_year = q_start.year
                if q_end_month > 12:
                    q_end_month -= 12
                    q_end_year += 1
                q_end = q_start.replace(year=q_end_year, month=q_end_month, day=1)
                time_min, time_max = q_start, q_end
            else:
                time_min, time_max = today_start, tomorrow_start
        elif direction == "past":
            # Previous: the full prior day/week/etc ending at start of today
            if period == "day":
                time_min, time_max = today_start - timedelta(days=1), today_start
            elif period == "week":
                weekday = today_start.weekday()
                this_week_start = today_start - timedelta(days=weekday)
                time_min, time_max = this_week_start - timedelta(days=7), this_week_start
            elif period == "month":
                month_start = today_start.replace(day=1)
                prev_month_end = month_start
                prev_month_start = (month_start - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if local_tz:
                    prev_month_start = prev_month_start.replace(tzinfo=local_tz)
                time_min, time_max = prev_month_start, prev_month_end
            elif period == "quarter":
                q_month = ((today_start.month - 1) // 3) * 3 + 1
                q_start = today_start.replace(month=q_month, day=1)
                prev_q_end = q_start
                prev_q_start_month = q_month - 3
                prev_q_start_year = q_start.year
                if prev_q_start_month < 1:
                    prev_q_start_month += 12
                    prev_q_start_year -= 1
                prev_q_start = today_start.replace(year=prev_q_start_year, month=prev_q_start_month, day=1)
                time_min, time_max = prev_q_start, prev_q_end
            else:
                time_min, time_max = today_start - timedelta(days=1), today_start
        else:
            # Upcoming/future: the next full day/week/etc starting after today
            if period == "day":
                time_min, time_max = tomorrow_start, tomorrow_start + timedelta(days=1)
            elif period == "week":
                weekday = today_start.weekday()
                next_week_start = today_start - timedelta(days=weekday) + timedelta(days=7)
                time_min, time_max = next_week_start, next_week_start + timedelta(days=7)
            elif period == "month":
                next_month_num = (today_start.month % 12) + 1
                next_month_year = today_start.year + (1 if next_month_num == 1 else 0)
                next_month_start = today_start.replace(year=next_month_year, month=next_month_num, day=1)
                after_month_num = (next_month_num % 12) + 1
                after_month_year = next_month_year + (1 if after_month_num == 1 else 0)
                next_month_end = today_start.replace(year=after_month_year, month=after_month_num, day=1)
                time_min, time_max = next_month_start, next_month_end
            elif period == "quarter":
                q_month = ((today_start.month - 1) // 3) * 3 + 1
                next_q_month = q_month + 3
                next_q_year = today_start.year
                if next_q_month > 12:
                    next_q_month -= 12
                    next_q_year += 1
                next_q_start = today_start.replace(year=next_q_year, month=next_q_month, day=1)
                after_q_month = next_q_month + 3
                after_q_year = next_q_year
                if after_q_month > 12:
                    after_q_month -= 12
                    after_q_year += 1
                next_q_end = today_start.replace(year=after_q_year, month=after_q_month, day=1)
                time_min, time_max = next_q_start, next_q_end
            else:
                time_min, time_max = tomorrow_start, tomorrow_start + timedelta(days=1)

        events: list[dict] = []
        page_token: Optional[str] = None
        while True:
            resp = (
                self.calendar.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=250,
                    pageToken=page_token,
                )
                .execute()
            )
            for ev in resp.get("items", []):
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
