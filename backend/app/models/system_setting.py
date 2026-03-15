"""系统设置模型 — key-value 存储，用于运行时配置（如存储后端参数）"""
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func

from app.db.session import Base


class SystemSetting(Base):
    """系统设置 key-value 表"""
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
