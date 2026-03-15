"""数据库会话管理"""
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy ORM 基础类"""
    pass


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        db_url = str(settings.DATABASE_URL)
        # asyncpg requires postgresql+asyncpg:// scheme
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)

        self.engine = create_async_engine(
            db_url,
            echo=settings.DATABASE_ECHO,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_pre_ping=True,
            future=True,
        )
        self.async_session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话"""
        async with self.async_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def ping(self) -> bool:
        """检查数据库连接"""
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
    
    async def close(self):
        """关闭数据库连接"""
        if self.engine:
            await self.engine.dispose()


# 创建全局数据库管理器实例
db_manager = DatabaseManager()
get_db = db_manager.get_session


async def init_db():
    """初始化数据库（创建表）"""
    # 导入所有模型确保 Base.metadata 包含所有表
    import app.models.user  # noqa: F401
    import app.models.project  # noqa: F401
    import app.models.notification  # noqa: F401
    import app.models.system_setting  # noqa: F401
    import app.models.virtual_human_profile  # noqa: F401

    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db():
    """删除所有表"""
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def create_default_admin():
    """确保系统中至少有一个超级管理员账户"""
    from sqlalchemy import select
    from app.models.user import User
    from app.utils.security import get_password_hash
    import uuid

    async with db_manager.async_session_factory() as session:
        # 检查是否已存在超级管理员
        result = await session.execute(
            select(User).where(User.is_superuser.is_(True))
        )
        if result.scalar_one_or_none():
            return  # 已有管理员，无需创建

        admin = User(
            id=uuid.uuid4(),
            email="admin@beatflow.com",
            username="admin",
            full_name="System Administrator",
            password_hash=get_password_hash("admin123"),
            role="admin",
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()
        print("✅ 默认管理员已创建  用户名: admin  密码: admin123  (请及时修改密码)")