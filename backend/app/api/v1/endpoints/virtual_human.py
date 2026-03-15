"""
虚拟人体 WebSocket 端点

ws://host/api/v1/ws/virtual-human?token=xxx&profile_id=xxx

协议：
  Server → Client:
    {"type":"init", "vitals":{...}, "interactions":[...], "profile":{...}}  (首帧)
    {"type":"signal", "ecg":[50], "pcg":[400], "vitals":{...}}             (每100ms)
    {"type":"error", "message":"..."}                                       (错误)

  Client → Server:
    {"type":"command", "command":"run", "params":{}}             (交互命令)
    {"type":"save"}                                               (显式保存)
    {"type":"ping"}                                               (保活)
"""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect, Query
from fastapi.routing import APIRouter

from app.core.logger import logger
from app.engine import VirtualHuman

router = APIRouter()


@router.websocket("/ws/virtual-human")
async def virtual_human_ws(
    websocket: WebSocket,
    token: str = Query(default=None),
    profile_id: str = Query(default=None),
    protocol: str = Query(default="json"),
) -> None:
    """
    虚拟人体实时仿真 WebSocket。

    认证可选（通过 ?token=JWT 查询参数），支持匿名 demo 模式。
    - 有 profile_id：从 DB 加载快照，断开时自动保存
    - 无 profile_id：匿名模式，不持久化
    """
    await websocket.accept()

    # ── 可选认证 ──
    user_id = None
    if token:
        try:
            from app.utils.security import decode_token
            payload = decode_token(token)
            user_id = payload.get("sub") if payload else None
        except Exception:
            pass

    logger.info(f"Virtual Human WS connected (user={user_id}, profile={profile_id})")

    # ── 加载档案快照 ──
    snapshot = None
    profile_info = None
    resolved_profile_id: UUID | None = None

    if profile_id and user_id:
        try:
            resolved_profile_id = UUID(profile_id)
            from app.db.session import db_manager
            from app.crud.virtual_human_profile import get_profile
            async with db_manager.async_session_factory() as session:
                profile = await get_profile(session, resolved_profile_id, UUID(user_id))
                if profile:
                    snapshot = profile.state_snapshot
                    profile_info = {"id": str(profile.id), "name": profile.name}
                    logger.info(f"Loaded profile '{profile.name}' snapshot={'present' if snapshot else 'empty'}")
                else:
                    logger.warning(f"Profile {profile_id} not found for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to load profile: {e}")

    # ── 创建引擎 ──
    engine = VirtualHuman(snapshot=snapshot)

    async def send_message(data: dict) -> None:
        logger.debug(f"VH send_message: {data}")
        """推送 JSON 帧到客户端。"""
        await websocket.send_text(json.dumps(data))

    use_binary = protocol == "binary"

    async def send_binary(data: bytes) -> None:
        logger.debug(f"VH send_binary: {data}")
        """推送二进制帧到客户端。"""
        await websocket.send_bytes(data)

    async def save_state() -> bool:
        """保存当前状态到 DB。"""
        if not resolved_profile_id or not user_id:
            return False
        try:
            from app.db.session import db_manager
            from app.crud.virtual_human_profile import save_snapshot
            async with db_manager.async_session_factory() as session:
                snap = engine.get_snapshot()
                return await save_snapshot(session, resolved_profile_id, UUID(user_id), snap)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            return False

    try:
        # 发送 init 帧（扩展：包含 profile 信息）
        init_payload = engine.get_init_payload()
        if profile_info:
            init_payload["profile"] = profile_info
        await websocket.send_text(json.dumps(init_payload))

        # 启动引擎
        await engine.start(
            send_message,
            send_binary_callback=send_binary if use_binary else None,
            use_binary=use_binary,
        )

        # 监听客户端命令
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type")

                if msg_type == "command":
                    cmd = msg.get("command", "")
                    params = msg.get("params", {})
                    if cmd == "set_leads":
                        # Feature 3: 12-lead ECG — 设置活动导联
                        leads = params.get("leads", ["II"])
                        if isinstance(leads, list):
                            engine.set_leads(leads)
                            logger.debug(f"VH set_leads: {leads} (user={user_id})")
                    else:
                        engine.apply_command(cmd, params)
                        logger.debug(f"VH command: {cmd} params={params} (user={user_id})")

                elif msg_type == "save":
                    ok = await save_state()
                    await websocket.send_text(json.dumps({
                        "type": "save_result",
                        "success": ok,
                    }))

                elif msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

                else:
                    logger.warning(f"VH unknown message type: {msg_type}")

            except json.JSONDecodeError:
                logger.warning(f"VH invalid JSON: {data[:100]}")
            except ValueError as e:
                # 命令不存在等
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": str(e),
                }))
            except Exception as e:
                logger.error(f"VH message processing error: {e}")

    except WebSocketDisconnect:
        logger.info(f"Virtual Human WS disconnected (user={user_id})")
    except Exception as e:
        logger.error(f"Virtual Human WS error: {e}")
    finally:
        # 断开时自动保存
        if resolved_profile_id and user_id:
            await save_state()
            logger.info(f"Auto-saved profile {resolved_profile_id}")
        await engine.stop()
        logger.info(f"Virtual Human engine stopped (user={user_id})")
