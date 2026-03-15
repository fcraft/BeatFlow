"""认证端点"""
from typing import Annotated, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.deps import CurrentUser, DatabaseSession
from app.crud.user import user_crud
from app.models.base import ErrorResponse
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserWithToken,
    TokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    UserResponse,
)
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    get_password_hash,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=Dict,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "用户已存在"},
    },
)
async def register(
    db: DatabaseSession,
    user_data: UserCreate,
) -> Dict:
    """
    用户注册
    """
    # 检查邮箱是否已存在
    existing_email = await user_crud.get_by_email(db, user_data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册",
        )

    # 检查用户名是否已存在
    existing_username = await user_crud.get_by_username(db, user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名已被使用",
        )

    # 创建用户
    user = await user_crud.create(db, user_data)
    await db.commit()

    return {
        "message": "注册成功",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
        },
    }


@router.post(
    "/login",
    response_model=UserWithToken,
    responses={
        401: {"model": ErrorResponse, "description": "认证失败"},
        403: {"model": ErrorResponse, "description": "用户被禁用"},
    },
)
async def login(
    db: DatabaseSession,
    login_data: UserLogin,
) -> UserWithToken:
    """
    用户登录

    支持用户名或邮箱登录
    """
    # 根据提供的凭证类型进行认证
    if login_data.username:
        user = await user_crud.authenticate(
            db,
            username=login_data.username,
            password=login_data.password,
        )
    else:
        user = await user_crud.authenticate(
            db,
            email=login_data.email,
            password=login_data.password,
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名/邮箱或密码错误",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    # 更新最后登录时间
    await user_crud.update_last_login(db, user.id)
    await db.commit()

    # 创建令牌
    access_token = create_access_token(
        subject=str(user.id),
        user_data={
            "username": user.username,
            "role": user.role,
        },
    )
    refresh_token = create_refresh_token(subject=str(user.id))

    return UserWithToken(
        id=str(user.id),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        last_login=user.last_login,
        created_at=user.created_at,
        updated_at=user.updated_at,
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post(
    "/token",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "认证失败"},
    },
)
async def oauth2_login(
    db: DatabaseSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    """
    OAuth2 兼容的令牌获取端点
    """
    # 根据用户名（可能是邮箱）进行认证
    user = await user_crud.authenticate(
        db,
        username=form_data.username,
        password=form_data.password,
    )

    if not user:
        # 尝试作为邮箱认证
        user = await user_crud.authenticate(
            db,
            email=form_data.username,
            password=form_data.password,
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名/邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    # 更新最后登录时间
    await user_crud.update_last_login(db, user.id)
    await db.commit()

    # 创建令牌
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "刷新令牌无效"},
    },
)
async def refresh_token(
    db: DatabaseSession,
    refresh_token: str,
) -> TokenResponse:
    """
    刷新访问令牌

    使用刷新令牌获取新的访问令牌
    """
    from app.utils.security import decode_token

    # 解码刷新令牌
    payload = decode_token(refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌无效",
        )

    # 检查令牌类型
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="不是刷新令牌",
        )

    # 获取用户
    user_id = payload.get("sub")
    user = await user_crud.get_by_uuid(db, user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )

    # 创建新的访问令牌
    access_token = create_access_token(subject=str(user.id))

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "未认证"},
    },
)
async def logout(
    current_user: CurrentUser,
) -> None:
    """
    用户登出

    注意：由于JWT是无状态的，实际需要在客户端删除令牌
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证",
        )
    # 无状态JWT，客户端需要删除令牌
    return


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": ErrorResponse, "description": "邮箱未注册"},
    },
)
async def forgot_password(
    db: DatabaseSession,
    forgot_data: ForgotPasswordRequest,
) -> Dict:
    """
    忘记密码

    发送密码重置邮件给用户
    """
    # 检查邮箱是否存在
    user = await user_crud.get_by_email(db, forgot_data.email)
    if not user:
        # 出于安全考虑，不返回具体错误信息
        return {"message": "如果邮箱已注册，将收到重置邮件"}

    if not user.is_active:
        return {"message": "如果邮箱已注册，将收到重置邮件"}

    # TODO: 实际项目中应发送密码重置邮件
    return {"message": "如果邮箱已注册，将收到重置邮件"}


@router.post(
    "/reset-password",
    response_model=Dict,
    responses={
        400: {"model": ErrorResponse, "description": "令牌无效或已过期"},
        404: {"model": ErrorResponse, "description": "用户不存在"},
    },
)
async def reset_password(
    db: DatabaseSession,
    reset_data: ResetPasswordRequest,
) -> Dict:
    """
    重置密码

    使用重置令牌重置密码
    """
    from app.utils.security import decode_token

    payload = decode_token(reset_data.token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重置令牌无效或已过期",
        )

    user_id = payload.get("sub")
    user = await user_crud.get_by_uuid(db, user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 更新密码
    await user_crud.update(
        db,
        user,
        {"password": reset_data.new_password},
    )
    await db.commit()

    return {"message": "密码重置成功"}


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        400: {"model": ErrorResponse, "description": "当前密码错误"},
        401: {"model": ErrorResponse, "description": "未认证"},
    },
)
async def change_password(
    db: DatabaseSession,
    password_data: ChangePasswordRequest,
    current_user: CurrentUser,
) -> None:
    """
    更改密码

    用户更改自己的密码
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证",
        )

    # 验证当前密码
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码错误",
        )

    # 更新密码
    await user_crud.update(
        db,
        current_user,
        {"password": password_data.new_password},
    )
    await db.commit()


@router.get(
    "/me",
    response_model=Dict,
    responses={
        401: {"model": ErrorResponse, "description": "未认证"},
    },
)
async def get_auth_status(
    current_user: CurrentUser,
) -> Dict:
    """
    获取当前认证状态
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证",
        )

    return {
        "status": "authenticated",
        "user_id": str(current_user.id),
        "username": current_user.username,
        "role": current_user.role,
    }
