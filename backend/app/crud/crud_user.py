from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
import bcrypt
import uuid

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import verify_password, get_password_hash


class CRUDUser:
    """用户CRUD操作"""
    
    @staticmethod
    async def get(db: AsyncSession, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        result = await db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        result = await db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        result = await db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_multi(
        db: AsyncSession, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[User]:
        """获取多个用户"""
        query = select(User)
        
        # 应用过滤器
        if filters:
            for key, value in filters.items():
                if hasattr(User, key):
                    if isinstance(value, list):
                        query = query.where(getattr(User, key).in_(value))
                    else:
                        query = query.where(getattr(User, key) == value)
        
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def create(db: AsyncSession, *, obj_in: UserCreate) -> User:
        """创建新用户"""
        # 检查邮箱是否已存在
        existing_user = await CRUDUser.get_by_email(db, obj_in.email)
        if existing_user:
            raise ValueError("邮箱已存在")
        
        # 检查用户名是否已存在
        existing_username = await CRUDUser.get_by_username(db, obj_in.username)
        if existing_username:
            raise ValueError("用户名已存在")
        
        # 创建新用户
        hashed_password = get_password_hash(obj_in.password)
        user_data = obj_in.dict()
        user_data.pop("password")
        user_data["hashed_password"] = hashed_password
        
        db_user = User(**user_data)
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        return db_user
    
    @staticmethod
    async def update(
        db: AsyncSession, 
        *, 
        db_user: User, 
        obj_in: UserUpdate
    ) -> User:
        """更新用户"""
        update_data = obj_in.dict(exclude_unset=True)
        
        if "password" in update_data:
            hashed_password = get_password_hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password
        
        for field, value in update_data.items():
            if hasattr(db_user, field):
                setattr(db_user, field, value)
        
        await db.commit()
        await db.refresh(db_user)
        return db_user
    
    @staticmethod
    async def remove(db: AsyncSession, *, user_id: str) -> User:
        """删除用户（软删除）"""
        result = await db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        db_user = result.scalar_one()
        
        # 软删除：将用户标记为不活跃
        db_user.is_active = False
        await db.commit()
        await db.refresh(db_user)
        return db_user
    
    @staticmethod
    async def authenticate(
        db: AsyncSession, 
        *, 
        email: str, 
        password: str
    ) -> Optional[User]:
        """验证用户凭据"""
        user = await CRUDUser.get_by_email(db, email)
        if not user:
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
    
    @staticmethod
    async def count(
        db: AsyncSession,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """统计用户数量"""
        query = select(User.id)
        
        if filters:
            for key, value in filters.items():
                if hasattr(User, key):
                    if isinstance(value, list):
                        query = query.where(getattr(User, key).in_(value))
                    else:
                        query = query.where(getattr(User, key) == value)
        
        query = query.where(User.is_active == True)
        result = await db.execute(query)
        return len(result.scalars().all())


user = CRUDUser()