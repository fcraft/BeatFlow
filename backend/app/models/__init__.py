# 统一导入所有模型，确保 SQLAlchemy mapper 能解析跨模型关系
from app.models.user import User  # noqa: F401
from app.models.project import Project, ProjectMember, MediaFile, Annotation, AnalysisResult, CommunityPost, PostComment, FileAssociation  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.system_setting import SystemSetting  # noqa: F401
from app.models.virtual_human_profile import VirtualHumanProfile  # noqa: F401
from app.models.shares import FileShare, FileAssociationShare  # noqa: F401
