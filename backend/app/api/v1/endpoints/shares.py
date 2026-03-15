"""文件和关联共享相关的 API 端点"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import DatabaseSession, CurrentActiveUser, CurrentUser, require_project_role
from app.models.shares import FileShare, FileAssociationShare, hash_share_code
from app.models.project import MediaFile, FileAssociation
from app.utils.security import generate_share_code
from app.services.storage import LocalStorageBackend
from app.services.storage_manager import get_storage_for_file
from app.utils.http_range import build_bytes_stream_response, build_file_stream_response

router = APIRouter(tags=["sharing"])


# ============================================================================
# 文件分享 API
# ============================================================================

@router.post(
    "/files/{file_id}/share",
    responses={404: {}, 403: {}, 400: {}},
)
async def create_file_share(
    db: DatabaseSession,
    file_id: str,
    current_user: CurrentActiveUser,
    expires_in_hours: Optional[int] = Query(None, description="分享有效期 (小时)"),
    expires_in_days: Optional[int] = Query(None, description="分享有效期 (天)"),
    expires_at_custom: Optional[str] = Query(None, description="自定义过期时间 (ISO 8601, 如 2026-04-01T00:00:00Z)"),
    share_code: Optional[str] = Query(None, description="自定义分享码 (可选, 6-20 字符)"),
    is_code_required: bool = Query(True, description="是否需要分享码访问"),
    max_downloads: Optional[int] = Query(None, description="最大下载次数 (可选)"),
):
    """创建文件临时分享

    有效期选项:
    - expires_in_hours: 以小时为单位 (如 1, 24)
    - expires_in_days: 以天为单位 (如 7, 30)
    - expires_at_custom: ISO 8601 时间 (优先级最高)
    - 全部留空 = 永不过期
    """
    # 获取文件
    result = await db.execute(select(MediaFile).where(MediaFile.id == file_id))
    media_file = result.scalar_one_or_none()
    if not media_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    # 验证权限: 需要 member 或以上
    await require_project_role(db, current_user, str(media_file.project_id), "member")

    # 计算过期时间 (优先级: custom > hours > days)
    expires_at = None
    if expires_at_custom:
        try:
            expires_at = datetime.fromisoformat(expires_at_custom.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="自定义过期时间格式无效，请使用 ISO 8601 格式 (如 2026-04-01T00:00:00Z)"
            )
    elif expires_in_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
    elif expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    # 生成或验证分享码
    if not share_code:
        share_code = generate_share_code(16)
    elif len(share_code) < 6 or len(share_code) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="分享码长度应在 6-20 字符之间"
        )

    # 检查分享码是否已存在 (跨表检查)
    existing_file = await db.execute(
        select(FileShare).where(FileShare.share_code == share_code)
    )
    existing_assoc = await db.execute(
        select(FileAssociationShare).where(FileAssociationShare.share_code == share_code)
    )
    if existing_file.scalar_one_or_none() or existing_assoc.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="分享码已存在，请使用其他分享码"
        )

    # 创建分享记录
    share_code_hash = hash_share_code(share_code)
    file_share = FileShare(
        file_id=file_id,
        created_by=current_user.id,
        share_code=share_code,
        share_code_hash=share_code_hash,
        expires_at=expires_at,
        is_code_required=is_code_required,
        max_downloads=max_downloads,
    )
    db.add(file_share)
    await db.commit()
    await db.refresh(file_share)

    return {
        "id": str(file_share.id),
        "share_code": share_code,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "is_code_required": is_code_required,
        "max_downloads": max_downloads,
        "share_url": f"/share/file/{share_code}",
        "share_type": "file",
    }


@router.get("/files/{file_id}/shares")
async def list_file_shares(
    db: DatabaseSession,
    file_id: str,
    current_user: CurrentActiveUser,
):
    """列出文件的所有分享"""
    result = await db.execute(select(MediaFile).where(MediaFile.id == file_id))
    media_file = result.scalar_one_or_none()
    if not media_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    # 验证权限
    await require_project_role(db, current_user, str(media_file.project_id), "member")

    result = await db.execute(
        select(FileShare).where(FileShare.file_id == file_id)
    )
    shares = result.scalars().all()

    return {
        "items": [
            {
                "id": str(s.id),
                "share_code": s.share_code,
                "share_type": "file",
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "is_expired": bool(s.expires_at and datetime.now(timezone.utc) > s.expires_at),
                "is_code_required": s.is_code_required,
                "view_count": s.view_count,
                "download_count": s.download_count,
                "max_downloads": s.max_downloads,
                "is_download_exhausted": bool(s.max_downloads and s.download_count >= s.max_downloads),
                "created_at": s.created_at.isoformat(),
                "last_accessed_at": s.last_accessed_at.isoformat() if s.last_accessed_at else None,
                "share_url": f"/share/file/{s.share_code}",
            }
            for s in shares
        ]
    }


@router.delete("/file-shares/{share_id}")
async def delete_file_share(
    db: DatabaseSession,
    share_id: str,
    current_user: CurrentActiveUser,
):
    """撤销文件分享"""
    result = await db.execute(select(FileShare).where(FileShare.id == share_id))
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享不存在")

    # 验证权限: 创建者或项目管理员可以删除
    media_file_result = await db.execute(select(MediaFile).where(MediaFile.id == share.file_id))
    media_file = media_file_result.scalar_one_or_none()
    if media_file:
        try:
            await require_project_role(db, current_user, str(media_file.project_id), "admin")
        except HTTPException:
            # 非管理员则只有创建者可以删除
            if str(share.created_by) != str(current_user.id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除此分享")
    else:
        if str(share.created_by) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除此分享")

    await db.delete(share)
    await db.commit()

    return {"message": "分享已撤销"}


# ============================================================================
# 公开分享访问 API (无需认证)
# ============================================================================

@router.get("/share/file/{share_code}")
async def access_file_share(
    db: DatabaseSession,
    share_code: str,
):
    """访问共享文件 (无需认证)"""
    share_code_hash = hash_share_code(share_code)
    result = await db.execute(
        select(FileShare).where(FileShare.share_code_hash == share_code_hash)
    )
    share = result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享不存在或链接无效")

    # 验证过期
    if share.expires_at:
        exp = share.expires_at.replace(tzinfo=timezone.utc) if share.expires_at.tzinfo is None else share.expires_at
        if datetime.now(timezone.utc) > exp:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="分享已过期")

    # 验证下载次数
    if share.max_downloads and share.download_count >= share.max_downloads:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="分享的下载次数已达上限")

    # 更新访问统计
    share.view_count += 1
    share.last_accessed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(share)

    # 返回文件信息
    media_file_result = await db.execute(select(MediaFile).where(MediaFile.id == share.file_id))
    file = media_file_result.scalar_one_or_none()

    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件已被删除")

    return {
        "share_type": "file",
        "file": {
            "id": str(file.id),
            "filename": file.filename,
            "original_filename": file.original_filename,
            "file_type": file.file_type,
            "file_size": file.file_size,
            "duration": file.duration,
            "sample_rate": file.sample_rate,
            "channels": file.channels,
        },
        "share": {
            "id": str(share.id),
            "view_count": share.view_count,
            "download_count": share.download_count,
            "max_downloads": share.max_downloads,
            "expires_at": share.expires_at.isoformat() if share.expires_at else None,
            "is_code_required": share.is_code_required,
        },
        "download_url": f"/api/v1/share/file/{share_code}/download",
        "stream_url": f"/api/v1/share/file/{share_code}/stream",
    }


@router.get("/share/file/{share_code}/download")
async def download_shared_file(
    db: DatabaseSession,
    share_code: str,
):
    """下载共享文件 (无需认证)"""
    share_code_hash = hash_share_code(share_code)
    result = await db.execute(
        select(FileShare).where(FileShare.share_code_hash == share_code_hash)
    )
    share = result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享不存在")

    # 验证过期
    if share.expires_at:
        exp = share.expires_at.replace(tzinfo=timezone.utc) if share.expires_at.tzinfo is None else share.expires_at
        if datetime.now(timezone.utc) > exp:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="分享已过期")

    # 验证下载次数
    if share.max_downloads and share.download_count >= share.max_downloads:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="下载次数已达上限")

    # 获取文件
    media_file_result = await db.execute(select(MediaFile).where(MediaFile.id == share.file_id))
    media_file = media_file_result.scalar_one_or_none()
    if not media_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件已被删除")

    storage = await get_storage_for_file(db, media_file)

    # 增加下载计数
    share.download_count += 1
    share.last_accessed_at = datetime.now(timezone.utc)
    await db.commit()

    # 推断 MIME 类型
    ext = os.path.splitext(media_file.file_path)[1].lower()
    mime_map = {
        ".wav": "audio/wav", ".mp3": "audio/mpeg", ".mp4": "video/mp4",
        ".avi": "video/x-msvideo", ".mov": "video/quicktime",
        ".m4a": "audio/mp4", ".flac": "audio/flac", ".ogg": "audio/ogg",
        ".webm": "video/webm",
    }
    media_type = mime_map.get(ext, "application/octet-stream")

    # 本地存储 → FileResponse
    if isinstance(storage, LocalStorageBackend):
        local_path = storage.get_local_path(media_file.file_path)
        if not os.path.exists(local_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件内容不存在")
        return FileResponse(
            path=local_path,
            filename=media_file.original_filename,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{media_file.original_filename}"'},
        )

    # S3/COS → 流式代理
    try:
        data = await storage.get(media_file.file_path)
        import io
        return StreamingResponse(
            io.BytesIO(data),
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{media_file.original_filename}"',
                "Content-Length": str(len(data)),
            },
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件内容不存在")


@router.get("/share/file/{share_code}/stream")
async def stream_shared_file(
    db: DatabaseSession,
    share_code: str,
):
    """流式播放共享文件 (无需认证，用于前端 <audio>/<video> 元素)"""
    share_code_hash = hash_share_code(share_code)
    result = await db.execute(
        select(FileShare).where(FileShare.share_code_hash == share_code_hash)
    )
    share = result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享不存在")

    # 验证过期
    if share.expires_at:
        exp = share.expires_at.replace(tzinfo=timezone.utc) if share.expires_at.tzinfo is None else share.expires_at
        if datetime.now(timezone.utc) > exp:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="分享已过期")

    media_file_result = await db.execute(select(MediaFile).where(MediaFile.id == share.file_id))
    media_file = media_file_result.scalar_one_or_none()
    if not media_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件已被删除")

    storage = await get_storage_for_file(db, media_file)

    ext = os.path.splitext(media_file.file_path)[1].lower()
    mime_map = {
        ".wav": "audio/wav", ".mp3": "audio/mpeg", ".mp4": "video/mp4",
        ".avi": "video/x-msvideo", ".mov": "video/quicktime",
        ".m4a": "audio/mp4", ".flac": "audio/flac", ".ogg": "audio/ogg",
        ".webm": "video/webm",
    }
    media_type = mime_map.get(ext, "application/octet-stream")

    if isinstance(storage, LocalStorageBackend):
        local_path = storage.get_local_path(media_file.file_path)
        if not os.path.exists(local_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件内容不存在")
        return FileResponse(
            path=local_path,
            filename=media_file.original_filename,
            media_type=media_type,
        )

    try:
        data = await storage.get(media_file.file_path)
        import io
        return StreamingResponse(
            io.BytesIO(data),
            media_type=media_type,
            headers={
                "Content-Disposition": f'inline; filename="{media_file.original_filename}"',
                "Content-Length": str(len(data)),
            },
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件内容不存在")


# ============================================================================
# 关联分享 API
# ============================================================================

@router.post("/associations/{association_id}/share")
async def create_association_share(
    db: DatabaseSession,
    association_id: str,
    current_user: CurrentActiveUser,
    expires_in_hours: Optional[int] = Query(None),
    expires_in_days: Optional[int] = Query(None),
    expires_at_custom: Optional[str] = Query(None, description="自定义过期时间 (ISO 8601)"),
    share_code: Optional[str] = Query(None, description="自定义分享码 (6-20 字符)"),
    is_code_required: bool = Query(True),
    max_downloads: Optional[int] = Query(None),
):
    """创建关联共享 (同时共享 ECG/PCG/Video 关联的所有文件)"""
    result = await db.execute(
        select(FileAssociation).where(FileAssociation.id == association_id)
    )
    association = result.scalar_one_or_none()
    if not association:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联不存在")

    # 验证权限
    await require_project_role(db, current_user, str(association.project_id), "member")

    # 计算过期时间
    expires_at = None
    if expires_at_custom:
        try:
            expires_at = datetime.fromisoformat(expires_at_custom.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="自定义过期时间格式无效"
            )
    elif expires_in_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
    elif expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    # 生成或验证分享码
    if not share_code:
        share_code = generate_share_code(16)
    elif len(share_code) < 6 or len(share_code) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="分享码长度应在 6-20 字符之间"
        )

    # 跨表检查分享码唯一性
    existing_file = await db.execute(
        select(FileShare).where(FileShare.share_code == share_code)
    )
    existing_assoc = await db.execute(
        select(FileAssociationShare).where(FileAssociationShare.share_code == share_code)
    )
    if existing_file.scalar_one_or_none() or existing_assoc.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="分享码已存在，请使用其他分享码"
        )

    # 创建关联分享
    share_code_hash = hash_share_code(share_code)
    assoc_share = FileAssociationShare(
        association_id=association_id,
        created_by=current_user.id,
        share_code=share_code,
        share_code_hash=share_code_hash,
        expires_at=expires_at,
        is_code_required=is_code_required,
        max_downloads=max_downloads,
    )
    db.add(assoc_share)
    await db.commit()
    await db.refresh(assoc_share)

    return {
        "id": str(assoc_share.id),
        "share_code": share_code,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "max_downloads": max_downloads,
        "share_url": f"/share/association/{share_code}",
        "share_type": "association",
    }


@router.get("/associations/{association_id}/shares")
async def list_association_shares(
    db: DatabaseSession,
    association_id: str,
    current_user: CurrentActiveUser,
):
    """列出关联的所有分享"""
    result = await db.execute(
        select(FileAssociation).where(FileAssociation.id == association_id)
    )
    association = result.scalar_one_or_none()
    if not association:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联不存在")

    await require_project_role(db, current_user, str(association.project_id), "member")

    result = await db.execute(
        select(FileAssociationShare).where(FileAssociationShare.association_id == association_id)
    )
    shares = result.scalars().all()

    return {
        "items": [
            {
                "id": str(s.id),
                "share_code": s.share_code,
                "share_type": "association",
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "is_expired": bool(s.expires_at and datetime.now(timezone.utc) > s.expires_at),
                "is_code_required": s.is_code_required,
                "view_count": s.view_count,
                "download_count": s.download_count,
                "max_downloads": s.max_downloads,
                "is_download_exhausted": bool(s.max_downloads and s.download_count >= s.max_downloads),
                "created_at": s.created_at.isoformat(),
                "last_accessed_at": s.last_accessed_at.isoformat() if s.last_accessed_at else None,
                "share_url": f"/share/association/{s.share_code}",
            }
            for s in shares
        ]
    }


@router.delete("/association-shares/{share_id}")
async def delete_association_share(
    db: DatabaseSession,
    share_id: str,
    current_user: CurrentActiveUser,
):
    """撤销关联分享"""
    result = await db.execute(select(FileAssociationShare).where(FileAssociationShare.id == share_id))
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享不存在")

    # 验证权限: 创建者或项目管理员可以删除
    assoc_result = await db.execute(select(FileAssociation).where(FileAssociation.id == share.association_id))
    association = assoc_result.scalar_one_or_none()
    if association:
        try:
            await require_project_role(db, current_user, str(association.project_id), "admin")
        except HTTPException:
            if str(share.created_by) != str(current_user.id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除此分享")
    else:
        if str(share.created_by) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除此分享")

    await db.delete(share)
    await db.commit()

    return {"message": "分享已撤销"}


@router.get("/share/association/{share_code}")
async def access_association_share(
    db: DatabaseSession,
    share_code: str,
):
    """访问共享关联 (无需认证)"""
    share_code_hash = hash_share_code(share_code)
    result = await db.execute(
        select(FileAssociationShare).where(FileAssociationShare.share_code_hash == share_code_hash)
    )
    share = result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享不存在或链接无效")

    # 验证过期和下载限制
    if share.expires_at:
        exp = share.expires_at.replace(tzinfo=timezone.utc) if share.expires_at.tzinfo is None else share.expires_at
        if datetime.now(timezone.utc) > exp:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="分享已过期")

    if share.max_downloads and share.download_count >= share.max_downloads:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="下载次数已达上限")

    # 更新统计
    share.view_count += 1
    share.last_accessed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(share)

    # 返回关联信息和文件列表
    result = await db.execute(
        select(FileAssociation).where(FileAssociation.id == share.association_id)
    )
    association = result.scalar_one_or_none()
    if not association:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联已被删除")

    files = {}
    file_stream_urls = {}
    for file_type, file_id_attr in [("ecg", "ecg_file_id"), ("pcg", "pcg_file_id"), ("video", "video_file_id")]:
        fid = getattr(association, file_id_attr)
        if fid:
            f_result = await db.execute(select(MediaFile).where(MediaFile.id == fid))
            file = f_result.scalar_one_or_none()
            if file:
                files[file_type] = {
                    "id": str(file.id),
                    "filename": file.filename,
                    "original_filename": file.original_filename,
                    "file_type": file.file_type,
                    "file_size": file.file_size,
                    "duration": file.duration,
                    "sample_rate": file.sample_rate,
                    "channels": file.channels,
                }
                file_stream_urls[file_type] = f"/api/v1/share/association/{share_code}/file/{file_type}/stream"

    return {
        "share_type": "association",
        "association": {
            "id": str(association.id),
            "name": association.name if hasattr(association, 'name') else None,
            "pcg_offset": association.pcg_offset,
            "video_offset": association.video_offset,
            "files": files,
        },
        "share": {
            "id": str(share.id),
            "view_count": share.view_count,
            "download_count": share.download_count,
            "max_downloads": share.max_downloads,
            "expires_at": share.expires_at.isoformat() if share.expires_at else None,
            "is_code_required": share.is_code_required,
        },
        "stream_urls": file_stream_urls,
    }


@router.get("/share/association/{share_code}/file/{file_type}/stream")
async def stream_association_file(
    request: Request,
    db: DatabaseSession,
    share_code: str,
    file_type: str,
):
    """流式播放关联共享中的某个文件 (无需认证)

    file_type: ecg | pcg | video
    """
    if file_type not in ("ecg", "pcg", "video"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的文件类型")

    share_code_hash = hash_share_code(share_code)
    result = await db.execute(
        select(FileAssociationShare).where(FileAssociationShare.share_code_hash == share_code_hash)
    )
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享不存在")

    # 验证
    if share.expires_at:
        exp = share.expires_at.replace(tzinfo=timezone.utc) if share.expires_at.tzinfo is None else share.expires_at
        if datetime.now(timezone.utc) > exp:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="分享已过期")

    # 获取关联和文件
    assoc_result = await db.execute(select(FileAssociation).where(FileAssociation.id == share.association_id))
    association = assoc_result.scalar_one_or_none()
    if not association:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联已被删除")

    file_id_map = {"ecg": association.ecg_file_id, "pcg": association.pcg_file_id, "video": association.video_file_id}
    fid = file_id_map.get(file_type)
    if not fid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"关联中没有 {file_type} 文件")

    file_result = await db.execute(select(MediaFile).where(MediaFile.id == fid))
    media_file = file_result.scalar_one_or_none()
    if not media_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件已被删除")

    storage = await get_storage_for_file(db, media_file)

    ext = os.path.splitext(media_file.file_path)[1].lower()
    mime_map = {
        ".wav": "audio/wav", ".mp3": "audio/mpeg", ".mp4": "video/mp4",
        ".avi": "video/x-msvideo", ".mov": "video/quicktime",
        ".m4a": "audio/mp4", ".flac": "audio/flac", ".ogg": "audio/ogg",
        ".webm": "video/webm",
    }
    media_type_val = mime_map.get(ext, "application/octet-stream")

    range_header = request.headers.get("range")

    if isinstance(storage, LocalStorageBackend):
        local_path = storage.get_local_path(media_file.file_path)
        if not os.path.exists(local_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件内容不存在")
        return build_file_stream_response(
            path=local_path,
            filename=media_file.original_filename,
            media_type=media_type_val,
            disposition="inline",
            range_header=range_header,
        )

    try:
        data = await storage.get(media_file.file_path)
        return build_bytes_stream_response(
            data=data,
            filename=media_file.original_filename,
            media_type=media_type_val,
            disposition="inline",
            range_header=range_header,
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件内容不存在")
