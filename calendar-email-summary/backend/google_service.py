"""Read-only wrapper around Gmail and Google Calendar."""
import base64
from datetime import datetime, timedelta, timezone
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
        now = datetime.now(tz=timezone.utc)
        if direction == "past":
            time_min, time_max = now - delta, now
        else:
            time_min, time_max = now, now + delta

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
