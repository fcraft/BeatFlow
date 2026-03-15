"""临时共享模型定义"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer, Index, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
import hashlib

from app.db.session import Base


class FileShare(Base):
    """文件临时共享"""
    __tablename__ = "file_shares"
    __table_args__ = (
        Index('ix_file_shares_share_code_hash', 'share_code_hash'),
        Index('ix_file_shares_file_id', 'file_id'),
        Index('ix_file_shares_expires_at', 'expires_at'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("media_files.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 分享码: URL-safe 唯一标识符 (16-20 字符)
    share_code = Column(String(20), nullable=False, unique=True, index=True)
    # 分享码哈希 (用于安全存储)
    share_code_hash = Column(String(64), nullable=False, unique=True)
    
    # 有效期: NULL = 永不过期
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # 可选分享码保护 (默认需要分享码)
    is_code_required = Column(Boolean, default=True, nullable=False)
    
    # 下载限制: NULL = 无限制
    max_downloads = Column(Integer, nullable=True)
    download_count = Column(Integer, default=0, nullable=False)
    
    # 时间戳和统计
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    view_count = Column(Integer, default=0, nullable=False)  # 查看次数
    
    # 关系
    file = relationship("MediaFile", backref="shares")
    creator = relationship("User", backref="file_shares")

    def to_dict(self):
        return {
            "id": str(self.id),
            "file_id": str(self.file_id),
            "created_by": str(self.created_by),
            "share_code": self.share_code,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_code_required": self.is_code_required,
            "max_downloads": self.max_downloads,
            "download_count": self.download_count,
            "created_at": self.created_at.isoformat(),
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            "view_count": self.view_count,
        }


class FileAssociationShare(Base):
    """关联文件临时共享 (同时共享 ECG/PCG/Video)"""
    __tablename__ = "file_association_shares"
    __table_args__ = (
        Index('ix_file_association_shares_code_hash', 'share_code_hash'),
        Index('ix_file_association_shares_association_id', 'association_id'),
        Index('ix_file_association_shares_expires_at', 'expires_at'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    association_id = Column(UUID(as_uuid=True), ForeignKey("file_associations.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    share_code = Column(String(20), nullable=False, unique=True, index=True)
    share_code_hash = Column(String(64), nullable=False, unique=True)
    
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_code_required = Column(Boolean, default=True, nullable=False)
    
    max_downloads = Column(Integer, nullable=True)
    download_count = Column(Integer, default=0, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    view_count = Column(Integer, default=0, nullable=False)
    
    # 关系
    association = relationship("FileAssociation", backref="shares")
    creator = relationship("User", backref="association_shares")

    def to_dict(self):
        return {
            "id": str(self.id),
            "association_id": str(self.association_id),
            "created_by": str(self.created_by),
            "share_code": self.share_code,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_code_required": self.is_code_required,
            "max_downloads": self.max_downloads,
            "download_count": self.download_count,
            "created_at": self.created_at.isoformat(),
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            "view_count": self.view_count,
        }


def hash_share_code(code: str) -> str:
    """对分享码进行 SHA256 哈希"""
    return hashlib.sha256(code.encode()).hexdigest()
