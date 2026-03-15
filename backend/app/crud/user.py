"""用户CRUD操作"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserFilter
from app.utils.security import get_password_hash, verify_password


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate, UserFilter]):
    """用户CRUD操作类"""

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        return await self.get_by_field(db, "username", username)

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        return await self.get_by_field(db, "email", email)

    async def get_by_uuid(self, db: AsyncSession, user_id: str) -> Optional[User]:
        """通过 UUID 获取用户"""
        stmt = select(self.model).where(self.model.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def authenticate(
        self,
        db: AsyncSession,
        username: Optional[str] = None,
        email: Optional[str] = None,
        password: str = "",
    ) -> Optional[User]:
        """用户认证"""
        if username:
            user = await self.get_by_username(db, username)
        elif email:
            user = await self.get_by_email(db, email)
        else:
            return None

        if not user:
            return None

        if not user.is_active:
            return None

        if not verify_password(password, user.password_hash):
            return None

        return user

    async def create(self, db: AsyncSession, obj_in: UserCreate) -> User:
        """创建用户"""
        obj_data = obj_in.model_dump(exclude_unset=True)
        obj_data["password_hash"] = get_password_hash(obj_data.pop("password"))

        # 设置默认值
        obj_data.setdefault("is_active", True)
        obj_data.setdefault("is_verified", False)
        obj_data.setdefault("role", "member")

        return await super().create(db, obj_data)

    async def update(
        self,
        db: AsyncSession,
        db_obj: User,
        obj_in,
    ) -> User:
        """更新用户"""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        # 如果更新密码，需要哈希
        if "password" in update_data:
            update_data["password_hash"] = get_password_hash(
                update_data.pop("password")
            )

        return await super().update(db, db_obj, update_data)

    async def update_last_login(self, db: AsyncSession, user_id) -> Optional[User]:
        """更新最后登录时间"""
        user = await self.get_by_uuid(db, str(user_id))
        if user:
            user.last_login = datetime.now()
            await db.flush()
            await db.refresh(user)
        return user

    async def check_username_exists(
        self,
        db: AsyncSession,
        username: str,
        exclude_id: Optional[str] = None,
    ) -> bool:
        """检查用户名是否存在"""
        stmt = select(User).where(User.username == username)
        if exclude_id:
            stmt = stmt.where(User.id != exclude_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def check_email_exists(
        self,
        db: AsyncSession,
        email: str,
        exclude_id: Optional[str] = None,
    ) -> bool:
        """检查邮箱是否存在"""
        stmt = select(User).where(User.email == email)
        if exclude_id:
            stmt = stmt.where(User.id != exclude_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def update_role(
        self,
        db: AsyncSession,
        user_id: str,
        role: str,
    ) -> Optional[User]:
        """更新用户角色"""
        user = await self.get_by_uuid(db, user_id)
        if not user:
            return None

        user.role = role
        await db.flush()
        await db.refresh(user)
        return user

    async def set_active_status(
        self,
        db: AsyncSession,
        user_id: str,
        is_active: bool,
    ) -> Optional[User]:
        """设置用户激活状态"""
        user = await self.get_by_uuid(db, user_id)
        if not user:
            return None

        user.is_active = is_active
        await db.flush()
        await db.refresh(user)
        return user

    async def set_verified_status(
        self,
        db: AsyncSession,
        user_id: str,
        is_verified: bool,
    ) -> Optional[User]:
        """设置用户验证状态"""
        user = await self.get_by_uuid(db, user_id)
        if not user:
            return None

        user.is_verified = is_verified
        await db.flush()
        await db.refresh(user)
        return user

    async def get_all_active_users(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
    ) -> list[User]:
        """获取所有活跃用户"""
        return await self.get_multi(
            db,
            skip=skip,
            limit=limit,
            filters=UserFilter(is_active=True),
        )

    async def search_users(
        self,
        db: AsyncSession,
        search_term: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[User]:
        """搜索用户"""
        return await self.search(
            db,
            search_fields=["username", "email", "full_name"],
            search_term=search_term,
            skip=skip,
            limit=limit,
        )


# 全局用户CRUD实例
user_crud = CRUDUser(User)
