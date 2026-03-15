"""通知模型"""
import uuid
from sqlalchemy import Boolean, Column, String, DateTime, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.session import Base


class Notification(Base):
    """通知模型"""
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notification_type = Column(String(50), nullable=False, index=True)
    # project_invite | system_announcement | community_interaction | analysis_complete
    title = Column(String(200), nullable=False)
    content = Column(String(1000), nullable=False, default="")
    is_read = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="pending")
    # pending | accepted | rejected | done
    data = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<Notification(id={self.id}, type={self.notification_type}, recipient={self.recipient_id})>"
