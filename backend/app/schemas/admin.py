"""管理后台相关 Schema"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class SystemStats(BaseModel):
    user_count: int
    project_count: int
    file_count: int
    post_count: int
    total_storage_bytes: int


class AdminUserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AdminUserListResponse(BaseModel):
    items: List[AdminUserResponse]
    total: int
    page: int
    size: int
    has_next: bool


class AdminFileResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    project_id: str
    project_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AdminFileListResponse(BaseModel):
    items: List[AdminFileResponse]
    total: int
    page: int
    size: int
    has_next: bool


class AdminPostResponse(BaseModel):
    id: str
    title: str
    author_username: str
    likes_count: int
    comments_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class AdminPostListResponse(BaseModel):
    items: List[AdminPostResponse]
    total: int
    page: int
    size: int
    has_next: bool


class RoleUpdate(BaseModel):
    role: str


class AnnouncementCreate(BaseModel):
    title: str
    content: str
