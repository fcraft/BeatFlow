"""虚拟人体档案 CRUD 操作"""
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.virtual_human_profile import VirtualHumanProfile


async def create_profile(
    db: AsyncSession,
    user_id: UUID,
    name: str,
    settings: dict | None = None,
) -> VirtualHumanProfile:
    """创建虚拟人档案。"""
    profile = VirtualHumanProfile(
        user_id=user_id,
        name=name,
        settings=settings or {},
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def get_profile(
    db: AsyncSession,
    profile_id: UUID,
    user_id: UUID | None = None,
) -> Optional[VirtualHumanProfile]:
    """获取单个档案（可选 ownership 校验）。"""
    conditions = [VirtualHumanProfile.id == profile_id]
    if user_id is not None:
        conditions.append(VirtualHumanProfile.user_id == user_id)
    result = await db.execute(
        select(VirtualHumanProfile).where(and_(*conditions))
    )
    return result.scalar_one_or_none()


async def list_profiles(
    db: AsyncSession,
    user_id: UUID,
) -> Sequence[VirtualHumanProfile]:
    """列出用户所有档案。"""
    result = await db.execute(
        select(VirtualHumanProfile)
        .where(VirtualHumanProfile.user_id == user_id)
        .order_by(VirtualHumanProfile.updated_at.desc())
    )
    return result.scalars().all()


async def update_profile(
    db: AsyncSession,
    profile: VirtualHumanProfile,
    name: str | None = None,
    settings: dict | None = None,
    state_snapshot: dict | None = None,
) -> VirtualHumanProfile:
    """更新档案字段。"""
    if name is not None:
        profile.name = name
    if settings is not None:
        profile.settings = settings
    if state_snapshot is not None:
        profile.state_snapshot = state_snapshot
    await db.commit()
    await db.refresh(profile)
    return profile


async def save_snapshot(
    db: AsyncSession,
    profile_id: UUID,
    user_id: UUID,
    snapshot: dict,
) -> bool:
    """保存状态快照（ownership 校验）。"""
    profile = await get_profile(db, profile_id, user_id)
    if not profile:
        return False
    profile.state_snapshot = snapshot
    await db.commit()
    return True


async def delete_profile(
    db: AsyncSession,
    profile_id: UUID,
    user_id: UUID,
) -> bool:
    """删除档案（ownership 校验）。"""
    profile = await get_profile(db, profile_id, user_id)
    if not profile:
        return False
    await db.delete(profile)
    await db.commit()
    return True
