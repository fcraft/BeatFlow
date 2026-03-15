"""虚拟人体档案 Pydantic schemas"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    """创建虚拟人档案请求。"""
    name: str = Field(..., min_length=1, max_length=100)
    settings: Dict[str, Any] = Field(default_factory=dict)


class ProfileUpdate(BaseModel):
    """更新虚拟人档案请求。"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    settings: Optional[Dict[str, Any]] = None


class ProfileResponse(BaseModel):
    """虚拟人档案响应。"""
    id: UUID
    user_id: UUID
    name: str
    state_snapshot: Optional[Dict[str, Any]] = None
    settings: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileListItem(BaseModel):
    """列表项（不含完整 snapshot）。"""
    id: UUID
    name: str
    is_active: bool
    # 从 snapshot 提取的摘要信息
    heart_rate: Optional[float] = None
    rhythm: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
