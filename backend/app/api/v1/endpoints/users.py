"""用户端点"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentActiveUser, CurrentAdminUser, DatabaseSession
from app.crud.user import user_crud
from app.models.base import ErrorResponse
from app.schemas.user import UserResponse, UserUpdate, UserListResponse

router = APIRouter()


@router.get(
    "/",
    response_model=UserListResponse,
    responses={
        403: {"model": ErrorResponse, "description": "权限不足"},
    },
)
async def list_users(
    db: DatabaseSession,
    current_user: CurrentAdminUser,
    skip: int = 0,
    limit: int = 20,
) -> UserListResponse:
    """获取用户列表（仅管理员）"""
    users = await user_crud.get_multi(db, skip=skip, limit=limit)
    total = await user_crud.get_count(db)
    page = skip // limit + 1
    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        size=limit,
        has_next=(skip + limit) < total,
    )


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "用户已存在"},
    },
)
async def create_user(
    db: DatabaseSession,
    user_data,
    current_user: CurrentAdminUser,
):
    """创建用户（管理员）"""
    from app.schemas.user import UserCreate
    existing = await user_crud.get_by_email(db, user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册",
        )
    user = await user_crud.create(db, user_data)
    await db.commit()
    return UserResponse.model_validate(user)


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "未认证"},
    },
)
async def get_me(
    current_user: CurrentActiveUser,
) -> UserResponse:
    """获取当前用户信息"""
    return UserResponse.model_validate(current_user)


@router.put(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "未认证"},
    },
)
async def update_me(
    db: DatabaseSession,
    update_data: UserUpdate,
    current_user: CurrentActiveUser,
) -> UserResponse:
    """更新当前用户信息"""
    user = await user_crud.update(db, current_user, update_data)
    await db.commit()
    return UserResponse.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    responses={
        404: {"model": ErrorResponse, "description": "用户不存在"},
    },
)
async def get_user(
    db: DatabaseSession,
    user_id: str,
    current_user: CurrentActiveUser,
) -> UserResponse:
    """获取指定用户信息"""
    user = await user_crud.get_by_uuid(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    return UserResponse.model_validate(user)
