"""基础CRUD操作"""
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import func

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)
FilterType = TypeVar("FilterType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType, FilterType]):
    """基础CRUD类，提供通用数据库操作"""
    
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    async def get(
        self,
        db: AsyncSession,
        id: Optional[Union[str, UUID]] = None,
        **filters,
    ) -> Optional[ModelType]:
        """
        获取单个记录

        Args:
            db: 数据库会话
            id: 主键ID（UUID字符串或UUID对象）
            **filters: 其他过滤条件

        Returns:
            模型实例或None
        """
        if id is not None:
            filter_by = {"id": id}
        else:
            filter_by = filters

        if not filter_by:
            raise ValueError("必须提供ID或过滤条件")

        stmt = select(self.model).filter_by(**filter_by)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[FilterType] = None,
        order_by: Optional[str] = None,
        **kwargs,
    ) -> List[ModelType]:
        """
        获取多个记录
        
        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 限制记录数
            filters: 过滤条件
            order_by: 排序字段
            **kwargs: 其他过滤条件
        
        Returns:
            模型实例列表
        """
        stmt = select(self.model)
        
        # 应用过滤条件
        if filters:
            filter_dict = filters.model_dump(exclude_none=True)
            for key, value in filter_dict.items():
                stmt = stmt.where(getattr(self.model, key) == value)
        
        # 应用额外过滤条件
        for key, value in kwargs.items():
            if hasattr(self.model, key) and value is not None:
                stmt = stmt.where(getattr(self.model, key) == value)
        
        # 应用排序
        if order_by:
            if order_by.startswith("-"):
                field = order_by[1:]
                stmt = stmt.order_by(getattr(self.model, field).desc())
            else:
                stmt = stmt.order_by(getattr(self.model, order_by))
        else:
            stmt = stmt.order_by(self.model.id.desc())
        
        # 应用分页
        stmt = stmt.offset(skip).limit(limit)
        
        result = await db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_count(
        self,
        db: AsyncSession,
        filters: Optional[FilterType] = None,
        **kwargs,
    ) -> int:
        """
        获取记录总数
        
        Args:
            db: 数据库会话
            filters: 过滤条件
            **kwargs: 其他过滤条件
        
        Returns:
            记录总数
        """
        stmt = select(func.count()).select_from(self.model)
        
        # 应用过滤条件
        if filters:
            filter_dict = filters.model_dump(exclude_none=True)
            for key, value in filter_dict.items():
                stmt = stmt.where(getattr(self.model, key) == value)
        
        # 应用额外过滤条件
        for key, value in kwargs.items():
            if hasattr(self.model, key) and value is not None:
                stmt = stmt.where(getattr(self.model, key) == value)
        
        result = await db.execute(stmt)
        return result.scalar_one()
    
    async def create(
        self,
        db: AsyncSession,
        obj_in: Union[CreateSchemaType, Dict[str, Any]],
    ) -> ModelType:
        """
        创建新记录
        
        Args:
            db: 数据库会话
            obj_in: 创建数据
        
        Returns:
            创建的模型实例
        """
        if isinstance(obj_in, dict):
            obj_data = obj_in
        else:
            obj_data = obj_in.model_dump(exclude_unset=True)
        
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj
    
    async def update(
        self,
        db: AsyncSession,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]],
    ) -> ModelType:
        """
        更新记录
        
        Args:
            db: 数据库会话
            db_obj: 数据库对象
            obj_in: 更新数据
        
        Returns:
            更新后的模型实例
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        
        # 手动更新每个字段
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        await db.flush()
        await db.refresh(db_obj)
        return db_obj
    
    async def patch(
        self,
        db: AsyncSession,
        id: Union[str, UUID],
        obj_in: Union[UpdateSchemaType, Dict[str, Any]],
    ) -> Optional[ModelType]:
        """
        通过ID更新记录
        
        Args:
            db: 数据库会话
            id: 记录ID
            obj_in: 更新数据
        
        Returns:
            更新后的模型实例或None
        """
        db_obj = await self.get(db, id=id)
        if not db_obj:
            return None
        
        return await self.update(db, db_obj, obj_in)
    
    async def delete(self, db: AsyncSession, id: Union[str, UUID]) -> bool:
        """
        删除记录
        
        Args:
            db: 数据库会话
            id: 记录ID
        
        Returns:
            是否成功删除
        """
        db_obj = await self.get(db, id=id)
        if not db_obj:
            return False
        
        await db.delete(db_obj)
        await db.flush()
        return True
    
    async def delete_multi(
        self,
        db: AsyncSession,
        ids: List[Union[str, UUID]],
    ) -> int:
        """
        批量删除记录
        
        Args:
            db: 数据库会话
            ids: 记录ID列表
        
        Returns:
            删除的记录数
        """
        stmt = delete(self.model).where(self.model.id.in_(ids))
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount
    
    async def exists(
        self,
        db: AsyncSession,
        id: Optional[Union[str, UUID]] = None,
        **filters,
    ) -> bool:
        """
        检查记录是否存在
        
        Args:
            db: 数据库会话
            id: 记录ID
            **filters: 过滤条件
        
        Returns:
            是否存在
        """
        db_obj = await self.get(db, id=id, **filters)
        return db_obj is not None
    
    async def create_or_update(
        self,
        db: AsyncSession,
        obj_in: Union[CreateSchemaType, Dict[str, Any]],
        id: Optional[Union[str, UUID]] = None,
        **filters,
    ) -> ModelType:
        """
        创建或更新记录
        
        Args:
            db: 数据库会话
            obj_in: 数据
            id: 记录ID（用于更新）
            **filters: 过滤条件（用于查找）
        
        Returns:
            创建或更新后的模型实例
        """
        if id is not None:
            db_obj = await self.get(db, id=id)
        elif filters:
            db_obj = await self.get(db, **filters)
        else:
            db_obj = None
        
        if db_obj:
            return await self.update(db, db_obj, obj_in)
        else:
            return await self.create(db, obj_in)
    
    async def get_by_field(
        self,
        db: AsyncSession,
        field: str,
        value: Any,
    ) -> Optional[ModelType]:
        """
        通过字段值获取记录
        
        Args:
            db: 数据库会话
            field: 字段名
            value: 字段值
        
        Returns:
            模型实例或None
        """
        if not hasattr(self.model, field):
            raise ValueError(f"字段 '{field}' 不存在于模型 {self.model.__name__}")
        
        stmt = select(self.model).where(getattr(self.model, field) == value)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def search(
        self,
        db: AsyncSession,
        *,
        search_fields: List[str],
        search_term: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ModelType]:
        """
        搜索记录
        
        Args:
            db: 数据库会话
            search_fields: 搜索字段列表
            search_term: 搜索关键词
            skip: 跳过记录数
            limit: 限制记录数
        
        Returns:
            模型实例列表
        """
        stmt = select(self.model)
        
        # 构建搜索条件
        from sqlalchemy import or_
        
        conditions = []
        for field in search_fields:
            if hasattr(self.model, field):
                conditions.append(
                    getattr(self.model, field).ilike(f"%{search_term}%")
                )
        
        if conditions:
            stmt = stmt.where(or_(*conditions))
        
        stmt = stmt.order_by(self.model.id.desc())
        stmt = stmt.offset(skip).limit(limit)
        
        result = await db.execute(stmt)
        return list(result.scalars().all())