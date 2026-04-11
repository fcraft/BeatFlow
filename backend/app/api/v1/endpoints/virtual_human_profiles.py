"""
虚拟人体档案 REST API

CRUD 端点用于管理用户的虚拟人档案。
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import virtual_human_profile as crud
from app.db.session import get_db
from app.schemas.virtual_human import (
    ProfileCreate,
    ProfileListItem,
    ProfileResponse,
    ProfileUpdate,
)
from app.utils.security import decode_token
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

router = APIRouter()
security = HTTPBearer()


async def _get_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UUID:
    """从 JWT 提取 user_id。"""
    payload = decode_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return UUID(payload["sub"])


@router.post("/profiles", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    body: ProfileCreate,
    user_id: UUID = Depends(_get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """创建虚拟人档案。"""
    profile = await crud.create_profile(db, user_id, body.name, body.settings)
    return profile


@router.get("/profiles", response_model=list[ProfileListItem])
async def list_profiles(
    user_id: UUID = Depends(_get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户所有虚拟人档案。"""
    profiles = await crud.list_profiles(db, user_id)
    items = []
    for p in profiles:
        snap = p.state_snapshot or {}
        items.append(ProfileListItem(
            id=p.id,
            name=p.name,
            is_active=p.is_active,
            heart_rate=snap.get("heart_rate"),
            rhythm=snap.get("rhythm"),
            systolic_bp=snap.get("systolic_bp"),
            diastolic_bp=snap.get("diastolic_bp"),
            spo2=snap.get("spo2"),
            temperature=snap.get("temperature"),
            has_snapshot=bool(p.state_snapshot),
            created_at=p.created_at,
            updated_at=p.updated_at,
        ))
    return items


@router.get("/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: UUID,
    user_id: UUID = Depends(_get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取单个档案详情。"""
    profile = await crud.get_profile(db, profile_id, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.patch("/profiles/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: UUID,
    body: ProfileUpdate,
    user_id: UUID = Depends(_get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """修改档案名称/设置。"""
    profile = await crud.get_profile(db, profile_id, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    updated = await crud.update_profile(
        db, profile,
        name=body.name,
        settings=body.settings,
    )
    return updated


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: UUID,
    user_id: UUID = Depends(_get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """删除档案。"""
    ok = await crud.delete_profile(db, profile_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Profile not found")
