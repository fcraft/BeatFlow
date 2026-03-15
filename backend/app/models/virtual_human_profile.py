"""虚拟人体档案模型 — 多实例持久化"""
import uuid
from sqlalchemy import Boolean, Column, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.session import Base


class VirtualHumanProfile(Base):
    """虚拟人体档案：每个用户可创建多个虚拟人。"""
    __tablename__ = "virtual_human_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    state_snapshot = Column(JSONB, nullable=True)   # PhysioState.to_snapshot()
    settings = Column(JSONB, default=dict)           # 引擎配置预留
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<VirtualHumanProfile(id={self.id}, name={self.name})>"
