"""标记端点"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from app.core.deps import CurrentActiveUser, DatabaseSession
from app.models.base import ErrorResponse
import app.models  # noqa: F401 — ensures all ORM relationships are resolved
from app.models.project import Annotation, OperationLog
from app.schemas.project import (
    AnnotationCreate,
    AnnotationUpdate,
    AnnotationResponse,
    AnnotationListResponse,
)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# 审核后接受标注
# ─────────────────────────────────────────────────────────────────────────────


class AnnotationAcceptItem(BaseModel):
    annotation_type: str
    start_time: float
    end_time: float
    confidence: Optional[float] = None
    label: str = ""


class AnnotationAcceptRequest(BaseModel):
    file_id: str
    items: List[AnnotationAcceptItem]


@router.post(
    "/accept",
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse, "description": "文件不存在"},
    },
)
async def accept_annotations(
    db: DatabaseSession,
    body: AnnotationAcceptRequest,
    current_user: CurrentActiveUser,
):
    """接受检测预览中的标注：按时间范围合并，覆盖区域内旧标注并插入新标注。

    配合 POST /api/v1/files/{id}/detect/preview 使用。
    用户审核预览结果后，将接受的标注列表提交到此端点。

    只删除与接受标注时间范围重叠的旧 auto 标注，
    区域外的已有标注不受影响（保护区域重检测场景）。
    """
    import uuid

    from app.models.project import MediaFile
    from sqlalchemy import and_

    result = await db.execute(select(MediaFile).where(MediaFile.id == body.file_id))
    media_file = result.scalar_one_or_none()
    if not media_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    # 按接受标注的时间区间删除重叠的旧 auto 标注（合并而非全量替换）
    if body.items:
        new_min = min(item.start_time for item in body.items) - 0.1
        new_max = max(item.end_time for item in body.items) + 0.1
        del_stmt = select(Annotation).where(
            Annotation.file_id == body.file_id,
            Annotation.source == "auto",
            Annotation.end_time > new_min,
            Annotation.start_time < new_max,
        )
    else:
        # 空列表：清空所有 auto 标注
        del_stmt = select(Annotation).where(
            Annotation.file_id == body.file_id,
            Annotation.source == "auto",
        )
    old = (await db.execute(del_stmt)).scalars().all()
    old_data = [o.to_dict() for o in old]
    for o in old:
        await db.delete(o)

    # 插入新标注
    created = []
    for item in body.items:
        ann = Annotation(
            file_id=uuid.UUID(body.file_id),
            user_id=current_user.id,
            annotation_type=item.annotation_type,
            start_time=item.start_time,
            end_time=item.end_time,
            confidence=item.confidence,
            label=item.label or item.annotation_type.upper(),
            source="auto",
        )
        db.add(ann)
        created.append(ann)

    await db.flush()
    for ann in created:
        await db.refresh(ann)

    # 操作日志
    new_data = [a.to_dict() for a in created]
    log = OperationLog(
        file_id=uuid.UUID(body.file_id),
        user_id=current_user.id,
        operation_type="accept",
        description=f"接受了 {len(created)} 个标注，清除了 {len(old_data)} 个旧自动标注",
        details={
            "old_annotations": old_data,
            "new_annotations": new_data,
            "accepted_count": len(created),
            "deleted_count": len(old_data),
        },
    )
    db.add(log)

    await db.commit()

    return {
        "file_id": body.file_id,
        "accepted_count": len(created),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 批量操作
# ─────────────────────────────────────────────────────────────────────────────


class BatchAnnotationUpdate(BaseModel):
    ids: List[str]
    updates: Optional[dict] = None  # { annotation_type?, label?, confidence? }
    action: Optional[str] = None     # "delete"


@router.patch(
    "/batch",
    responses={
        400: {"model": ErrorResponse, "description": "参数无效"},
        403: {"model": ErrorResponse, "description": "无修改权限"},
    },
)
async def batch_annotations(
    db: DatabaseSession,
    body: BatchAnnotationUpdate,
    current_user: CurrentActiveUser,
):
    """批量更新或删除标注。

    - 更新: `{ ids: [...], updates: { annotation_type?, label?, confidence? } }`
    - 删除: `{ ids: [...], action: "delete" }`
    """
    if not body.ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids 不能为空")

    if body.action not in (None, "delete"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的操作: {body.action}")

    result = await db.execute(select(Annotation).where(Annotation.id.in_(body.ids)))
    annotations = list(result.scalars().all())

    # 权限校验
    for ann in annotations:
        if str(ann.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"只能操作自己创建的标记 (id={ann.id})",
            )

    if body.action == "delete":
        snapshots = [a.to_dict() for a in annotations]
        for ann in annotations:
            await db.delete(ann)

        log = OperationLog(
            file_id=annotations[0].file_id,
            user_id=current_user.id,
            operation_type="batch_delete",
            description=f"批量删除了 {len(annotations)} 个标注",
            details={"deleted_annotations": snapshots, "count": len(snapshots)},
        )
        db.add(log)

        await db.commit()
        return {"deleted_count": len(annotations)}

    if body.updates:
        for ann in annotations:
            for key, value in body.updates.items():
                if hasattr(ann, key) and value is not None:
                    setattr(ann, key, value)
        await db.commit()

        # 刷新后重新查询
        result = await db.execute(select(Annotation).where(Annotation.id.in_(body.ids)))
        updated = list(result.scalars().all())
        return {
            "updated_count": len(updated),
            "items": [AnnotationResponse.model_validate(a).model_dump() for a in updated],
        }

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="需要提供 updates 或 action")


# ─────────────────────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/",
    response_model=AnnotationListResponse,
)
async def list_annotations(
    db: DatabaseSession,
    current_user: CurrentActiveUser,
    file_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> AnnotationListResponse:
    """获取标记列表"""
    stmt = select(Annotation)
    if file_id:
        stmt = stmt.where(Annotation.file_id == file_id)

    result = await db.execute(stmt.offset(skip).limit(limit))
    annotations = list(result.scalars().all())

    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(Annotation)
    if file_id:
        count_stmt = count_stmt.where(Annotation.file_id == file_id)
    total = (await db.execute(count_stmt)).scalar_one()

    page = skip // limit + 1
    return AnnotationListResponse(
        items=[AnnotationResponse.model_validate(a) for a in annotations],
        total=total,
        page=page,
        size=limit,
        has_next=(skip + limit) < total,
    )


@router.post(
    "/",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    db: DatabaseSession,
    annotation_data: AnnotationCreate,
    current_user: CurrentActiveUser,
) -> AnnotationResponse:
    """创建标记"""
    import uuid
    annotation = Annotation(
        file_id=uuid.UUID(annotation_data.file_id),
        user_id=current_user.id,
        annotation_type=annotation_data.annotation_type.value,
        start_time=annotation_data.start_time,
        end_time=annotation_data.end_time,
        label=annotation_data.label,
        confidence=annotation_data.confidence,
        annotation_metadata=annotation_data.metadata,
    )
    db.add(annotation)
    await db.flush()
    await db.refresh(annotation)

    # 操作日志
    log = OperationLog(
        file_id=annotation.file_id,
        user_id=current_user.id,
        operation_type="create",
        description=f"创建了标注 {annotation.label} ({annotation.annotation_type})",
        details={"created_annotation": annotation.to_dict()},
    )
    db.add(log)

    await db.commit()

    return AnnotationResponse.model_validate(annotation)


@router.put(
    "/{annotation_id}",
    response_model=AnnotationResponse,
    responses={
        404: {"model": ErrorResponse, "description": "标记不存在"},
        403: {"model": ErrorResponse, "description": "无修改权限"},
    },
)
async def update_annotation(
    db: DatabaseSession,
    annotation_id: str,
    update_data: AnnotationUpdate,
    current_user: CurrentActiveUser,
) -> AnnotationResponse:
    """更新标记"""
    result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标记不存在")

    if str(annotation.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能修改自己创建的标记")

    old_snapshot = annotation.to_dict()
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(annotation, key, value)

    await db.flush()
    await db.refresh(annotation)

    # 操作日志
    log = OperationLog(
        file_id=annotation.file_id,
        user_id=current_user.id,
        operation_type="update",
        description=f"更新了标注 {annotation.label}",
        details={"old_values": old_snapshot, "new_values": annotation.to_dict()},
    )
    db.add(log)

    await db.commit()

    return AnnotationResponse.model_validate(annotation)


@router.delete(
    "/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse, "description": "标记不存在"},
        403: {"model": ErrorResponse, "description": "无删除权限"},
    },
)
async def delete_annotation(
    db: DatabaseSession,
    annotation_id: str,
    current_user: CurrentActiveUser,
) -> None:
    """删除标记"""
    result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标记不存在")

    if str(annotation.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能删除自己创建的标记")

    snapshot = annotation.to_dict()
    await db.delete(annotation)

    # 操作日志
    log = OperationLog(
        file_id=annotation.file_id,
        user_id=current_user.id,
        operation_type="delete",
        description=f"删除了标注 {snapshot['label']} ({snapshot['annotation_type']})",
        details={"deleted_annotation": snapshot},
    )
    db.add(log)

    await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# 操作日志查询与撤销
# ─────────────────────────────────────────────────────────────────────────────


class OperationLogItem(BaseModel):
    id: str
    file_id: str
    user_id: str
    operation_type: str
    description: str
    details: dict
    is_undone: bool
    undone_at: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}

    @field_validator("id", "file_id", "user_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v

    @field_validator("created_at", "undone_at", mode="before")
    @classmethod
    def coerce_datetime(cls, v):
        return v.isoformat() if v is not None else v


class OperationLogListResponse(BaseModel):
    items: List[OperationLogItem]
    total: int


class UndoResponse(BaseModel):
    success: bool
    recreated_count: int
    deleted_count: int
    message: str


@router.get(
    "/operation-logs",
    response_model=OperationLogListResponse,
    responses={400: {"model": ErrorResponse, "description": "file_id 参数必填"}},
)
async def list_operation_logs(
    db: DatabaseSession,
    current_user: CurrentActiveUser,
    file_id: str,
    limit: int = 50,
) -> OperationLogListResponse:
    """查询某个文件的操作日志（按时间倒序）"""
    from sqlalchemy import func

    stmt = (
        select(OperationLog)
        .where(OperationLog.file_id == file_id)
        .order_by(OperationLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    logs = list(result.scalars().all())

    count_stmt = (
        select(func.count())
        .select_from(OperationLog)
        .where(OperationLog.file_id == file_id)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    return OperationLogListResponse(
        items=[OperationLogItem.model_validate(log) for log in logs],
        total=total,
    )


@router.post(
    "/operation-logs/{log_id}/undo",
    response_model=UndoResponse,
    responses={
        404: {"model": ErrorResponse, "description": "日志不存在"},
        400: {"model": ErrorResponse, "description": "无法撤销"},
    },
)
async def undo_operation(
    db: DatabaseSession,
    log_id: str,
    current_user: CurrentActiveUser,
) -> UndoResponse:
    """撤销一个操作日志记录的操作。

    支持撤销: accept, delete, batch_delete
    不支持撤销: create, update (仅作审计记录)
    """
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz

    from app.models.project import MediaFile

    result = await db.execute(select(OperationLog).where(OperationLog.id == log_id))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="操作日志不存在")

    # 校验文件存在
    file_result = await db.execute(select(MediaFile).where(MediaFile.id == log.file_id))
    if not file_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联文件不存在")

    if log.is_undone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该操作已被撤销，不能重复撤销")

    if log.operation_type not in ("accept", "delete", "batch_delete"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持撤销 {log.operation_type} 类型的操作",
        )

    details = log.details or {}
    recreated_count = 0
    deleted_count = 0

    if log.operation_type == "accept":
        # 删除 accept 时创建的标注
        new_ids = [item["id"] for item in details.get("new_annotations", [])]
        if new_ids:
            del_result = await db.execute(select(Annotation).where(Annotation.id.in_(new_ids)))
            for ann in del_result.scalars().all():
                await db.delete(ann)
                deleted_count += 1

        # 重建旧标注
        for item in details.get("old_annotations", []):
            ann = Annotation(
                file_id=_uuid.UUID(item["file_id"]),
                user_id=_uuid.UUID(item["user_id"]),
                annotation_type=item["annotation_type"],
                start_time=item["start_time"],
                end_time=item["end_time"],
                label=item["label"],
                confidence=item["confidence"],
                source=item.get("source", "auto"),
                annotation_metadata=item.get("metadata", {}),
            )
            db.add(ann)
            recreated_count += 1

    elif log.operation_type == "delete":
        item = details.get("deleted_annotation", {})
        if item:
            ann = Annotation(
                file_id=_uuid.UUID(item["file_id"]),
                user_id=_uuid.UUID(item["user_id"]),
                annotation_type=item["annotation_type"],
                start_time=item["start_time"],
                end_time=item["end_time"],
                label=item["label"],
                confidence=item["confidence"],
                source=item.get("source", "manual"),
                annotation_metadata=item.get("metadata", {}),
            )
            db.add(ann)
            recreated_count = 1

    elif log.operation_type == "batch_delete":
        for item in details.get("deleted_annotations", []):
            ann = Annotation(
                file_id=_uuid.UUID(item["file_id"]),
                user_id=_uuid.UUID(item["user_id"]),
                annotation_type=item["annotation_type"],
                start_time=item["start_time"],
                end_time=item["end_time"],
                label=item["label"],
                confidence=item["confidence"],
                source=item.get("source", "manual"),
                annotation_metadata=item.get("metadata", {}),
            )
            db.add(ann)
            recreated_count += 1

    await db.flush()

    # 标记日志为已撤销
    log.is_undone = True
    log.undone_at = _dt.now(_tz.utc)

    # 记录撤销操作本身
    undo_log = OperationLog(
        file_id=log.file_id,
        user_id=current_user.id,
        operation_type="undo",
        description=f"撤销了操作: {log.description}",
        details={
            "undone_log_id": str(log.id),
            "recreated_count": recreated_count,
            "deleted_count": deleted_count,
            "original_operation": log.operation_type,
        },
    )
    db.add(undo_log)

    await db.commit()

    return UndoResponse(
        success=True,
        recreated_count=recreated_count,
        deleted_count=deleted_count,
        message=f"已撤销: {log.description}",
    )
