#!/usr/bin/env python3
"""
创建临时共享表
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import Base
from app.models import FileShare, FileAssociationShare


async def create_tables():
    """创建所有新表"""
    # 获取数据库 URL - 转换为异步 URL
    db_url = str(settings.DATABASE_URL)
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # 创建异步引擎
    engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
    )

    async with engine.begin() as conn:
        # 创建表
        await conn.run_sync(Base.metadata.create_all)
        print("✅ 表创建成功")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_tables())
