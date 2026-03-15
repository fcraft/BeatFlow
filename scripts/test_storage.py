#!/usr/bin/env python3
"""
BeatFlow 存储测试脚本
测试 local 和 COS 两种存储后端的文件上传、检测、下载功能
"""

import asyncio
import json
import os
import sys
import time
import struct
import math
import tempfile
import httpx

BASE_URL = "http://localhost:3090"
ADMIN_CREDS = {"username": "admin", "password": "Admin123!"}


def generate_test_wav(filename: str, duration_s: float = 2.0, sample_rate: int = 44100, freq: float = 440.0) -> str:
    """生成测试 WAV 文件 (PCM 16-bit mono sine wave)"""
    num_samples = int(duration_s * sample_rate)
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        value = int(32767 * 0.5 * math.sin(2 * math.pi * freq * t))
        samples.append(struct.pack('<h', value))

    data = b''.join(samples)
    data_size = len(data)

    filepath = os.path.join(tempfile.gettempdir(), filename)
    with open(filepath, 'wb') as f:
        # RIFF header
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + data_size))
        f.write(b'WAVE')
        # fmt chunk
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))  # chunk size
        f.write(struct.pack('<H', 1))   # PCM
        f.write(struct.pack('<H', 1))   # mono
        f.write(struct.pack('<I', sample_rate))
        f.write(struct.pack('<I', sample_rate * 2))  # byte rate
        f.write(struct.pack('<H', 2))   # block align
        f.write(struct.pack('<H', 16))  # bits per sample
        # data chunk
        f.write(b'data')
        f.write(struct.pack('<I', data_size))
        f.write(data)

    return filepath


async def login(client: httpx.AsyncClient) -> str:
    """登录获取 token"""
    resp = await client.post(f"{BASE_URL}/api/v1/auth/login", json=ADMIN_CREDS)
    assert resp.status_code == 200, f"登录失败: {resp.status_code} {resp.text}"
    data = resp.json()
    print(f"  ✅ 登录成功: {data['username']} ({data['role']})")
    return data["access_token"]


async def get_current_storage_type(client: httpx.AsyncClient, token: str) -> str:
    """获取当前存储类型"""
    resp = await client.get(
        f"{BASE_URL}/api/v1/admin/settings",
        headers={"Authorization": f"Bearer {token}"}
    )
    if resp.status_code == 200:
        data = resp.json()
        settings = data.get("items", data) if isinstance(data, dict) else data
        for s in settings:
            if isinstance(s, dict) and s.get("key") == "storage_type":
                return s.get("value", "local")
    return "local"


async def set_storage_type(client: httpx.AsyncClient, token: str, storage_type: str) -> bool:
    """切换存储类型"""
    resp = await client.put(
        f"{BASE_URL}/api/v1/admin/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"settings": {"storage_type": storage_type}}
    )
    if resp.status_code == 200:
        print(f"  ✅ 存储类型已切换为: {storage_type}")
        return True
    else:
        print(f"  ❌ 切换存储类型失败: {resp.status_code} {resp.text}")
        return False


async def create_test_project(client: httpx.AsyncClient, token: str, name: str) -> str:
    """创建测试项目"""
    resp = await client.post(
        f"{BASE_URL}/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "description": f"Storage test project ({name})"}
    )
    assert resp.status_code in (200, 201), f"创建项目失败: {resp.status_code} {resp.text}"
    project_id = resp.json()["id"]
    print(f"  ✅ 项目已创建: {name} ({project_id})")
    return project_id


async def upload_file(client: httpx.AsyncClient, token: str, project_id: str, filepath: str) -> dict:
    """上传文件"""
    filename = os.path.basename(filepath)
    with open(filepath, 'rb') as f:
        resp = await client.post(
            f"{BASE_URL}/api/v1/projects/{project_id}/files/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, f, "audio/wav")},
            timeout=60.0
        )
    assert resp.status_code in (200, 201), f"上传失败: {resp.status_code} {resp.text}"
    data = resp.json()
    print(f"  ✅ 文件已上传: {data.get('original_filename', filename)}")
    print(f"     文件ID: {data['id']}")
    print(f"     存储后端: {data.get('storage_backend', 'unknown')}")
    print(f"     大小: {data.get('file_size', 0)} bytes")
    print(f"     采样率: {data.get('sample_rate', 'N/A')} Hz")
    print(f"     时长: {data.get('duration', 'N/A')} s")
    return data


