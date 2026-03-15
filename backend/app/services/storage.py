"""统一存储抽象层 — 支持 Local / S3(COS) 后端"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """存储后端抽象基类"""

    @abstractmethod
    async def put(self, key: str, data: bytes) -> None:
        """上传文件"""
        ...

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """下载文件内容"""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """删除文件"""
        ...

    @abstractmethod
    async def get_url(self, key: str, expires: int = 3600) -> str:
        """获取预签名 URL（仅 S3/COS 有意义，本地返回空字符串）"""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查文件是否存在"""
        ...


class LocalStorageBackend(StorageBackend):
    """本地文件系统存储后端"""

    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)

    def _resolve(self, key: str) -> str:
        """将 storage key 解析为本地绝对路径。
        兼容旧的绝对路径 file_path —— 如果 key 是绝对路径且存在则直接返回。
        """
        if os.path.isabs(key) and os.path.exists(key):
            return key
        return os.path.join(self.base_dir, key)

    async def put(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._write, path, data)

    @staticmethod
    def _write(path: str, data: bytes) -> None:
        with open(path, "wb") as f:
            f.write(data)

    async def get(self, key: str) -> bytes:
        path = self._resolve(key)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._read, path)

    @staticmethod
    def _read(path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        if os.path.exists(path):
            os.remove(path)

    async def get_url(self, key: str, expires: int = 3600) -> str:
        # 本地存储不支持 presigned URL
        return ""

    async def exists(self, key: str) -> bool:
        path = self._resolve(key)
        return os.path.exists(path)

    def get_local_path(self, key: str) -> str:
        """直接获取本地路径（仅 LocalStorageBackend 可用）"""
        return self._resolve(key)


class S3StorageBackend(StorageBackend):
    """S3 兼容存储后端（适用于 AWS S3 / Tencent COS / MinIO）"""

    def __init__(
        self,
        bucket: str,
        region: str | None = None,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ):
        import boto3

        self.bucket = bucket
        client_kwargs: dict = {}
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        if region:
            client_kwargs["region_name"] = region

        self._client = boto3.client(
            "s3",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            **client_kwargs,
        )

    async def put(self, key: str, data: bytes) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, lambda: self._client.put_object(Bucket=self.bucket, Key=key, Body=data)
        )

    async def get(self, key: str) -> bytes:
        loop = asyncio.get_running_loop()

        def _download():
            resp = self._client.get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].read()

        return await loop.run_in_executor(None, _download)

    async def delete(self, key: str) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, lambda: self._client.delete_object(Bucket=self.bucket, Key=key)
        )

    async def get_url(self, key: str, expires: int = 3600) -> str:
        loop = asyncio.get_running_loop()

        def _presign():
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires,
            )

        return await loop.run_in_executor(None, _presign)

    async def exists(self, key: str) -> bool:
        loop = asyncio.get_running_loop()

        def _head():
            try:
                self._client.head_object(Bucket=self.bucket, Key=key)
                return True
            except Exception:
                return False

        return await loop.run_in_executor(None, _head)


@asynccontextmanager
async def temp_local_file(storage: StorageBackend, key: str) -> AsyncGenerator[str, None]:
    """上下文管理器：将远程/本地存储中的文件下载到临时目录，返回临时文件路径。
    退出时自动清理临时文件。对于 LocalStorageBackend，直接返回本地路径而不拷贝。
    """
    if isinstance(storage, LocalStorageBackend):
        yield storage.get_local_path(key)
        return

    data = await storage.get(key)
    # 保留原始扩展名
    ext = os.path.splitext(key)[1] or ".tmp"
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    try:
        tmp.write(data)
        tmp.close()
        yield tmp.name
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
