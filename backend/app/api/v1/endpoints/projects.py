"""项目端点"""
import os
import tempfile
import uuid
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentActiveUser, DatabaseSession
from app.models.base import ErrorResponse
from app.models.project import Project, ProjectMember, MediaFile
from app.models.user import User  # noqa: F401 — 确保 User 被注册到 SQLAlchemy mapper
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    ProjectMemberCreate,
    ProjectMemberResponse,
    MediaFileResponse,
    MediaFileListResponse,
)
from app.services.storage_manager import get_storage_backend
from app.utils.security import sanitize_filename

router = APIRouter()


def _is_admin(user) -> bool:
    return bool(user.is_superuser or user.role == "admin")


@router.get(
    "/",
    response_model=ProjectListResponse,
)
async def list_projects(
    db: DatabaseSession,
    current_user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 20,
) -> ProjectListResponse:
    """获取当前用户的项目列表"""
    from sqlalchemy import or_

    stmt = (
        select(Project)
        .where(
            or_(
                Project.owner_id == current_user.id,
                Project.is_public == True,
                Project.id.in_(
                    select(ProjectMember.project_id).where(
                        ProjectMember.user_id == current_user.id
                    )
                ),
            )
        )
        .order_by(Project.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    projects = list(result.scalars().all())

    # count
    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(Project).where(
        or_(
            Project.owner_id == current_user.id,
            Project.is_public == True,
            Project.id.in_(
                select(ProjectMember.project_id).where(
                    ProjectMember.user_id == current_user.id
                )
            ),
        )
    )
    total = (await db.execute(count_stmt)).scalar_one()

    page = skip // limit + 1
    return ProjectListResponse(
        items=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
        page=page,
        size=limit,
        has_next=(skip + limit) < total,
    )


@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    db: DatabaseSession,
    project_data: ProjectCreate,
    current_user: CurrentActiveUser,
) -> ProjectResponse:
    """创建项目"""
    project = Project(
        id=uuid.uuid4(),
        owner_id=current_user.id,
        name=project_data.name,
        description=project_data.description,
        is_public=project_data.is_public,
    )
    db.add(project)
    await db.flush()

    # 添加创建者为 owner 成员
    member = ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role="owner",
    )
    db.add(member)
    await db.flush()
    await db.refresh(project)
    await db.commit()

    return ProjectResponse.model_validate(project)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={
        404: {"model": ErrorResponse, "description": "项目不存在"},
        403: {"model": ErrorResponse, "description": "无访问权限"},
    },
)
async def get_project(
    db: DatabaseSession,
    project_id: str,
    current_user: CurrentActiveUser,
) -> ProjectResponse:
    """获取项目详情"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    if not _is_admin(current_user) and not project.is_public and str(project.owner_id) != str(current_user.id):
        # Check membership
        mem_result = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.id,
            )
        )
        if not mem_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无访问权限")

    return ProjectResponse.model_validate(project)


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={
        404: {"model": ErrorResponse, "description": "项目不存在"},
        403: {"model": ErrorResponse, "description": "无修改权限"},
    },
)
async def update_project(
    db: DatabaseSession,
    project_id: str,
    update_data: ProjectUpdate,
    current_user: CurrentActiveUser,
) -> ProjectResponse:
    """更新项目"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    if not _is_admin(current_user) and str(project.owner_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有项目所有者可以修改项目")

    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(project, key, value)

    await db.flush()
    await db.refresh(project)
    await db.commit()

    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse, "description": "项目不存在"},
        403: {"model": ErrorResponse, "description": "无删除权限"},
    },
)
async def delete_project(
    db: DatabaseSession,
    project_id: str,
    current_user: CurrentActiveUser,
) -> None:
    """删除项目"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    if not _is_admin(current_user) and str(project.owner_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有项目所有者可以删除项目")

    await db.delete(project)
    await db.commit()


@router.get(
    "/{project_id}/members",
    response_model=List[ProjectMemberResponse],
)
async def list_members(
    db: DatabaseSession,
    project_id: str,
    current_user: CurrentActiveUser,
) -> List[ProjectMemberResponse]:
    """获取项目成员列表"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    mem_result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    )
    members = list(mem_result.scalars().all())

    # Build response with user info
    response = []
    from app.models.user import User
    for m in members:
        user_result = await db.execute(select(User).where(User.id == m.user_id))
        user = user_result.scalar_one_or_none()
        user_info = {"id": str(m.user_id), "username": "unknown"}
        if user:
            user_info = {"id": str(user.id), "username": user.username, "email": user.email}
        response.append(ProjectMemberResponse(
            id=str(m.id),
            project_id=str(m.project_id),
            user_id=str(m.user_id),
            role=m.role,
            created_at=m.created_at,
            user=user_info,
        ))
    return response


