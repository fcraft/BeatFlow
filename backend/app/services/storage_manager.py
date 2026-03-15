"""存储后端工厂 — 从 SystemSetting 表读取配置，构造对应的 StorageBackend"""
from __future__ import annotations

import logging
import time
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.storage import LocalStorageBackend, S3StorageBackend, StorageBackend

logger = logging.getLogger(__name__)

# 内存缓存：(backend_instance, config_hash, timestamp)
_cache: Dict[str, object] = {
    "backend": None,
    "config_hash": None,
    "ts": 0.0,
}
_CACHE_TTL = 60  # seconds


async def _load_settings(db: AsyncSession) -> Dict[str, Optional[str]]:
    """从数据库加载所有系统设置"""
    from app.models.system_setting import SystemSetting

    result = await db.execute(select(SystemSetting))
    rows = result.scalars().all()
    return {row.key: row.value for row in rows}


def _build_backend(cfg: Dict[str, Optional[str]]) -> StorageBackend:
    """根据配置字典构造存储后端"""
    storage_type = (cfg.get("storage_type") or "local").lower()

    if storage_type == "cos" or storage_type == "s3":
        bucket = cfg.get("cos_bucket_name") or cfg.get("s3_bucket_name") or ""
        region = cfg.get("cos_region") or cfg.get("s3_region") or ""
        endpoint = cfg.get("cos_endpoint") or cfg.get("s3_endpoint_url") or ""
        access_key = cfg.get("cos_secret_id") or cfg.get("s3_access_key_id") or ""
        secret_key = cfg.get("cos_secret_key") or cfg.get("s3_secret_access_key") or ""

        if not bucket:
            logger.warning("COS/S3 bucket 未配置，回退到本地存储")
            return LocalStorageBackend(settings.UPLOAD_DIR)

        # COS endpoint 自动补全
        if not endpoint and region:
            endpoint = f"https://cos.{region}.myqcloud.com"

        return S3StorageBackend(
            bucket=bucket,
            region=region or None,
            endpoint_url=endpoint or None,
            access_key_id=access_key or None,
            secret_access_key=secret_key or None,
        )

    # 默认本地
    return LocalStorageBackend(settings.UPLOAD_DIR)


async def get_storage_backend(db: AsyncSession) -> StorageBackend:
    """工厂函数：获取当前存储后端（带 TTL 缓存）"""
    now = time.time()
    if _cache["backend"] is not None and (now - _cache["ts"]) < _CACHE_TTL:  # type: ignore
        return _cache["backend"]  # type: ignore

    cfg = await _load_settings(db)
    config_hash = str(sorted(cfg.items()))

    # 配置未变且未过期，复用旧实例
    if _cache["backend"] is not None and _cache["config_hash"] == config_hash:
        _cache["ts"] = now
        return _cache["backend"]  # type: ignore

    backend = _build_backend(cfg)
    _cache["backend"] = backend
    _cache["config_hash"] = config_hash
    _cache["ts"] = now
    logger.info("Storage backend initialized: %s", type(backend).__name__)
    return backend


def invalidate_storage_cache() -> None:
    """清除缓存，下次调用会重新从 DB 加载配置"""
    _cache["backend"] = None
    _cache["config_hash"] = None
    _cache["ts"] = 0.0


async def get_storage_for_file(db: AsyncSession, media_file) -> StorageBackend:
    """根据文件记录的 storage_backend 字段返回对应的存储后端。

    上传时已将 "local" / "cos" 写入 media_file.storage_backend，
    读取/删除/分析时调用此函数，保证即使全局配置已切换，旧文件仍能正确访问。
    """
    backend_type = getattr(media_file, "storage_backend", "local") or "local"

    if backend_type == "local":
        return LocalStorageBackend(settings.UPLOAD_DIR)

    # COS / S3: 从 DB 读取当前 COS 配置来构造客户端
    cfg = await _load_settings(db)
    return _build_backend({**cfg, "storage_type": "cos"})
