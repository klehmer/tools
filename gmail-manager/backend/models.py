from pydantic import BaseModel
from typing import List, Optional, Literal


class EmailGroup(BaseModel):
    sender: str
    sender_name: str
    count: int
    total_size_mb: float
    oldest_date: str
    newest_date: str
    email_ids: List[str]
    category: Literal["delete", "unsubscribe", "block"]
    suggestion_reason: str
    unsubscribe_link: Optional[str] = None


class AnalysisResult(BaseModel):
    analysis_summary: str
    email_groups: List[EmailGroup]
    total_emails_to_process: int
    estimated_storage_freed_mb: float


class UserProfile(BaseModel):
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    total_messages: int = 0
    storage_used_bytes: Optional[int] = None
    storage_limit_bytes: Optional[int] = None


class DeleteRequest(BaseModel):
    email_ids: List[str]


class UnsubscribeRequest(BaseModel):
    email_id: str
    sender_email: str
    unsubscribe_link: Optional[str] = None


class BlockRequest(BaseModel):
    sender_email: str


class DownloadRequest(BaseModel):
    email_ids: List[str]
    include_attachments: bool = True
    filename: Optional[str] = None