@router.post(
    "/{project_id}/members",
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    db: DatabaseSession,
    project_id: str,
    member_data: ProjectMemberCreate,
    current_user: CurrentActiveUser,
):
    """添加项目成员（user_id 直接添加；email 发送邀请通知）"""
    from app.models.notification import Notification

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    if str(project.owner_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有项目所有者可以添加成员")

    from app.models.user import User

    # 确定目标用户
    if member_data.email:
        user_result = await db.execute(select(User).where(User.email == member_data.email))
        target_user = user_result.scalar_one_or_none()
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该邮箱未注册")

        # 不能邀请自己
        if str(target_user.id) == str(current_user.id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能邀请自己")

        # 已是成员
        existing = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == target_user.id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户已是项目成员")

        # 检查是否已有待处理邀请
        existing_notif = await db.execute(
            select(Notification).where(
                Notification.recipient_id == target_user.id,
                Notification.notification_type == "project_invite",
                Notification.status == "pending",
                Notification.data["project_id"].astext == project_id,
            )
        )
        if existing_notif.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已向该用户发送过邀请")

        # 创建邀请通知
        notif = Notification(
            recipient_id=target_user.id,
            sender_id=current_user.id,
            notification_type="project_invite",
            title=f"项目邀请：{project.name}",
            content=f"{current_user.username} 邀请您加入项目「{project.name}」，担任{member_data.role.value}角色。",
            status="pending",
            data={
                "project_id": project_id,
                "project_name": project.name,
                "member_role": member_data.role.value,
                "inviter_username": current_user.username,
            },
        )
        db.add(notif)
        await db.commit()

        return {
            "type": "invitation_sent",
            "message": f"已向 {target_user.username} ({member_data.email}) 发送邀请",
            "recipient_username": target_user.username,
        }

    elif member_data.user_id:
        # 直接添加（保持原有逻辑）
        user_result = await db.execute(select(User).where(User.id == member_data.user_id))
        target_user = user_result.scalar_one_or_none()
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

        existing = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == member_data.user_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户已是项目成员")

        member = ProjectMember(
            project_id=uuid.UUID(project_id),
            user_id=uuid.UUID(member_data.user_id),
            role=member_data.role.value,
        )
        db.add(member)
        await db.flush()
        await db.refresh(member)
        await db.commit()

        return ProjectMemberResponse(
            id=str(member.id),
            project_id=str(member.project_id),
            user_id=str(member.user_id),
            role=member.role,
            created_at=member.created_at,
            user={"id": str(target_user.id), "username": target_user.username, "email": target_user.email},
        )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="必须提供 user_id 或 email")


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    db: DatabaseSession,
    project_id: str,
    user_id: str,
    current_user: CurrentActiveUser,
) -> None:
    """移除项目成员"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    if str(project.owner_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有项目所有者可以移除成员")

    mem_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = mem_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")

    await db.delete(member)
    await db.commit()


@router.get(
    "/{project_id}/files",
    response_model=MediaFileListResponse,
)
async def list_files(
    db: DatabaseSession,
    project_id: str,
    current_user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 500,
    q: Optional[str] = Query(None, description="搜索文件名"),
    file_type: Optional[str] = Query(None, description="按文件类型筛选: audio|video|ecg|pcg|other"),
) -> MediaFileListResponse:
    """获取项目文件列表（支持搜索和类型筛选）"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    stmt = select(MediaFile).where(MediaFile.project_id == project_id)

    # 文件名搜索
    if q:
        stmt = stmt.where(
            MediaFile.original_filename.ilike(f"%{q}%")
        )
    # 文件类型筛选
    if file_type:
        stmt = stmt.where(MediaFile.file_type == file_type)

    stmt = stmt.order_by(MediaFile.created_at.desc())

    files_result = await db.execute(stmt.offset(skip).limit(limit))
    files = list(files_result.scalars().all())

    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(MediaFile).where(MediaFile.project_id == project_id)
    if q:
        count_stmt = count_stmt.where(MediaFile.original_filename.ilike(f"%{q}%"))
    if file_type:
        count_stmt = count_stmt.where(MediaFile.file_type == file_type)
    total = (await db.execute(count_stmt)).scalar_one()

    page = skip // limit + 1
    return MediaFileListResponse(
        items=[MediaFileResponse.model_validate(f) for f in files],
        total=total,
        page=page,
        size=limit,
        has_next=(skip + limit) < total,
    )


