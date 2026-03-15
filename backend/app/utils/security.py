"""安全工具函数"""
from datetime import datetime, timedelta
from typing import Optional, Union

import bcrypt
from jose import jwt

from app.core.config import settings
from app.core.logger import logger


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.error(f"Password verification failed: {e}")
        return False


def get_password_hash(password: str) -> str:
    """获取密码哈希值"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(
    subject: Union[str, int],
    expires_delta: Optional[timedelta] = None,
    user_data: Optional[dict] = None,
) -> str:
    """创建访问令牌"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {"sub": str(subject), "exp": expire}
    if user_data:
        to_encode.update(user_data)
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, int],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """创建刷新令牌"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    to_encode = {"sub": str(subject), "exp": expire, "type": "refresh"}
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """解码JWT令牌"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.JWTError as e:
        logger.warning(f"Token decode failed: {e}")
        return None


def generate_api_key(name: str, user_id: int) -> str:
    """生成API Key"""
    import secrets
    import hashlib
    
    # 生成随机密钥
    random_secret = secrets.token_hex(32)
    
    # 创建唯一标识符
    timestamp = datetime.utcnow().isoformat()
    combined = f"{user_id}:{name}:{random_secret}:{timestamp}"
    
    # 生成哈希
    api_key = hashlib.sha256(combined.encode()).hexdigest()
    
    return f"ecg_{user_id}_{api_key[:32]}"


def validate_api_key(api_key: str) -> Optional[dict]:
    """验证API Key格式"""
    if not api_key.startswith("ecg_"):
        return None
    
    try:
        parts = api_key.split("_")
        if len(parts) != 3:
            return None
        
        user_id = int(parts[1])
        key_hash = parts[2]
        
        return {"user_id": user_id, "key_hash": key_hash}
    except (ValueError, IndexError):
        return None


def sanitize_filename(filename: str) -> str:
    """清理文件名，防止路径遍历攻击"""
    import re
    import os
    
    # 移除危险的字符和路径
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    filename = filename.replace("..", "")
    filename = filename.strip()
    
    # 限制文件名长度
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250 - len(ext)] + ext
    
    return filename


def generate_share_code(length: int = 16) -> str:
    """生成 URL-safe 的分享码
    
    Args:
        length: 分享码长度 (default: 16)
        
    Returns:
        URL-safe alphanumeric string (A-Z, a-z, 0-9)
    """
    import secrets
    import string
    
    # URL-safe alphabet
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))