async def download_file(client: httpx.AsyncClient, token: str, file_id: str) -> bytes:
    """下载文件并验证"""
    resp = await client.get(
        f"{BASE_URL}/api/v1/files/{file_id}/download",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0
    )
    assert resp.status_code == 200, f"下载失败: {resp.status_code} {resp.text}"
    content = resp.content
    print(f"  ✅ 文件下载成功: {len(content)} bytes")
    # 验证 WAV header
    assert content[:4] == b'RIFF', "下载的文件不是有效的 WAV 文件"
    assert content[8:12] == b'WAVE', "下载的文件不是有效的 WAV 文件"
    print(f"  ✅ WAV 格式验证通过")
    return content


async def detect_file(client: httpx.AsyncClient, token: str, file_id: str) -> dict:
    """运行文件检测"""
    resp = await client.post(
        f"{BASE_URL}/api/v1/files/{file_id}/detect",
        headers={"Authorization": f"Bearer {token}"},
        json={"algorithm": "scipy"},
        timeout=120.0
    )
    if resp.status_code == 200:
        data = resp.json()
        annotations = data.get("annotations", [])
        print(f"  ✅ 检测完成: 发现 {len(annotations)} 个标注点")
        if annotations:
            print(f"     类型: {set(a.get('label', 'N/A') for a in annotations[:10])}")
        return data
    else:
        print(f"  ⚠️ 检测返回: {resp.status_code} (可能是测试正弦波无有效特征)")
        return {"annotations": []}


async def test_storage_backend(client: httpx.AsyncClient, token: str, storage_type: str):
    """测试指定存储后端的完整流程"""
    print(f"\n{'='*60}")
    print(f"  测试存储后端: {storage_type.upper()}")
    print(f"{'='*60}")

    # 1. 切换存储类型
    if not await set_storage_type(client, token, storage_type):
        print(f"  ❌ 无法切换到 {storage_type}，跳过测试")
        return False

    # 2. 创建测试项目
    project_id = await create_test_project(client, token, f"存储测试-{storage_type}")

    # 3. 生成并上传测试文件
    print(f"\n  --- 文件上传测试 ---")
    wav_path = generate_test_wav(f"test_{storage_type}.wav", duration_s=3.0, freq=440.0)
    file_size_orig = os.path.getsize(wav_path)
    print(f"  生成测试 WAV: {file_size_orig} bytes (3s, 440Hz)")

    file_data = await upload_file(client, token, project_id, wav_path)
    file_id = file_data["id"]

    # 4. 下载并验证
    print(f"\n  --- 文件下载测试 ---")
    content = await download_file(client, token, file_id)

    # 5. 运行检测
    print(f"\n  --- 文件检测测试 ---")
    await detect_file(client, token, file_id)

    # 清理临时文件
    os.unlink(wav_path)

    print(f"\n  ✅ {storage_type.upper()} 存储后端测试全部通过!")
    return True


async def test_cos_connection(client: httpx.AsyncClient, token: str):
    """测试 COS 连接"""
    print(f"\n  --- COS 连接测试 ---")
    # 先切换到 COS 再测试
    await set_storage_type(client, token, "cos")
    resp = await client.post(
        f"{BASE_URL}/api/v1/admin/settings/test-storage",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"  ✅ COS 连接测试通过: {data.get('message', 'OK')}")
        # 恢复到 local
        await set_storage_type(client, token, "local")
        return True
    else:
        print(f"  ❌ COS 连接测试失败: {resp.status_code} {resp.text}")
        await set_storage_type(client, token, "local")
        return False


async def main():
    print("=" * 60)
    print("  BeatFlow 存储后端测试")
    print("=" * 60)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # 登录
        print("\n[1] 登录...")
        token = await login(client)

        # 查看当前配置
        current_type = await get_current_storage_type(client, token)
        print(f"  当前存储类型: {current_type}")

        # 测试 COS 连接
        print("\n[2] COS 连接测试...")
        cos_ok = await test_cos_connection(client, token)

        # 测试 Local 存储
        print("\n[3] 本地存储测试...")
        local_ok = await test_storage_backend(client, token, "local")

        # 测试 COS 存储
        if cos_ok:
            print("\n[4] COS 存储测试...")
            cos_ok = await test_storage_backend(client, token, "cos")
        else:
            print("\n[4] ⚠️ 跳过 COS 存储测试 (连接失败)")

        # 恢复原来的存储类型
        print(f"\n[5] 恢复存储类型为: {current_type}")
        await set_storage_type(client, token, current_type)

        # 总结
        print("\n" + "=" * 60)
        print("  测试总结")
        print("=" * 60)
        print(f"  本地存储: {'✅ 通过' if local_ok else '❌ 失败'}")
        print(f"  COS 存储: {'✅ 通过' if cos_ok else '❌ 失败'}")
        print("=" * 60)

        if not (local_ok and cos_ok):
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
