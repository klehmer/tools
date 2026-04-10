import base64
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GmailService:
    def __init__(self, credentials: Credentials):
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        self.service = build("gmail", "v1", credentials=credentials)
        self._user_info = None

    # ------------------------------------------------------------------ #
    # Profile / Overview                                                   #
    # ------------------------------------------------------------------ #

    def get_inbox_overview(self) -> Dict[str, Any]:
        """Return total message count, email address, and storage usage."""
        try:
            profile = self.service.users().getProfile(userId="me").execute()
            out = {
                "email_address": profile.get("emailAddress", ""),
                "total_messages": profile.get("messagesTotal", 0),
                "total_threads": profile.get("threadsTotal", 0),
            }
            try:
                from googleapiclient.discovery import build as _build
                drive = _build("drive", "v3", credentials=self.service._http.credentials)
                about = drive.about().get(fields="storageQuota").execute()
                quota = about.get("storageQuota", {})
                out["storage_used_bytes"] = int(quota.get("usage", 0))
                out["storage_limit_bytes"] = int(quota.get("limit", 0)) if quota.get("limit") else None
            except Exception:
                out["storage_used_bytes"] = None
                out["storage_limit_bytes"] = None
            return out
        except HttpError as e:
            return {"error": str(e)}

    def get_user_profile(self) -> Dict[str, Any]:
        """Return basic user profile info."""
        try:
            from googleapiclient.discovery import build as _build
            from google.oauth2.credentials import Credentials

            oauth2 = _build("oauth2", "v2", credentials=self.service._http.credentials)
            info = oauth2.userinfo().get().execute()
            return {
                "email": info.get("email", ""),
                "name": info.get("name", ""),
                "picture": info.get("picture", ""),
            }
        except Exception:
            profile = self.service.users().getProfile(userId="me").execute()
            return {"email": profile.get("emailAddress", ""), "name": "", "picture": ""}

    # ------------------------------------------------------------------ #
    # Sender Analysis                                                      #
    # ------------------------------------------------------------------ #

    def get_top_senders(self, limit: int = 30) -> Dict[str, Any]:
        """
        Sample up to 500 inbox messages and tally by sender.
        Uses batch requests to minimise API calls.
        """
        sender_stats: Dict[str, Dict] = defaultdict(
            lambda: {"count": 0, "size_bytes": 0, "ids": []}
        )

        # Fetch up to 500 message IDs from INBOX
        result = self.service.users().messages().list(
            userId="me", maxResults=500, labelIds=["INBOX"]
        ).execute()
        messages = result.get("messages", [])
        if not messages:
            return {"senders": [], "total_sampled": 0}

        # Batch-fetch metadata (From header + sizeEstimate) in chunks of 100
        message_data: Dict[str, Any] = {}

        def _callback(request_id, response, exception):
            if exception is None:
                message_data[request_id] = response

        for i in range(0, len(messages), 100):
            batch = self.service.new_batch_http_request()
            for msg in messages[i : i + 100]:
                batch.add(
                    self.service.users().messages().get(
                        userId="me",
                        id=msg["id"],
                        format="metadata",
                        metadataHeaders=["From", "Date"],
                    ),
                    request_id=msg["id"],
                    callback=_callback,
                )
            batch.execute()

        for msg_id, data in message_data.items():
            from_value = ""
            date_value = ""
            for header in data.get("payload", {}).get("headers", []):
                if header["name"] == "From":
                    from_value = header["value"]
                elif header["name"] == "Date":
                    date_value = header["value"]

            if from_value:
                stats = sender_stats[from_value]
                stats["count"] += 1
                stats["size_bytes"] += data.get("sizeEstimate", 0)
                if len(stats["ids"]) < 50:
                    stats["ids"].append(msg_id)
                if "oldest_date" not in stats or (date_value and date_value < stats["oldest_date"]):
                    stats["oldest_date"] = date_value
                if "newest_date" not in stats or (date_value and date_value > stats["newest_date"]):
                    stats["newest_date"] = date_value

        top = sorted(
            [
                {
                    "sender": sender,
                    "count": s["count"],
                    "size_mb": round(s["size_bytes"] / (1024 * 1024), 2),
                    "email_ids": s["ids"],
                    "oldest_date": s.get("oldest_date", ""),
                    "newest_date": s.get("newest_date", ""),
                }
                for sender, s in sender_stats.items()
            ],
            key=lambda x: x["count"],
            reverse=True,
        )[:limit]

        return {"senders": top, "total_sampled": len(messages)}

    # ------------------------------------------------------------------ #
    # Search                                                               #
    # ------------------------------------------------------------------ #

    def search_emails(self, query: str, limit: int = 50) -> Dict[str, Any]:
        """Search Gmail with Gmail search syntax."""
        try:
            result = self.service.users().messages().list(
                userId="me", q=query, maxResults=min(limit, 500)
            ).execute()
        except HttpError as e:
            return {"emails": [], "error": str(e)}

        messages = result.get("messages", [])
        if not messages:
            return {"emails": [], "total_found": 0}

        # Batch-fetch metadata
        meta: Dict[str, Any] = {}

        def _cb(request_id, response, exception):
            if exception is None:
                meta[request_id] = response

        for i in range(0, len(messages[:limit]), 100):
            batch = self.service.new_batch_http_request()
            for msg in messages[i : i + 100]:
                batch.add(
                    self.service.users().messages().get(
                        userId="me",
                        id=msg["id"],
                        format="metadata",
                        metadataHeaders=["From", "Subject", "Date", "List-Unsubscribe"],
                    ),
                    request_id=msg["id"],
                    callback=_cb,
                )
            batch.execute()

        email_list = []
        for msg_id, data in meta.items():
            headers = {
                h["name"]: h["value"]
                for h in data.get("payload", {}).get("headers", [])
            }
            unsubscribe_raw = headers.get("List-Unsubscribe", "")
            email_list.append(
                {
                    "id": msg_id,
                    "sender": headers.get("From", ""),
                    "subject": headers.get("Subject", "(no subject)"),
                    "date": headers.get("Date", ""),
                    "size_bytes": data.get("sizeEstimate", 0),
                    "has_unsubscribe": bool(unsubscribe_raw),
                    "unsubscribe_link": self._parse_unsubscribe_header(unsubscribe_raw),
                }
            )

        return {
            "emails": email_list,
            "total_found": result.get("resultSizeEstimate", len(messages)),
        }

    def get_messages_metadata(self, email_ids: List[str]) -> List[Dict[str, Any]]:
        """Batch-fetch metadata (subject/from/date/size) for a list of message IDs."""
        if not email_ids:
            return []

        meta: Dict[str, Any] = {}

        def _cb(request_id, response, exception):
            if exception is None:
                meta[request_id] = response

        for i in range(0, len(email_ids), 100):
            batch = self.service.new_batch_http_request()
            for mid in email_ids[i : i + 100]:
                batch.add(
                    self.service.users().messages().get(
                        userId="me",
                        id=mid,
                        format="metadata",
                        metadataHeaders=["From", "Subject", "Date"],
                    ),
                    request_id=mid,
                    callback=_cb,
                )
            batch.execute()

        out: List[Dict[str, Any]] = []
        for mid in email_ids:
            data = meta.get(mid)
            if not data:
                out.append({"id": mid, "subject": "(unavailable)", "sender": "", "date": "", "size_bytes": 0})
                continue
            headers = {
                h["name"]: h["value"]
                for h in data.get("payload", {}).get("headers", [])
            }
            out.append(
                {
                    "id": mid,
                    "sender": headers.get("From", ""),
                    "subject": headers.get("Subject", "(no subject)"),
                    "date": headers.get("Date", ""),
                    "size_bytes": data.get("sizeEstimate", 0),
                }
            )
        return out

    def get_emails_with_unsubscribe(self, limit: int = 50) -> Dict[str, Any]:
        """Find newsletter/mailing-list emails that have unsubscribe links."""
        return self.search_emails("category:promotions OR category:forums", limit)

    # ------------------------------------------------------------------ #
    # Actions                                                              #
    # ------------------------------------------------------------------ #

    def delete_emails(self, email_ids: List[str]) -> Dict[str, Any]:
        """Batch-delete emails by ID (moves to Trash)."""
        if not email_ids:
            return {"deleted": 0}

        deleted = 0
        errors = []
        # batchDelete supports up to 1000 IDs
        for i in range(0, len(email_ids), 1000):
            chunk = email_ids[i : i + 1000]
            try:
                self.service.users().messages().batchDelete(
                    userId="me", body={"ids": chunk}
                ).execute()
                deleted += len(chunk)
            except HttpError as e:
                errors.append(str(e))

        return {"deleted": deleted, "errors": errors}

    def create_block_filter(self, sender_email: str) -> Dict[str, Any]:
        """Create a Gmail filter that moves future emails from sender to Trash."""
        try:
            result = self.service.users().settings().filters().create(
                userId="me",
                body={
                    "criteria": {"from": sender_email},
                    "action": {
                        "addLabelIds": ["TRASH"],
                        "removeLabelIds": ["INBOX"],
                    },
                },
            ).execute()
            return {"success": True, "filter_id": result.get("id")}
        except HttpError as e:
            return {"success": False, "error": str(e)}

    def send_unsubscribe_email(self, mailto_link: str) -> bool:
        """Send an unsubscribe request via mailto: link."""
        import email.mime.text
        import urllib.parse

        parsed = urllib.parse.urlparse(mailto_link)
        to_address = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        subject = params.get("subject", ["Unsubscribe"])[0]
        body = params.get("body", ["Please unsubscribe me from this mailing list."])[0]

        msg = email.mime.text.MIMEText(body)
        msg["to"] = to_address
        msg["subject"] = subject

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        try:
            self.service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()
            return True
        except HttpError:
            return False

    # ------------------------------------------------------------------ #
    # Download                                                             #
    # ------------------------------------------------------------------ #

    def download_email_as_eml(self, email_id: str) -> bytes:
        """Return the raw RFC-2822 bytes of an email (.eml)."""
        msg = self.service.users().messages().get(
            userId="me", id=email_id, format="raw"
        ).execute()
        return base64.urlsafe_b64decode(msg["raw"])

    def get_email_subject(self, email_id: str) -> str:
        """Return the Subject header of an email."""
        try:
            data = self.service.users().messages().get(
                userId="me",
                id=email_id,
                format="metadata",
                metadataHeaders=["Subject"],
            ).execute()
            for h in data.get("payload", {}).get("headers", []):
                if h["name"] == "Subject":
                    return h["value"]
        except HttpError:
            pass
        return email_id

    def get_attachments(self, email_id: str) -> List[Dict[str, Any]]:
        """List attachments for an email."""
        try:
            msg = self.service.users().messages().get(
                userId="me", id=email_id, format="full"
            ).execute()
        except HttpError:
            return []

        attachments: List[Dict] = []

        def _walk(parts: List[Dict]) -> None:
            for part in parts:
                att_id = part.get("body", {}).get("attachmentId")
                filename = part.get("filename", "")
                if att_id and filename:
                    attachments.append(
                        {
                            "attachment_id": att_id,
                            "filename": filename,
                            "mime_type": part.get("mimeType", "application/octet-stream"),
                            "size_bytes": part.get("body", {}).get("size", 0),
                        }
                    )
                if "parts" in part:
                    _walk(part["parts"])

        payload = msg.get("payload", {})
        if "parts" in payload:
            _walk(payload["parts"])

        return attachments

    def download_attachment(self, email_id: str, attachment_id: str) -> bytes:
        """Return raw bytes of a specific attachment."""
        att = self.service.users().messages().attachments().get(
            userId="me", messageId=email_id, id=attachment_id
        ).execute()
        return base64.urlsafe_b64decode(att["data"])

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_unsubscribe_header(header_value: str) -> Optional[str]:
        if not header_value:
            return None
        links = re.findall(r"<([^>]+)>", header_value)
        # Prefer HTTP link
        for link in links:
            if link.startswith("http"):
                return link
        for link in links:
            if link.startswith("mailto:"):
                return link
        return None
