"""
文件关联端点
支持在同一项目内关联 ECG / PCG / Video 文件，并进行同步预览。
"""
from __future__ import annotations

import uuid
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.models  # noqa: F401
from app.core.deps import CurrentActiveUser, DatabaseSession
from app.models.project import FileAssociation, MediaFile, Project

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class FileInfo(BaseModel):
    id: str
    original_filename: str
    filename: str
    file_type: str
    duration: Optional[float] = None
    sample_rate: Optional[float] = None


class AssociationCreate(BaseModel):
    project_id: str
    name: str = Field(default="", max_length=200)
    ecg_file_id: Optional[str] = None
    pcg_file_id: Optional[str] = None
    video_file_id: Optional[str] = None
    pcg_offset: float = Field(default=0.0, ge=-3600, le=3600)
    video_offset: float = Field(default=0.0, ge=-3600, le=3600)
    notes: Optional[str] = Field(default=None, max_length=1000)


class AssociationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    ecg_file_id: Optional[str] = None
    pcg_file_id: Optional[str] = None
    video_file_id: Optional[str] = None
    pcg_offset: Optional[float] = Field(default=None, ge=-3600, le=3600)
    video_offset: Optional[float] = Field(default=None, ge=-3600, le=3600)
    notes: Optional[str] = Field(default=None, max_length=1000)


class AssociationResponse(BaseModel):
    id: str
    project_id: str
    created_by: str
    name: str
    ecg_file_id: Optional[str]
    pcg_file_id: Optional[str]
    video_file_id: Optional[str]
    pcg_offset: float
    video_offset: float
    notes: Optional[str]
    created_at: str
    updated_at: str
    # 扩展：附带文件信息
    ecg_file: Optional[FileInfo] = None
    pcg_file: Optional[FileInfo] = None
    video_file: Optional[FileInfo] = None


def _file_info(f: MediaFile | None) -> Optional[FileInfo]:
    if f is None:
        return None
    return FileInfo(
        id=str(f.id),
        original_filename=f.original_filename,
        filename=f.filename,
        file_type=f.file_type,
        duration=f.duration,
        sample_rate=f.sample_rate,
    )


