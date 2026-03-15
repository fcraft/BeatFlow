from pydantic import BaseModel, Field, validator, model_serializer
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid as _uuid


class UUIDMixin(BaseModel):
    """自动将 UUID 字段序列化为字符串的 Mixin"""

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, dict):
            return super().model_validate(obj, **kwargs)
        # 将 ORM 对象转成 dict，UUID → str
        data = {}
        for field_name in cls.model_fields:
            val = getattr(obj, field_name, None)
            if isinstance(val, _uuid.UUID):
                val = str(val)
            data[field_name] = val
        return cls(**data)


class FileType(str, Enum):
    """文件类型枚举"""
    AUDIO = "audio"
    VIDEO = "video"
    ECG = "ecg"
    PCG = "pcg"
    OTHER = "other"


class AnnotationType(str, Enum):
    """标记类型枚举"""
    S1 = "s1"
    S2 = "s2"
    QRS = "qrs"
    P_WAVE = "p_wave"
    T_WAVE = "t_wave"
    Q_WAVE = "q_wave"
    S_WAVE = "s_wave"
    MURMUR = "murmur"
    RON_T = "ron_t"
    VT = "vt"
    VF = "vf"
    OTHER = "other"


class MemberRole(str, Enum):
    """成员角色枚举"""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class WorkflowStatus(str, Enum):
    """工作流状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# 项目相关模式
class ProjectBase(BaseModel):
    """项目基础模式"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public: bool = Field(default=False)


class ProjectCreate(ProjectBase):
    """项目创建模式"""
    pass


class ProjectUpdate(BaseModel):
    """项目更新模式"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None


class ProjectResponse(UUIDMixin, ProjectBase):
    """项目响应模式"""
    id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime


# 项目成员相关模式
class ProjectMemberBase(BaseModel):
    """项目成员基础模式"""
    role: MemberRole = Field(default="member")


class ProjectMemberCreate(ProjectMemberBase):
    """项目成员创建模式"""
    user_id: Optional[str] = None
    email: Optional[str] = None


class ProjectMemberResponse(UUIDMixin, ProjectMemberBase):
    """项目成员响应模式"""
    id: str
    project_id: str
    user_id: str
    created_at: datetime
    user: Dict[str, Any]  # 用户基本信息


# 媒体文件相关模式
class MediaFileBase(BaseModel):
    """媒体文件基础模式"""
    file_type: FileType


class MediaFileCreate(BaseModel):
    """媒体文件创建模式"""
    original_filename: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MediaFileResponse(UUIDMixin, MediaFileBase):
    """媒体文件响应模式"""
    id: str
    project_id: str
    filename: str
    original_filename: str
    file_size: int
    duration: Optional[float] = None
    sample_rate: Optional[float] = None
    channels: Optional[int] = None
    bit_depth: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    frame_rate: Optional[float] = None
    created_at: datetime
    updated_at: datetime


# 标记相关模式
class AnnotationBase(BaseModel):
    """标记基础模式"""
    annotation_type: AnnotationType
    start_time: float = Field(..., ge=0)
    end_time: float = Field(..., ge=0)
    label: str = Field(..., min_length=1, max_length=100)
    confidence: Optional[float] = Field(None, ge=0, le=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnnotationCreate(AnnotationBase):
    """标记创建模式"""
    file_id: str


class AnnotationUpdate(BaseModel):
    """标记更新模式"""
    start_time: Optional[float] = Field(None, ge=0)
    end_time: Optional[float] = Field(None, ge=0)
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    confidence: Optional[float] = Field(None, ge=0, le=1)
    metadata: Optional[Dict[str, Any]] = None


class AnnotationResponse(BaseModel):
    """标记响应模式"""
    id: str
    file_id: str
    user_id: str
    annotation_type: AnnotationType
    start_time: float
    end_time: float
    label: str
    confidence: Optional[float] = None
    source: str = "manual"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if hasattr(obj, 'annotation_metadata') and not isinstance(obj, dict):
            data = {
                'id': str(obj.id),
                'file_id': str(obj.file_id),
                'user_id': str(obj.user_id),
                'annotation_type': obj.annotation_type,
                'start_time': obj.start_time,
                'end_time': obj.end_time,
                'label': obj.label,
                'confidence': obj.confidence,
                'source': obj.source or 'manual',
                'metadata': obj.annotation_metadata or {},
                'created_at': obj.created_at,
                'updated_at': obj.updated_at,
            }
            return cls(**data)
        return super().model_validate(obj, **kwargs)


# 分析结果相关模式
class AnalysisResultBase(BaseModel):
    """分析结果基础模式"""
    analysis_type: str = Field(..., min_length=1, max_length=50)
    result_data: Dict[str, Any]


class AnalysisResultCreate(AnalysisResultBase):
    """分析结果创建模式"""
    file_id: str


class AnalysisResultResponse(AnalysisResultBase):
    """分析结果响应模式"""
    id: str
    file_id: str
    created_at: datetime

    class Config:
        from_attributes = True


# 工作流相关模式
class WorkflowStep(BaseModel):
    """工作流步骤模式"""
    name: str
    type: str
    config: Dict[str, Any]
    order: int
    dependencies: Optional[List[str]] = None


class WorkflowBase(BaseModel):
    """工作流基础模式"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    steps: List[WorkflowStep]


class WorkflowCreate(WorkflowBase):
    """工作流创建模式"""
    project_id: str


class WorkflowUpdate(BaseModel):
    """工作流更新模式"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[WorkflowStatus] = None
    steps: Optional[List[WorkflowStep]] = None


class WorkflowResponse(WorkflowBase):
    """工作流响应模式"""
    id: str
    project_id: str
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 列表响应模式
class ProjectListResponse(BaseModel):
    """项目列表响应模式"""
    items: List[ProjectResponse]
    total: int
    page: int
    size: int
    has_next: bool


class MediaFileListResponse(BaseModel):
    """媒体文件列表响应模式"""
    items: List[MediaFileResponse]
    total: int
    page: int
    size: int
    has_next: bool


class AnnotationListResponse(BaseModel):
    """标记列表响应模式"""
    items: List[AnnotationResponse]
    total: int
    page: int
    size: int
    has_next: bool