"""WebSocket 端点"""
import json
import uuid
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.routing import APIRouter

from app.core.deps import get_current_user
from app.core.logger import logger
from app.db.session import DatabaseSession
from app.schemas.user import User

router = APIRouter()


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.user_connections: Dict[int, Set[str]] = {}
        self.connection_user_map: Dict[str, int] = {}
    
    async def connect(self, websocket: WebSocket, room_id: str, user_id: int):
        """连接WebSocket"""
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        
        # 存储连接信息
        self.active_connections.setdefault(room_id, set()).add(websocket)
        self.user_connections.setdefault(user_id, set()).add(room_id)
        self.connection_user_map[connection_id] = user_id
        
        return connection_id
    
    def disconnect(self, websocket: WebSocket, room_id: str, connection_id: str):
        """断开WebSocket连接"""
        if room_id in self.active_connections:
            self.active_connections[room_id].discard(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
        
        if connection_id in self.connection_user_map:
            user_id = self.connection_user_map[connection_id]
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(room_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            del self.connection_user_map[connection_id]
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """发送个人消息"""
        await websocket.send_text(json.dumps(message))
    
    async def broadcast(self, message: dict, room_id: str, exclude: WebSocket = None):
        """广播消息到房间"""
        if room_id not in self.active_connections:
            return
        
        disconnected = set()
        for connection in self.active_connections[room_id]:
            if connection != exclude:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception:
                    disconnected.add(connection)
        
        # 清理断开连接
        for connection in disconnected:
            self.active_connections[room_id].discard(connection)
        
        if not self.active_connections[room_id]:
            del self.active_connections[room_id]


# 全局连接管理器
manager = ConnectionManager()


@router.websocket("/ws/collaboration/{room_id}")
async def collaboration_websocket(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(...),
    db: DatabaseSession = Depends(get_db),
):
    """协作WebSocket端点"""
    # 验证用户
    from app.core.deps import get_current_user
    
    # 这里简化验证，实际应该使用JWT验证
    try:
        # 解码令牌获取用户
        from app.utils.security import decode_token
        
        payload = decode_token(token)
        if not payload:
            await websocket.close(code=1008, reason="认证失败")
            return
        
        user_id = int(payload.get("sub"))
        user = await get_current_user(db, credentials=(token, ""))  # 简化验证
        
        if not user:
            await websocket.close(code=1008, reason="用户不存在")
            return
    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        await websocket.close(code=1008, reason="认证失败")
        return
    
    # 连接WebSocket
    connection_id = await manager.connect(websocket, room_id, user_id)
    
    try:
        # 发送连接成功消息
        await manager.send_personal_message({
            "type": "connected",
            "connection_id": connection_id,
            "user_id": user_id,
            "room_id": room_id,
        }, websocket)
        
        # 广播用户加入消息
        await manager.broadcast({
            "type": "user_joined",
            "user_id": user_id,
            "connection_id": connection_id,
            "timestamp": datetime.utcnow().isoformat(),
        }, room_id, exclude=websocket)
        
        # 处理消息
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                if message_type == "cursor_move":
                    # 光标移动
                    await manager.broadcast({
                        "type": "cursor_move",
                        "user_id": user_id,
                        "cursor_position": message.get("cursor_position"),
                        "timestamp": datetime.utcnow().isoformat(),
                    }, room_id, exclude=websocket)
                
                elif message_type == "annotation_create":
                    # 创建标记
                    await manager.broadcast({
                        "type": "annotation_create",
                        "user_id": user_id,
                        "annotation": message.get("annotation"),
                        "timestamp": datetime.utcnow().isoformat(),
                    }, room_id, exclude=websocket)
                
                elif message_type == "annotation_update":
                    # 更新标记
                    await manager.broadcast({
                        "type": "annotation_update",
                        "user_id": user_id,
                        "annotation": message.get("annotation"),
                        "timestamp": datetime.utcnow().isoformat(),
                    }, room_id, exclude=websocket)
                
                elif message_type == "annotation_delete":
                    # 删除标记
                    await manager.broadcast({
                        "type": "annotation_delete",
                        "user_id": user_id,
                        "annotation_id": message.get("annotation_id"),
                        "timestamp": datetime.utcnow().isoformat(),
                    }, room_id, exclude=websocket)
                
                elif message_type == "chat_message":
                    # 聊天消息
                    await manager.broadcast({
                        "type": "chat_message",
                        "user_id": user_id,
                        "message": message.get("message"),
                        "timestamp": datetime.utcnow().isoformat(),
                    }, room_id, exclude=websocket)
                
                elif message_type == "keep_alive":
                    # 保活消息
                    await manager.send_personal_message({
                        "type": "keep_alive",
                        "timestamp": datetime.utcnow().isoformat(),
                    }, websocket)
                
                else:
                    logger.warning(f"Unknown message type: {message_type}")
            
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {data}")
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # 广播用户离开消息
        await manager.broadcast({
            "type": "user_left",
            "user_id": user_id,
            "connection_id": connection_id,
            "timestamp": datetime.utcnow().isoformat(),
        }, room_id, exclude=websocket)
        
        # 清理连接
        manager.disconnect(websocket, room_id, connection_id)


@router.websocket("/ws/heartbeat")
async def heartbeat_websocket(websocket: WebSocket):
    """心跳WebSocket端点"""
    await websocket.accept()
    
    try:
        while True:
            # 接收心跳消息
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    # 回复pong
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat(),
                    }))
            
            except json.JSONDecodeError:
                logger.error(f"Invalid heartbeat JSON: {data}")
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    except WebSocketDisconnect:
        logger.info("Heartbeat WebSocket disconnected")
    except Exception as e:
        logger.error(f"Heartbeat WebSocket error: {e}")


@router.get("/ws/rooms/{room_id}/users")
async def get_room_users(
    room_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """获取房间在线用户列表"""
    if room_id not in manager.active_connections:
        return {"room_id": room_id, "users": []}
    
    # 获取房间中的用户ID列表
    user_ids = set()
    connection_ids = manager.active_connections.get(room_id, set())
    
    for connection in connection_ids:
        # 这里简化，实际应该通过连接ID映射到用户ID
        pass
    
    return {
        "room_id": room_id,
        "users_count": len(connection_ids),
    }