def _assoc_to_resp(a: FileAssociation) -> AssociationResponse:
    return AssociationResponse(
        id=str(a.id),
        project_id=str(a.project_id),
        created_by=str(a.created_by),
        name=a.name or "",
        ecg_file_id=str(a.ecg_file_id) if a.ecg_file_id else None,
        pcg_file_id=str(a.pcg_file_id) if a.pcg_file_id else None,
        video_file_id=str(a.video_file_id) if a.video_file_id else None,
        pcg_offset=a.pcg_offset,
        video_offset=a.video_offset,
        notes=a.notes,
        created_at=a.created_at.isoformat(),
        updated_at=a.updated_at.isoformat(),
        ecg_file=_file_info(a.ecg_file),
        pcg_file=_file_info(a.pcg_file),
        video_file=_file_info(a.video_file),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/project/{project_id}", response_model=List[AssociationResponse])
async def list_associations(
    project_id: str,
    db: DatabaseSession,
    current_user: CurrentActiveUser,
) -> List[AssociationResponse]:
    """获取项目内所有文件关联"""
    stmt = (
        select(FileAssociation)
        .where(FileAssociation.project_id == project_id)
        .options(
            selectinload(FileAssociation.ecg_file),
            selectinload(FileAssociation.pcg_file),
            selectinload(FileAssociation.video_file),
        )
        .order_by(FileAssociation.created_at.desc())
    )
    result = await db.execute(stmt)
    assocs = list(result.scalars().all())
    return [_assoc_to_resp(a) for a in assocs]


@router.post("/", response_model=AssociationResponse, status_code=status.HTTP_201_CREATED)
async def create_association(
    body: AssociationCreate,
    db: DatabaseSession,
    current_user: CurrentActiveUser,
) -> AssociationResponse:
    """创建文件关联"""
    # 验证项目存在
    proj_r = await db.execute(select(Project).where(Project.id == body.project_id))
    if not proj_r.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在")

    # 验证各文件属于同一项目
    for fid in [body.ecg_file_id, body.pcg_file_id, body.video_file_id]:
        if fid:
            fr = await db.execute(select(MediaFile).where(MediaFile.id == fid))
            f = fr.scalar_one_or_none()
            if not f:
                raise HTTPException(status_code=404, detail=f"文件 {fid} 不存在")
            if str(f.project_id) != body.project_id:
                raise HTTPException(status_code=400, detail=f"文件 {fid} 不属于该项目")

    assoc = FileAssociation(
        id=uuid.uuid4(),
        project_id=body.project_id,
        created_by=current_user.id,
        name=body.name or "",
        ecg_file_id=body.ecg_file_id or None,
        pcg_file_id=body.pcg_file_id or None,
        video_file_id=body.video_file_id or None,
        pcg_offset=body.pcg_offset,
        video_offset=body.video_offset,
        notes=body.notes,
    )
    db.add(assoc)
    await db.flush()
    await db.commit()

    # 重新查询以加载关联文件
    stmt = (
        select(FileAssociation)
        .where(FileAssociation.id == assoc.id)
        .options(
            selectinload(FileAssociation.ecg_file),
            selectinload(FileAssociation.pcg_file),
            selectinload(FileAssociation.video_file),
        )
    )
    result2 = await db.execute(stmt)
    assoc = result2.scalar_one()

    return _assoc_to_resp(assoc)


@router.get("/{assoc_id}", response_model=AssociationResponse)
async def get_association(
    assoc_id: str,
    db: DatabaseSession,
    current_user: CurrentActiveUser,
) -> AssociationResponse:
    """获取单个文件关联详情"""
    stmt = (
        select(FileAssociation)
        .where(FileAssociation.id == assoc_id)
        .options(
            selectinload(FileAssociation.ecg_file),
            selectinload(FileAssociation.pcg_file),
            selectinload(FileAssociation.video_file),
        )
    )
    result = await db.execute(stmt)
    assoc = result.scalar_one_or_none()
    if not assoc:
        raise HTTPException(status_code=404, detail="关联不存在")
    return _assoc_to_resp(assoc)


@router.patch("/{assoc_id}", response_model=AssociationResponse)
async def update_association(
    assoc_id: str,
    body: AssociationUpdate,
    db: DatabaseSession,
    current_user: CurrentActiveUser,
) -> AssociationResponse:
    """更新文件关联（修改文件绑定或偏移量）"""
    result = await db.execute(select(FileAssociation).where(FileAssociation.id == assoc_id))
    assoc = result.scalar_one_or_none()
    if not assoc:
        raise HTTPException(status_code=404, detail="关联不存在")

    if body.name is not None:
        assoc.name = body.name
    if body.pcg_offset is not None:
        assoc.pcg_offset = body.pcg_offset
    if body.video_offset is not None:
        assoc.video_offset = body.video_offset
    if body.notes is not None:
        assoc.notes = body.notes

    # 文件字段：None 表示不改动，空字符串 "" 表示清除
    for body_attr, model_attr in [
        ("ecg_file_id", "ecg_file_id"),
        ("pcg_file_id", "pcg_file_id"),
        ("video_file_id", "video_file_id"),
    ]:
        val = getattr(body, body_attr)
        if val is not None:
            setattr(assoc, model_attr, val if val else None)

    await db.flush()
    await db.commit()

    # 重新查询以加载关联文件
    stmt = (
        select(FileAssociation)
        .where(FileAssociation.id == assoc_id)
        .options(
            selectinload(FileAssociation.ecg_file),
            selectinload(FileAssociation.pcg_file),
            selectinload(FileAssociation.video_file),
        )
    )
    result2 = await db.execute(stmt)
    assoc = result2.scalar_one()

    return _assoc_to_resp(assoc)


@router.delete("/{assoc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_association(
    assoc_id: str,
    db: DatabaseSession,
    current_user: CurrentActiveUser,
):
    """删除文件关联"""
    result = await db.execute(select(FileAssociation).where(FileAssociation.id == assoc_id))
    assoc = result.scalar_one_or_none()
    if not assoc:
        raise HTTPException(status_code=404, detail="关联不存在")
    await db.delete(assoc)
    await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# 自动关联（基于模拟生成的 ECG/PCG）
# ─────────────────────────────────────────────────────────────────────────────

class AutoAssociateRequest(BaseModel):
    project_id: str
    ecg_file_id: str
    pcg_file_id: str
    name: Optional[str] = None


@router.post("/auto", response_model=AssociationResponse, status_code=status.HTTP_201_CREATED)
async def auto_associate(
    body: AutoAssociateRequest,
    db: DatabaseSession,
    current_user: CurrentActiveUser,
) -> AssociationResponse:
    """
    将模拟生成的 ECG + PCG 自动关联（偏移默认 0，因为它们是同步生成的）
    """
    # 验证文件存在且同属该项目
    for fid in [body.ecg_file_id, body.pcg_file_id]:
        fr = await db.execute(select(MediaFile).where(MediaFile.id == fid))
        f = fr.scalar_one_or_none()
        if not f:
            raise HTTPException(status_code=404, detail=f"文件 {fid} 不存在")
        if str(f.project_id) != body.project_id:
            raise HTTPException(status_code=400, detail=f"文件 {fid} 不属于该项目")

    name = body.name or "模拟生成关联"
    assoc = FileAssociation(
        id=uuid.uuid4(),
        project_id=body.project_id,
        created_by=current_user.id,
        name=name,
        ecg_file_id=body.ecg_file_id,
        pcg_file_id=body.pcg_file_id,
        video_file_id=None,
        pcg_offset=0.0,
        video_offset=0.0,
        notes="由模拟生成自动关联",
    )
    db.add(assoc)
    await db.flush()
    await db.commit()

    # 重新查询以加载关联文件
    stmt = (
        select(FileAssociation)
        .where(FileAssociation.id == assoc.id)
        .options(
            selectinload(FileAssociation.ecg_file),
            selectinload(FileAssociation.pcg_file),
            selectinload(FileAssociation.video_file),
        )
    )
    result2 = await db.execute(stmt)
    assoc = result2.scalar_one()

    return _assoc_to_resp(assoc)
