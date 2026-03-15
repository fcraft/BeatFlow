"""应用配置管理"""
from typing import List, Optional
from pydantic import PostgresDsn, field_validator
from pydantic_core.core_schema import FieldValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    # 应用配置
    APP_NAME: str = "ecg-pcg-platform"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "ECG/PCG 心音心电数据管理平台"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 3090
    
    # API配置
    API_V1_STR: str = "/api/v1"
    
    # 数据库配置
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False
    
    # JWT配置
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # 文件存储配置
    STORAGE_TYPE: str = "local"  # local, s3, cos
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 512
    ALLOWED_EXTENSIONS: List[str] = [".wav", ".mp3", ".mp4", ".avi", ".mov"]
    
    # 本地存储配置
    LOCAL_STORAGE_PATH: str = "./storage"
    
    # S3配置
    S3_ENDPOINT_URL: Optional[str] = None
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None
    S3_BUCKET_NAME: Optional[str] = None
    S3_REGION: Optional[str] = None
    
    # COS配置
    COS_SECRET_ID: Optional[str] = None
    COS_SECRET_KEY: Optional[str] = None
    COS_BUCKET_NAME: Optional[str] = None
    COS_REGION: Optional[str] = None
    COS_ENDPOINT: Optional[str] = None
    
    # CORS配置
    CORS_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    ALLOWED_HOSTS: List[str] = ["*"]

    # 静态文件配置
    STATIC_FILES_DIR: Optional[str] = None
    
    # 缓存配置
    CACHE_TTL_SECONDS: int = 300
    
    # 算法配置
    AUTO_ANNOTATION_ENABLED: bool = True
    ANNOTATION_ALGORITHM: str = "librosa_default"
    
    # 安全配置
    PASSWORD_HASH_ALGORITHM: str = "bcrypt"
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD_SECONDS: int = 60
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    @field_validator("STORAGE_TYPE")
    @classmethod
    def validate_storage_type(cls, v):
        valid_types = ["local", "s3", "cos"]
        if v not in valid_types:
            raise ValueError(f"STORAGE_TYPE must be one of {valid_types}")
        return v
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v):
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                # 处理列表字符串
                import ast
                v = ast.literal_eval(v)
            else:
                v = [item.strip() for item in v.split(",")]
        return v
    
    @field_validator("ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def validate_allowed_extensions(cls, v):
        if isinstance(v, str):
            v = [ext.strip() for ext in v.split(",")]
        return v


# 全局配置实例
settings = Settings()


class DevelopmentSettings(Settings):
    """开发环境配置"""
    APP_DEBUG: bool = True
    DATABASE_ECHO: bool = True
    LOG_LEVEL: str = "DEBUG"


class ProductionSettings(Settings):
    """生产环境配置"""
    APP_DEBUG: bool = False
    CORS_ORIGINS: List[str] = [
        "https://ecg-pcg.example.com",
        "https://api.ecg-pcg.example.com",
    ]


def get_settings() -> Settings:
    """获取当前环境配置"""
    env = settings.APP_ENV.lower()
    
    if env == "production":
        return ProductionSettings()
    elif env == "development":
        return DevelopmentSettings()
    else:
        return settings


# 使用环境特定的配置
settings = get_settings()