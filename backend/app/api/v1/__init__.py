"""API v1版本路由"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, projects, files, annotations, community, simulate, associations, notifications, admin, virtual_human, virtual_human_profiles, shares

api_router = APIRouter()

# 注册所有端点
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户"])
api_router.include_router(projects.router, prefix="/projects", tags=["项目"])
api_router.include_router(files.router, prefix="/files", tags=["文件"])
api_router.include_router(annotations.router, prefix="/annotations", tags=["标记"])
api_router.include_router(community.router, prefix="/community", tags=["社区"])
api_router.include_router(simulate.router, prefix="/simulate", tags=["模拟生成"])
api_router.include_router(associations.router, prefix="/associations", tags=["文件关联"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["通知"])
api_router.include_router(admin.router, prefix="/admin", tags=["管理后台"])
api_router.include_router(virtual_human.router, tags=["虚拟人体"])
api_router.include_router(virtual_human_profiles.router, prefix="/virtual-human", tags=["虚拟人体档案"])
api_router.include_router(shares.router)
