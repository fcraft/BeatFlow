"""通知相关 Schema"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class SenderInfo(BaseModel):
    id: str
    username: str

    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    id: str
    notification_type: str
    title: str
    content: str
    is_read: bool
    status: str
    data: Dict[str, Any]
    sender: Optional[SenderInfo] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    page: int
    size: int
    has_next: bool
    unread_count: int


class SystemAnnouncementCreate(BaseModel):
    title: str
    content: str