@router.post(
    "/{project_id}/files/upload",
    response_model=MediaFileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    db: DatabaseSession,
    project_id: str,
    current_user: CurrentActiveUser,
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
) -> MediaFileResponse:
    """上传文件到项目（MP3/OGG/FLAC 等音频自动转换为 WAV）"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    # Determine file type
    original_filename = file.filename or "unknown"
    ext = os.path.splitext(original_filename)[1].lower()
    file_type_map = {
        ".wav": "audio", ".mp3": "audio", ".m4a": "audio",
        ".flac": "audio", ".ogg": "audio",
        ".mp4": "video", ".avi": "video", ".mov": "video",
        ".ecg": "ecg", ".pcg": "pcg",
    }
    file_type = file_type_map.get(ext, "other")

    # 需要转换为 WAV 的格式（soundfile 可读取 MP3/OGG/FLAC）
    CONVERTIBLE_EXTS = {".mp3", ".ogg", ".flac"}
    # M4A (AAC) 目前不被 soundfile 支持，明确拒绝
    UNSUPPORTED_AUDIO = {".m4a", ".aac", ".wma"}
    needs_conversion = ext in CONVERTIBLE_EXTS

    if ext in UNSUPPORTED_AUDIO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"暂不支持 {ext} 格式。请先将文件转换为 WAV 或 MP3 后再上传。"
        )

    safe_filename = sanitize_filename(original_filename)
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"

    content = await file.read()
    file_size = len(content)

    # ── 写入临时目录进行格式转换 ─────────────────────────────────
    duration = None
    sample_rate_val = None
    channels_val = None
    final_content = content  # 最终要上传到存储后端的字节

    if needs_conversion:
        tmp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, unique_filename)
        try:
            with open(tmp_path, "wb") as f:
                f.write(content)

            import soundfile as sf
            import numpy as np

            data, sr = sf.read(tmp_path, dtype="float32")
            sample_rate_val = float(sr)
            channels_val = 1 if data.ndim == 1 else data.shape[1]
            duration = len(data) / sr if data.ndim == 1 else data.shape[0] / sr

            if data.ndim > 1:
                data = data[:, 0]
            peak = np.max(np.abs(data))
            if peak > 0:
                data = data / peak * 0.95
            pcm_i16 = (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)

            wav_filename = os.path.splitext(unique_filename)[0] + ".wav"
            wav_path = os.path.join(tmp_dir, wav_filename)

            import wave
            with wave.open(wav_path, "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(pcm_i16.tobytes())

            unique_filename = wav_filename
            with open(wav_path, "rb") as f:
                final_content = f.read()
            file_size = len(final_content)

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("音频转换失败 (%s): %s", ext, e)
            # 转换失败仍保存原始文件
            final_content = content
        finally:
            # 清理临时文件
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    elif ext == ".wav":
        # WAV 文件直接提取元数据（用临时文件）
        try:
            import wave as wave_mod
            import io
            with wave_mod.open(io.BytesIO(content), "r") as wf:
                sample_rate_val = float(wf.getframerate())
                channels_val = wf.getnchannels()
                duration = wf.getnframes() / wf.getframerate()
        except Exception:
            pass

    # ── 上传到存储后端 ───────────────────────────────────────────
    storage = await get_storage_backend(db)
    storage_key = f"{project_id}/{unique_filename}"
    await storage.put(storage_key, final_content)

    # 记录文件实际存储到哪个后端
    from app.services.storage import S3StorageBackend
    backend_type = "cos" if isinstance(storage, S3StorageBackend) else "local"

    # Parse metadata
    extra_meta = {}
    if metadata:
        import json
        try:
            extra_meta = json.loads(metadata)
        except Exception:
            pass

    media_file = MediaFile(
        project_id=uuid.UUID(project_id),
        filename=unique_filename,
        original_filename=original_filename,
        file_type=file_type,
        file_size=file_size,
        file_path=storage_key,
        storage_backend=backend_type,
        duration=duration,
        sample_rate=sample_rate_val,
        channels=channels_val,
        file_metadata=extra_meta,
    )
    db.add(media_file)
    await db.flush()
    await db.refresh(media_file)
    await db.commit()

    return MediaFileResponse.model_validate(media_file)
