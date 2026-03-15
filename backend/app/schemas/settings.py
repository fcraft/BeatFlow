"""系统设置相关 Schema"""
from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime


class SettingItem(BaseModel):
    key: str
    value: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SettingsResponse(BaseModel):
    items: list[SettingItem]


class SettingsBulkUpdate(BaseModel):
    """批量更新系统设置"""
    settings: Dict[str, Optional[str]]


class StorageTestResult(BaseModel):
    success: bool
    message: str
