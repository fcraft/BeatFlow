"""管理后台端点"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func

from app.core.deps import CurrentActiveUser, DatabaseSession
from app.models.notification import Notification
from app.models.project import Project, MediaFile, CommunityPost, PostComment
from app.models.user import User
from app.schemas.admin import (
    SystemStats,
    AdminUserResponse,
    AdminUserListResponse,
    AdminFileResponse,
    AdminFileListResponse,
    AdminPostResponse,
    AdminPostListResponse,
    RoleUpdate,
    AnnouncementCreate,
)
from app.schemas.settings import (
    SettingItem,
    SettingsResponse,
    SettingsBulkUpdate,
    StorageTestResult,
)

router = APIRouter()


def _require_admin(current_user: User) -> None:
    if not (current_user.is_superuser or current_user.role == "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")


class BatchDeleteRequest(BaseModel):
    file_ids: List[str]


@router.get("/stats", response_model=SystemStats)
async def get_stats(
    db: DatabaseSession,
    current_user: CurrentActiveUser,
) -> SystemStats:
    """获取系统统计"""
    _require_admin(current_user)

    user_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    project_count = (await db.execute(select(func.count()).select_from(Project))).scalar_one()
    file_count = (await db.execute(select(func.count()).select_from(MediaFile))).scalar_one()
    post_count = (await db.execute(select(func.count()).select_from(CommunityPost))).scalar_one()

    storage_result = await db.execute(select(func.coalesce(func.sum(MediaFile.file_size), 0)))
    total_storage = storage_result.scalar_one()

    return SystemStats(
        user_count=user_count,
        project_count=project_count,
        file_count=file_count,
        post_count=post_count,
        total_storage_bytes=int(total_storage),
    )


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    db: DatabaseSession,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None),
) -> AdminUserListResponse:
    """获取用户列表"""
    _require_admin(current_user)

    skip = (page - 1) * size
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)

    if q:
        like = f"%{q}%"
        from sqlalchemy import or_
        filter_cond = or_(User.username.ilike(like), User.email.ilike(like), User.full_name.ilike(like))
        stmt = stmt.where(filter_cond)
        count_stmt = count_stmt.where(filter_cond)

    total = (await db.execute(count_stmt)).scalar_one()
    result = await db.execute(stmt.order_by(User.created_at.desc()).offset(skip).limit(size))
    users = list(result.scalars().all())

    return AdminUserListResponse(
        items=[AdminUserResponse(
            id=str(u.id),
            username=u.username,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            is_superuser=u.is_superuser,
            created_at=u.created_at,
        ) for u in users],
        total=total,
        page=page,
        size=size,
        has_next=(skip + size) < total,
    )


@router.patch("/users/{user_id}/toggle-active")
async def toggle_user_active(
    db: DatabaseSession,
    user_id: str,
    current_user: CurrentActiveUser,
) -> dict:
    """激活/封禁用户"""
    _require_admin(current_user)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if str(user.id) == str(current_user.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能修改自身账号状态")

    user.is_active = not user.is_active
    await db.commit()
    return {"success": True, "is_active": user.is_active}


@router.patch("/users/{user_id}/role")
async def update_user_role(
    db: DatabaseSession,
    user_id: str,
    role_data: RoleUpdate,
    current_user: CurrentActiveUser,
) -> dict:
    """修改用户角色"""
    _require_admin(current_user)

    if role_data.role not in ("admin", "member"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="角色只能为 admin 或 member")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    user.role = role_data.role
    await db.commit()
    return {"success": True, "role": user.role}


@router.get("/files", response_model=AdminFileListResponse)
async def list_all_files(
    db: DatabaseSession,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None),
) -> AdminFileListResponse:
    """获取全局文件列表"""
    _require_admin(current_user)

    skip = (page - 1) * size
    stmt = select(MediaFile)
    count_stmt = select(func.count()).select_from(MediaFile)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(MediaFile.original_filename.ilike(like))
        count_stmt = count_stmt.where(MediaFile.original_filename.ilike(like))

    total = (await db.execute(count_stmt)).scalar_one()
    result = await db.execute(stmt.order_by(MediaFile.created_at.desc()).offset(skip).limit(size))
    files = list(result.scalars().all())

    # 获取项目名
    items = []
    for f in files:
        proj_result = await db.execute(select(Project).where(Project.id == f.project_id))
        proj = proj_result.scalar_one_or_none()
        items.append(AdminFileResponse(
            id=str(f.id),
            filename=f.filename,
            original_filename=f.original_filename,
            file_type=f.file_type,
            file_size=f.file_size,
            project_id=str(f.project_id),
            project_name=proj.name if proj else None,
            created_at=f.created_at,
        ))

    return AdminFileListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        has_next=(skip + size) < total,
    )


@router.delete("/files/batch", status_code=status.HTTP_200_OK)
async def batch_delete_files(
    db: DatabaseSession,
    body: BatchDeleteRequest,
    current_user: CurrentActiveUser,
) -> dict:
    """批量删除文件"""
    _require_admin(current_user)

    from app.api.v1.endpoints.files import _cleanup_file_references
    from app.services.storage_manager import get_storage_for_file

    deleted = 0
    failed = []

    for file_id in body.file_ids:
        try:
            result = await db.execute(select(MediaFile).where(MediaFile.id == file_id))
            file = result.scalar_one_or_none()
            if not file:
                failed.append({"id": file_id, "reason": "文件不存在"})
                continue

            # 删除存储文件（按文件记录的后端）
            if file.file_path:
                try:
                    storage = await get_storage_for_file(db, file)
                    await storage.delete(file.file_path)
                except Exception as e:
                    failed.append({"id": file_id, "reason": f"删除存储文件失败: {e}"})
                    continue

            # 清理外键引用
            await _cleanup_file_references(db, file.id)

            await db.delete(file)
            deleted += 1
        except Exception as e:
            failed.append({"id": file_id, "reason": str(e)})

    await db.commit()
    return {"deleted": deleted, "failed": failed}


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def force_delete_file(
    db: DatabaseSession,
    file_id: str,
    current_user: CurrentActiveUser,
) -> None:
    """强制删除文件"""
    _require_admin(current_user)

    result = await db.execute(select(MediaFile).where(MediaFile.id == file_id))
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    # 删除存储文件
    from app.services.storage_manager import get_storage_for_file
    storage = await get_storage_for_file(db, file)
    if file.file_path:
        try:
            await storage.delete(file.file_path)
        except Exception:
            pass

    # 清理外键引用，防止约束冲突
    from app.api.v1.endpoints.files import _cleanup_file_references
    await _cleanup_file_references(db, file.id)

    await db.delete(file)
    await db.commit()


@router.get("/community/posts", response_model=AdminPostListResponse)
async def list_all_posts(
    db: DatabaseSession,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> AdminPostListResponse:
    """获取全局帖子列表"""
    _require_admin(current_user)

    skip = (page - 1) * size
    total = (await db.execute(select(func.count()).select_from(CommunityPost))).scalar_one()
    result = await db.execute(
        select(CommunityPost).order_by(CommunityPost.created_at.desc()).offset(skip).limit(size)
    )
    posts = list(result.scalars().all())

    items = []
    for p in posts:
        # 获取作者
        author_result = await db.execute(select(User).where(User.id == p.author_id))
        author = author_result.scalar_one_or_none()
        # 评论数
        comment_count = (await db.execute(
            select(func.count()).select_from(PostComment).where(PostComment.post_id == p.id)
        )).scalar_one()
        items.append(AdminPostResponse(
            id=str(p.id),
            title=p.title,
            author_username=author.username if author else "未知",
            likes_count=p.like_count or 0,
            comments_count=comment_count,
            created_at=p.created_at,
        ))

    return AdminPostListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        has_next=(skip + size) < total,
    )


@router.delete("/community/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    db: DatabaseSession,
    post_id: str,
    current_user: CurrentActiveUser,
) -> None:
    """删除帖子"""
    _require_admin(current_user)

    result = await db.execute(select(CommunityPost).where(CommunityPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")

    await db.delete(post)
    await db.commit()


@router.post("/announcements", status_code=status.HTTP_201_CREATED)
async def send_announcement(
    db: DatabaseSession,
    announcement: AnnouncementCreate,
    current_user: CurrentActiveUser,
) -> dict:
    """发送系统公告（写入所有用户通知）"""
    _require_admin(current_user)

    result = await db.execute(select(User).where(User.is_active == True))
    users = list(result.scalars().all())

    for user in users:
        notif = Notification(
            recipient_id=user.id,
            sender_id=current_user.id,
            notification_type="system_announcement",
            title=announcement.title,
            content=announcement.content,
            status="done",
            data={},
        )
        db.add(notif)

    await db.commit()
    return {"success": True, "sent_to": len(users)}


# ═══════════════════════════════════════════════════════════════════════════
# 系统设置
# ═══════════════════════════════════════════════════════════════════════════

# 允许前端读写的系统设置键（白名单，防止意外写入）
_ALLOWED_SETTING_KEYS = {
    "storage_type",
    "cos_secret_id",
    "cos_secret_key",
    "cos_bucket_name",
    "cos_region",
    "cos_endpoint",
}


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    db: DatabaseSession,
    current_user: CurrentActiveUser,
) -> SettingsResponse:
    """获取所有系统设置（admin only）"""
    _require_admin(current_user)

    from app.models.system_setting import SystemSetting

    result = await db.execute(select(SystemSetting))
    rows = result.scalars().all()

    items = [
        SettingItem(key=row.key, value=row.value, updated_at=row.updated_at)
        for row in rows
    ]
    # 确保所有允许的 key 都返回（即使数据库里还没有）
    existing_keys = {item.key for item in items}
    for key in _ALLOWED_SETTING_KEYS:
        if key not in existing_keys:
            items.append(SettingItem(key=key, value=None, updated_at=None))

    return SettingsResponse(items=items)


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    db: DatabaseSession,
    body: SettingsBulkUpdate,
    current_user: CurrentActiveUser,
) -> SettingsResponse:
    """批量更新系统设置（admin only）"""
    _require_admin(current_user)

    from app.models.system_setting import SystemSetting
    from app.services.storage_manager import invalidate_storage_cache

    for key, value in body.settings.items():
        if key not in _ALLOWED_SETTING_KEYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不允许设置的键: {key}",
            )
        # Upsert
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
        else:
            db.add(SystemSetting(key=key, value=value))

    await db.commit()

    # 清除存储后端缓存，下次请求使用新配置
    invalidate_storage_cache()

    # 返回更新后的完整设置
    return await get_settings(db, current_user)


@router.post("/settings/test-storage", response_model=StorageTestResult)
async def test_storage_connection(
    db: DatabaseSession,
    current_user: CurrentActiveUser,
) -> StorageTestResult:
    """测试当前存储配置是否可用（上传+下载+删除测试文件）"""
    _require_admin(current_user)

    from app.services.storage_manager import get_storage_backend

    try:
        backend = await get_storage_backend(db)
        test_key = "__beatflow_test_connection__"
        test_data = b"BeatFlow storage connection test"

        # 上传
        await backend.put(test_key, test_data)
        # 检查存在
        exists = await backend.exists(test_key)
        if not exists:
            return StorageTestResult(success=False, message="文件上传后无法找到")
        # 下载验证
        downloaded = await backend.get(test_key)
        if downloaded != test_data:
            return StorageTestResult(success=False, message="下载内容与上传不一致")
        # 清理
        await backend.delete(test_key)

        backend_name = type(backend).__name__
        return StorageTestResult(success=True, message=f"连接成功 ({backend_name})")

    except Exception as e:
        return StorageTestResult(success=False, message=f"连接失败: {str(e)}")
