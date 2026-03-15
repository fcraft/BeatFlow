"""通知端点"""
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func, update

from app.core.deps import CurrentActiveUser, DatabaseSession
from app.models.notification import Notification
from app.models.project import ProjectMember
from app.models.user import User
from app.schemas.notification import NotificationResponse, NotificationListResponse

router = APIRouter()


def _build_notification_response(notif: Notification, sender: Optional[User]) -> NotificationResponse:
    return NotificationResponse(
        id=str(notif.id),
        notification_type=notif.notification_type,
        title=notif.title,
        content=notif.content,
        is_read=notif.is_read,
        status=notif.status,
        data=notif.data or {},
        sender={"id": str(sender.id), "username": sender.username} if sender else None,
        created_at=notif.created_at,
    )


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    db: DatabaseSession,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    notification_type: Optional[str] = Query(None),
) -> NotificationListResponse:
    """获取我的通知列表"""
    skip = (page - 1) * size

    stmt = select(Notification).where(Notification.recipient_id == current_user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)
    if notification_type:
        stmt = stmt.where(Notification.notification_type == notification_type)
    stmt = stmt.order_by(Notification.created_at.desc())

    count_stmt = select(func.count()).select_from(Notification).where(Notification.recipient_id == current_user.id)
    if unread_only:
        count_stmt = count_stmt.where(Notification.is_read == False)
    if notification_type:
        count_stmt = count_stmt.where(Notification.notification_type == notification_type)

    total = (await db.execute(count_stmt)).scalar_one()
    result = await db.execute(stmt.offset(skip).limit(size))
    notifications = list(result.scalars().all())

    # 统计未读总数（不受 unread_only 参数影响）
    unread_count_stmt = select(func.count()).select_from(Notification).where(
        Notification.recipient_id == current_user.id,
        Notification.is_read == False,
    )
    unread_count = (await db.execute(unread_count_stmt)).scalar_one()

    items = []
    for n in notifications:
        sender = None
        if n.sender_id:
            r = await db.execute(select(User).where(User.id == n.sender_id))
            sender = r.scalar_one_or_none()
        items.append(_build_notification_response(n, sender))

    return NotificationListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        has_next=(skip + size) < total,
        unread_count=unread_count,
    )


@router.get("/unread-count")
async def get_unread_count(
    db: DatabaseSession,
    current_user: CurrentActiveUser,
) -> dict:
    """获取未读通知数量"""
    stmt = select(func.count()).select_from(Notification).where(
        Notification.recipient_id == current_user.id,
        Notification.is_read == False,
    )
    count = (await db.execute(stmt)).scalar_one()
    return {"count": count}


@router.patch("/{notification_id}/read")
async def mark_read(
    db: DatabaseSession,
    notification_id: str,
    current_user: CurrentActiveUser,
) -> dict:
    """标记通知为已读"""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == current_user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在")

    notif.is_read = True
    await db.commit()
    return {"success": True}


@router.patch("/read-all")
async def mark_all_read(
    db: DatabaseSession,
    current_user: CurrentActiveUser,
) -> dict:
    """全部标为已读"""
    await db.execute(
        update(Notification)
        .where(
            Notification.recipient_id == current_user.id,
            Notification.is_read == False,
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"success": True}


@router.post("/{notification_id}/accept")
async def accept_invite(
    db: DatabaseSession,
    notification_id: str,
    current_user: CurrentActiveUser,
) -> dict:
    """接受项目邀请"""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == current_user.id,
            Notification.notification_type == "project_invite",
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="邀请通知不存在")

    if notif.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该邀请已处理")

    project_id = notif.data.get("project_id")
    role = notif.data.get("member_role", "member")

    if not project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邀请数据无效")

    # 检查是否已是成员
    existing = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        )
    )
    if not existing.scalar_one_or_none():
        member = ProjectMember(
            project_id=uuid.UUID(project_id),
            user_id=current_user.id,
            role=role,
        )
        db.add(member)

    notif.status = "accepted"
    notif.is_read = True
    await db.commit()

    return {"success": True, "project_id": project_id}


@router.post("/{notification_id}/reject")
async def reject_invite(
    db: DatabaseSession,
    notification_id: str,
    current_user: CurrentActiveUser,
) -> dict:
    """拒绝项目邀请"""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == current_user.id,
            Notification.notification_type == "project_invite",
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="邀请通知不存在")

    if notif.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该邀请已处理")

    notif.status = "rejected"
    notif.is_read = True
    await db.commit()

    return {"success": True}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    db: DatabaseSession,
    notification_id: str,
    current_user: CurrentActiveUser,
) -> None:
    """删除通知"""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == current_user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在")

    await db.delete(notif)
    await db.commit()
