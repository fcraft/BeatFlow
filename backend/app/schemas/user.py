from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
import re


class UserBase(BaseModel):
    """用户基础模式"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=100)

    @validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]{3,50}$', v):
            raise ValueError('用户名只能包含字母、数字、下划线和连字符，长度3-50字符')
        return v


class UserCreate(UserBase):
    """用户创建模式"""
    password: str = Field(..., min_length=8)

    @validator('password')
    def validate_password(cls, v):
        if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d\W]{8,}$', v):
            raise ValueError('密码必须包含大小写字母和数字，至少8位')
        return v


class UserUpdate(BaseModel):
    """用户更新模式"""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, min_length=8)


class UserInDB(UserBase):
    """数据库中的用户模式"""
    id: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserResponse(UserInDB):
    """用户响应模式"""
    pass


class Token(BaseModel):
    """Token模式"""
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Token载荷模式"""
    sub: Optional[str] = None  # 用户ID
    exp: Optional[int] = None  # 过期时间


class LoginCredentials(BaseModel):
    """登录凭据模式"""
    email: EmailStr
    password: str


class RegisterCredentials(UserCreate):
    """注册凭据模式"""
    pass


class AuthResponse(BaseModel):
    """认证响应模式"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserListResponse(BaseModel):
    """用户列表响应模式"""
    items: list[UserResponse]
    total: int
    page: int
    size: int
    has_next: bool


class UserFilter(BaseModel):
    """用户过滤模式"""
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    role: Optional[str] = None


class UserLogin(BaseModel):
    """用户登录模式"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str


class UserWithToken(BaseModel):
    """带 token 的用户响应"""
    id: str
    username: str
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    access_token: str
    refresh_token: str

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Token 响应模式"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    """忘记密码请求"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    """更改密码请求"""
    current_password: str
    new_password: str