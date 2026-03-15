"""标记相关模型"""
from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, Float, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.base import Base, UUIDBase


class AnnotationType(str, Enum):
    """标记类型枚举"""
    S1 = "s1"              # 心音 S1
    S2 = "s2"              # 心音 S2
    QRS = "qrs"           # 心电图 QRS波
    EXTRA_SYSTOLE = "extra_systole"  # 期外收缩
    MURMUR = "murmur"     # 杂音
    ARTIFACT = "artifact" # 伪影
    OTHER = "other"       # 其他


class AnnotationSource(str, Enum):
    """标记来源枚举"""
    MANUAL = "manual"     # 手动标记
    AUTO = "auto"         # 自动算法标记


class Annotation(UUIDBase):
    """标记数据模型"""
    
    __tablename__ = "annotations"
    
    # 标记信息
    annotation_type: Mapped[AnnotationType] = mapped_column(
        nullable=False,
    )
    start_time: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )  # 秒
    end_time: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )  # 秒
    confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )  # 置信度 0-1
    
    # 标记元数据
    label: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    attributes: Mapped[Optional[dict]] = mapped_column(
        type_=String(1000),
        nullable=True,
    )  # JSON字符串存储额外属性
    
    # 来源信息
    source: Mapped[AnnotationSource] = mapped_column(
        default=AnnotationSource.MANUAL,
        nullable=False,
    )
    algorithm_version: Mapped[Optional[str]] = mapped_column(String(50))
    
    # 时间信息
    annotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # 外键关系
    file_id: Mapped[int] = mapped_column(
        ForeignKey("media_files.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # 关系
    file = relationship("MediaFile", back_populates="annotations")
    user = relationship("User", back_populates="annotations")
    
    def __repr__(self) -> str:
        return f"<Annotation(id={self.id}, type='{self.annotation_type}', start={self.start_time})>"