from sqlalchemy import Column, String, DateTime, Boolean, JSON, Float, ForeignKey, Integer, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.db.session import Base


class Project(Base):
    """项目模型"""
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    is_public = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    owner = relationship("User", backref="owned_projects")
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    files = relationship("MediaFile", back_populates="project", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": str(self.id),
            "owner_id": str(self.owner_id),
            "name": self.name,
            "description": self.description,
            "is_public": self.is_public,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ProjectMember(Base):
    """项目成员模型"""
    __tablename__ = "project_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="member")  # owner, admin, member, viewer
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # 关系
    project = relationship("Project", back_populates="members")
    user = relationship("User", backref="project_memberships")

    def to_dict(self):
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "user_id": str(self.user_id),
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MediaFile(Base):
    """媒体文件模型"""
    __tablename__ = "media_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)  # audio, video, ecg, pcg, other
    file_size = Column(BigInteger, nullable=False)  # 文件大小（字节）
    file_path = Column(String(500), nullable=False)  # 实际存储路径
    storage_backend = Column(String(20), nullable=False, server_default="local")  # "local" | "cos"

    # 音频/视频元数据
    duration = Column(Float)  # 秒
    sample_rate = Column(Float)  # Hz
    channels = Column(Integer)
    bit_depth = Column(Integer)
    width = Column(Integer)  # 视频宽度
    height = Column(Integer)  # 视频高度
    frame_rate = Column(Float)  # 视频帧率
    
    file_metadata = Column(JSON, default=dict)  # 其他元数据
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    project = relationship("Project", back_populates="files")
    annotations = relationship("Annotation", back_populates="file", cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisResult", back_populates="file", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "storage_backend": self.storage_backend,
            "duration": self.duration,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bit_depth": self.bit_depth,
            "width": self.width,
            "height": self.height,
            "frame_rate": self.frame_rate,
            "metadata": self.file_metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Annotation(Base):
    """标记模型"""
    __tablename__ = "annotations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("media_files.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    annotation_type = Column(String(20), nullable=False)  # s1, s2, qrs, p_wave, t_wave, murmur, other
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    label = Column(String(100), nullable=False)
    confidence = Column(Float)
    source = Column(String(20), nullable=False, default="manual")  # manual | auto
    annotation_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    file = relationship("MediaFile", back_populates="annotations")
    user = relationship("User", backref="annotations")

    def to_dict(self):
        return {
            "id": str(self.id),
            "file_id": str(self.file_id),
            "user_id": str(self.user_id),
            "annotation_type": self.annotation_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "label": self.label,
            "confidence": self.confidence,
            "source": self.source or "manual",
            "metadata": self.annotation_metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AnalysisResult(Base):
    """分析结果模型"""
    __tablename__ = "analysis_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("media_files.id"), nullable=False, index=True)
    analysis_type = Column(String(50), nullable=False)
    result_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # 关系
    file = relationship("MediaFile", back_populates="analysis_results")

    def to_dict(self):
        return {
            "id": str(self.id),
            "file_id": str(self.file_id),
            "analysis_type": self.analysis_type,
            "result_data": self.result_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CommunityPost(Base):
    """社区帖子模型"""
    __tablename__ = "community_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(String(5000), nullable=False)
    # 可选关联到一个文件（分享波形数据）
    file_id = Column(UUID(as_uuid=True), ForeignKey("media_files.id"), nullable=True, index=True)
    tags = Column(JSON, default=list)  # e.g. ["ECG", "异常"]
    like_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    author = relationship("User", backref="community_posts")
    file = relationship("MediaFile", foreign_keys=[file_id])
    comments = relationship("PostComment", back_populates="post", cascade="all, delete-orphan")


class PostComment(Base):
    """帖子评论模型"""
    __tablename__ = "post_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    post_id = Column(UUID(as_uuid=True), ForeignKey("community_posts.id"), nullable=False, index=True)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    content = Column(String(2000), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # 关系
    post = relationship("CommunityPost", back_populates="comments")
    author = relationship("User", backref="post_comments")


class FileAssociation(Base):
    """文件关联模型 — 在同一项目内关联 ECG / PCG / Video 文件，支持时间偏移微调"""
    __tablename__ = "file_associations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(200), nullable=False, default="")

    # 三个可选槽：ecg / pcg / video（均可为 None）
    ecg_file_id = Column(UUID(as_uuid=True), ForeignKey("media_files.id"), nullable=True)
    pcg_file_id = Column(UUID(as_uuid=True), ForeignKey("media_files.id"), nullable=True)
    video_file_id = Column(UUID(as_uuid=True), ForeignKey("media_files.id"), nullable=True)

    # 相对时间偏移（秒），以 ECG 为基准 0，其他两个可正可负
    pcg_offset = Column(Float, nullable=False, default=0.0)    # PCG 相对于 ECG 的时间偏移
    video_offset = Column(Float, nullable=False, default=0.0)  # Video 相对于 ECG 的时间偏移

    # 额外元数据
    notes = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    project = relationship("Project", backref="file_associations")
    creator = relationship("User", backref="file_associations")
    ecg_file = relationship("MediaFile", foreign_keys=[ecg_file_id], lazy="noload")
    pcg_file = relationship("MediaFile", foreign_keys=[pcg_file_id], lazy="noload")
    video_file = relationship("MediaFile", foreign_keys=[video_file_id], lazy="noload")

    def to_dict(self):
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "created_by": str(self.created_by),
            "name": self.name,
            "ecg_file_id": str(self.ecg_file_id) if self.ecg_file_id else None,
            "pcg_file_id": str(self.pcg_file_id) if self.pcg_file_id else None,
            "video_file_id": str(self.video_file_id) if self.video_file_id else None,
            "pcg_offset": self.pcg_offset,
            "video_offset": self.video_offset,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }