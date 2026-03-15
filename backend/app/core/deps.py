"""依赖注入模块"""
from typing import Annotated, AsyncGenerator, Optional
from enum import Enum

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.models.project import Project, ProjectMember
from app.crud.user import user_crud
from app.utils.security import decode_token

# HTTP Bearer认证方案
security = HTTPBearer(auto_error=False)


class ProjectAccess:
    """项目访问权限级别"""
    OWNER = 4      # 项目所有者
    ADMIN = 3      # 项目管理员
    MEMBER = 2     # 项目成员
    VIEWER = 1     # 项目查看者
    NONE = 0       # 无权限


def get_role_level(role: Optional[str]) -> int:
    """获取角色权限级别"""
    if not role:
        return ProjectAccess.NONE
    role_levels = {
        "owner": ProjectAccess.OWNER,
        "admin": ProjectAccess.ADMIN,
        "member": ProjectAccess.MEMBER,
        "viewer": ProjectAccess.VIEWER,
    }
    return role_levels.get(role, ProjectAccess.NONE)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[User]:
    """获取当前认证用户"""
    if not credentials:
        return None
    
    token = credentials.credentials
    
    # 解码JWT令牌
    payload = decode_token(token)
    if not payload:
        return None
    
    # 获取用户ID
    user_id: str = payload.get("sub")
    if not user_id:
        return None
    
    # 获取用户
    user = await user_crud.get_by_uuid(db, user_id)
    if not user or not user.is_active:
        return None
    
    return user


async def get_current_active_user(
    current_user: Annotated[Optional[User], Depends(get_current_user)],
) -> User:
    """获取当前活跃用户（要求认证）"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证",
        )
    return current_user


async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """获取当前管理员用户"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足",
        )
    return current_user


async def get_api_key_user(
    db: AsyncSession = Depends(get_db),
    api_key: Optional[str] = None,
) -> Optional[User]:
    """通过API Key获取用户"""
    if not api_key:
        return None
    
    from app.utils.security import validate_api_key
    
    api_key_info = validate_api_key(api_key)
    if not api_key_info:
        return None
    
    user = await user_crud.get(db, id=api_key_info["user_id"])
    if not user or not user.is_active:
        return None
    
    return user


async def get_project_member(
    db: AsyncSession,
    user: User,
    project_id: str,
) -> tuple[ProjectMember, int]:
    """
    获取用户在项目中的成员信息和权限级别
    
    Args:
        db: 数据库会话
        user: 当前用户
        project_id: 项目 ID
    
    Returns:
        (ProjectMember, permission_level) 元组
        
    Raises:
        HTTPException: 用户不是项目成员 (403)
    """
    # 如果是系统管理员，自动返回 OWNER 级权限
    if user.role == "admin":
        # 返回一个虚拟的管理员会员对象
        virtual_member = ProjectMember(
            id=None,
            project_id=project_id,
            user_id=user.id,
            role="owner",
            created_at=None,
        )
        return virtual_member, ProjectAccess.OWNER

    # 查询项目成员记录
    result = await db.execute(
        select(ProjectMember).where(
            (ProjectMember.project_id == project_id)
            & (ProjectMember.user_id == user.id)
        )
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="你不是该项目的成员",
        )

    level = get_role_level(member.role)
    return member, level


async def require_project_role(
    db: AsyncSession,
    user: User,
    project_id: str,
    min_role: str,  # "viewer", "member", "admin", "owner"
) -> tuple[ProjectMember, int]:
    """
    验证用户是否具有项目中的最小权限级别
    
    Args:
        db: 数据库会话
        user: 当前用户
        project_id: 项目 ID
        min_role: 最小要求的角色级别
        
    Returns:
        (ProjectMember, permission_level) 元组
        
    Raises:
        HTTPException: 权限不足
    """
    member, level = await get_project_member(db, user, project_id)
    min_level = get_role_level(min_role)

    if level < min_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"权限不足。需要 {min_role} 权限，但你只有 {member.role} 权限",
        )

    return member, level


# 类型别名
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[Optional[User], Depends(get_current_user)]
CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]
CurrentAdminUser = Annotated[User, Depends(get_current_admin_user)]
OptionalApiKeyUser = Annotated[Optional[User], Depends(get_api_key_user)]