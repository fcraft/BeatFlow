"""FastAPI 应用主入口"""
import os
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logger import setup_logging
from app.api.api import api_router
from app.core.middleware import (
    RequestIDMiddleware,
    LoggingMiddleware,
    ExceptionHandlerMiddleware,
)
from app.db.session import db_manager, init_db, create_default_admin

# 设置日志
logger = setup_logging()

# 记录服务启动时间（模块加载时即确定）
SERVER_STARTED_AT = datetime.now(timezone.utc)

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.APP_DEBUG else None,
    redoc_url="/redoc" if settings.APP_DEBUG else None,
    openapi_url="/openapi.json" if settings.APP_DEBUG else None,
    default_response_class=JSONResponse,  # 使用JSONResponse作为默认响应类
)

# 添加中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# 添加安全中间件（仅在非通配符模式下）
if settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS != ["*"]:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )

# 添加自定义中间件
app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware, logger=logger)
app.add_middleware(ExceptionHandlerMiddleware, logger=logger)

# 挂载静态文件（如果需要）
if settings.STATIC_FILES_DIR and os.path.isdir(settings.STATIC_FILES_DIR):
    app.mount(
        "/static",
        StaticFiles(directory=settings.STATIC_FILES_DIR),
        name="static",
    )

# 包含API路由
app.include_router(api_router, prefix="/api")

# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查端点"""
    db_status = "healthy" if await db_manager.ping() else "unhealthy"
    
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "database": db_status,
        "started_at": SERVER_STARTED_AT.isoformat(),
    }


@app.get("/")
async def root():
    """根端点"""
    return {
        "message": f"欢迎使用{settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.APP_DEBUG else None,
    }


@app.on_event("startup")
async def startup_event():
    """启动事件"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} in {settings.APP_ENV} mode")
    
    # 初始化数据库
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # 创建默认管理员（如果不存在）
    try:
        await create_default_admin()
    except Exception as e:
        logger.warning(f"Failed to create default admin: {e}")

    # 检查数据库连接
    if not await db_manager.ping():
        logger.error("Database connection failed")
        raise RuntimeError("Database connection failed")
    
    logger.info("Application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """关闭事件"""
    logger.info("Shutting down application...")
    
    # 关闭数据库连接
    await db_manager.close()
    
    logger.info("Application shutdown complete")


# 错误处理
@app.exception_handler(404)
async def not_found_exception_handler(request, exc):
    """404错误处理"""
    return JSONResponse(
        status_code=404,
        content={
            "detail": "资源未找到",
            "code": "NOT_FOUND",
        },
    )


@app.exception_handler(500)
async def internal_exception_handler(request, exc):
    """500错误处理"""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "内部服务器错误",
            "code": "INTERNAL_SERVER_ERROR",
        },
    )


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Running in {'development' if settings.APP_DEBUG else 'production'} mode")
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.APP_DEBUG,
        log_level="info" if settings.APP_DEBUG else "warning",
        access_log=False,  # 我们有自己的日志中间件
    )