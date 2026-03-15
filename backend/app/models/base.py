"""Pydantic 基础模型"""
from datetime import datetime
from typing import Any, Dict, Generic, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelCaseModel(BaseModel):
    """支持 camelCase 的模型基类"""
    
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        arbitrary_types_allowed=True,
    )


class TimestampMixin(BaseModel):
    """时间戳混入"""
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UUIDMixin(BaseModel):
    """UUID混入"""
    
    uuid: UUID


class BaseResponse(CamelCaseModel, TimestampMixin):
    """基础响应模型"""
    
    id: int


class Pagination(BaseModel):
    """分页参数"""
    
    page: int = Field(default=1, ge=1, description="页码")
    limit: int = Field(default=20, ge=1, le=100, description="每页数量")
    total: Optional[int] = Field(default=None, description="总数量")
    total_pages: Optional[int] = Field(default=None, description="总页数")


class PaginatedResponse(CamelCaseModel, Generic[T]):
    """分页响应模型"""
    
    items: list[T]
    pagination: Pagination
    
    @classmethod
    def from_list(
        cls,
        items: list[T],
        total: int,
        page: int,
        limit: int,
    ) -> "PaginatedResponse[T]":
        """从列表创建分页响应"""
        
        total_pages = (total + limit - 1) // limit if total > 0 else 1
        
        return cls(
            items=items,
            pagination=Pagination(
                page=page,
                limit=limit,
                total=total,
                total_pages=total_pages,
            ),
        )


class ErrorResponse(BaseModel):
    """错误响应模型"""
    
    detail: str
    code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "发生了一个错误",
                "code": "INTERNAL_ERROR",
                "metadata": {"field": "example"},
            }
        }
    )


class ValidationErrorDetail(BaseModel):
    """验证错误详情"""
    
    field: str
    message: str
    value: Optional[Any] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "field": "username",
                "message": "用户名已存在",
                "value": "test_user",
            }
        }
    )


class ValidationErrorResponse(ErrorResponse):
    """验证错误响应"""
    
    errors: list[ValidationErrorDetail]
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "验证失败",
                "errors": [
                    {
                        "field": "username",
                        "message": "用户名已存在",
                        "value": "test_user",
                    }
                ],
            }
        }
    )