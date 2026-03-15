"""标记端点"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentActiveUser, DatabaseSession
from app.models.base import ErrorResponse
import app.models  # noqa: F401 — ensures all ORM relationships are resolved
from app.models.project import Annotation
from app.schemas.project import (
    AnnotationCreate,
    AnnotationUpdate,
    AnnotationResponse,
    AnnotationListResponse,
)

router = APIRouter()


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

    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(annotation, key, value)

    await db.flush()
    await db.refresh(annotation)
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

    await db.delete(annotation)
    await db.commit()
