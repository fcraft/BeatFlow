"""社区端点"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, update

import app.models  # noqa: F401
from app.core.deps import CurrentActiveUser, DatabaseSession
from app.models.project import CommunityPost, PostComment, MediaFile

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────

class PostCreate(BaseModel):
    title: str
    content: str
    file_id: Optional[str] = None
    tags: List[str] = []


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None


class CommentCreate(BaseModel):
    content: str


def _post_to_dict(p: CommunityPost, author_username: str = "", file_name: str = "", comment_count: int = 0) -> dict:
    return {
        "id": str(p.id),
        "author_id": str(p.author_id),
        "author_username": author_username,
        "title": p.title,
        "content": p.content,
        "file_id": str(p.file_id) if p.file_id else None,
        "file_name": file_name,
        "tags": p.tags or [],
        "like_count": p.like_count,
        "view_count": p.view_count,
        "comment_count": comment_count,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _comment_to_dict(c: PostComment, author_username: str = "") -> dict:
    return {
        "id": str(c.id),
        "post_id": str(c.post_id),
        "author_id": str(c.author_id),
        "author_username": author_username,
        "content": c.content,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ── Posts ─────────────────────────────────────────────────────────

@router.get("/posts")
async def list_posts(
    db: DatabaseSession,
    current_user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 20,
    tag: Optional[str] = None,
    q: Optional[str] = Query(None, description="搜索关键词（匹配标题和内容）"),
):
    """获取社区帖子列表（支持标签筛选和关键词搜索）"""
    from app.models.user import User
    from sqlalchemy import or_

    stmt = select(CommunityPost).order_by(CommunityPost.created_at.desc())
    count_stmt = select(func.count()).select_from(CommunityPost)

    # 标签精确匹配
    if tag:
        stmt = stmt.where(CommunityPost.tags.contains([tag]))
        count_stmt = count_stmt.where(CommunityPost.tags.contains([tag]))

    # 关键词搜索（标题 + 内容 + 标签名）
    if q:
        kw = f"%{q}%"
        keyword_filter = or_(
            CommunityPost.title.ilike(kw),
            CommunityPost.content.ilike(kw),
        )
        stmt = stmt.where(keyword_filter)
        count_stmt = count_stmt.where(keyword_filter)

    total = (await db.execute(count_stmt)).scalar_one()
    result = await db.execute(stmt.offset(skip).limit(limit))
    posts = result.scalars().all()

    items = []
    for p in posts:
        author = (await db.execute(select(User).where(User.id == p.author_id))).scalar_one_or_none()
        file_name = ""
        if p.file_id:
            mf = (await db.execute(select(MediaFile).where(MediaFile.id == p.file_id))).scalar_one_or_none()
            if mf:
                file_name = mf.original_filename or mf.filename
        comment_count = (await db.execute(
            select(func.count()).select_from(PostComment).where(PostComment.post_id == p.id)
        )).scalar_one()
        items.append(_post_to_dict(p, author.username if author else "", file_name, comment_count))

    return {"items": items, "total": total, "page": skip // limit + 1, "size": limit}


@router.post("/posts", status_code=status.HTTP_201_CREATED)
async def create_post(
    db: DatabaseSession,
    data: PostCreate,
    current_user: CurrentActiveUser,
):
    """创建帖子"""
    post = CommunityPost(
        author_id=current_user.id,
        title=data.title,
        content=data.content,
        file_id=uuid.UUID(data.file_id) if data.file_id else None,
        tags=data.tags,
    )
    db.add(post)
    await db.flush()
    await db.refresh(post)
    await db.commit()
    return _post_to_dict(post, current_user.username)


@router.get("/posts/{post_id}")
async def get_post(
    db: DatabaseSession,
    post_id: str,
    current_user: CurrentActiveUser,
):
    """获取帖子详情（并增加浏览量）"""
    from app.models.user import User

    result = await db.execute(select(CommunityPost).where(CommunityPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    # Increment view count
    await db.execute(
        update(CommunityPost).where(CommunityPost.id == post_id).values(view_count=CommunityPost.view_count + 1)
    )
    await db.commit()
    await db.refresh(post)

    author = (await db.execute(select(User).where(User.id == post.author_id))).scalar_one_or_none()
    file_name = ""
    if post.file_id:
        mf = (await db.execute(select(MediaFile).where(MediaFile.id == post.file_id))).scalar_one_or_none()
        if mf:
            file_name = mf.original_filename or mf.filename
    comment_count = (await db.execute(
        select(func.count()).select_from(PostComment).where(PostComment.post_id == post.id)
    )).scalar_one()
    return _post_to_dict(post, author.username if author else "", file_name, comment_count)


@router.put("/posts/{post_id}")
async def update_post(
    db: DatabaseSession,
    post_id: str,
    data: PostUpdate,
    current_user: CurrentActiveUser,
):
    """更新帖子（仅作者）"""
    result = await db.execute(select(CommunityPost).where(CommunityPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if str(post.author_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="无权修改")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(post, k, v)
    await db.flush()
    await db.refresh(post)
    await db.commit()
    return _post_to_dict(post, current_user.username)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    db: DatabaseSession,
    post_id: str,
    current_user: CurrentActiveUser,
):
    """删除帖子（仅作者）"""
    result = await db.execute(select(CommunityPost).where(CommunityPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if str(post.author_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="无权删除")
    await db.delete(post)
    await db.commit()


@router.post("/posts/{post_id}/like")
async def like_post(
    db: DatabaseSession,
    post_id: str,
    current_user: CurrentActiveUser,
):
    """点赞帖子"""
    result = await db.execute(select(CommunityPost).where(CommunityPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    await db.execute(
        update(CommunityPost).where(CommunityPost.id == post_id).values(like_count=CommunityPost.like_count + 1)
    )
    await db.commit()
    return {"like_count": post.like_count + 1}


# ── Comments ──────────────────────────────────────────────────────

@router.get("/posts/{post_id}/comments")
async def list_comments(
    db: DatabaseSession,
    post_id: str,
    current_user: CurrentActiveUser,
):
    """获取帖子评论"""
    from app.models.user import User

    result = await db.execute(
        select(PostComment).where(PostComment.post_id == post_id).order_by(PostComment.created_at.asc())
    )
    comments = result.scalars().all()

    items = []
    for c in comments:
        author = (await db.execute(select(User).where(User.id == c.author_id))).scalar_one_or_none()
        items.append(_comment_to_dict(c, author.username if author else ""))
    return {"items": items, "total": len(items)}


@router.post("/posts/{post_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_comment(
    db: DatabaseSession,
    post_id: str,
    data: CommentCreate,
    current_user: CurrentActiveUser,
):
    """发表评论"""
    result = await db.execute(select(CommunityPost).where(CommunityPost.id == post_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="帖子不存在")

    comment = PostComment(
        post_id=uuid.UUID(post_id),
        author_id=current_user.id,
        content=data.content,
    )
    db.add(comment)
    await db.flush()
    await db.refresh(comment)
    await db.commit()
    return _comment_to_dict(comment, current_user.username)


@router.delete("/posts/{post_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    db: DatabaseSession,
    post_id: str,
    comment_id: str,
    current_user: CurrentActiveUser,
):
    """删除评论（评论作者 / 帖子作者 / 管理员均可）"""
    result = await db.execute(select(PostComment).where(PostComment.id == comment_id, PostComment.post_id == post_id))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    # 同时查出帖子，用于判断帖子作者权限
    post_res = await db.execute(select(CommunityPost).where(CommunityPost.id == post_id))
    post = post_res.scalar_one_or_none()

    is_admin = current_user.is_superuser or current_user.role == "admin"
    is_comment_author = str(comment.author_id) == str(current_user.id)
    is_post_author = post is not None and str(post.author_id) == str(current_user.id)

    if not (is_admin or is_comment_author or is_post_author):
        raise HTTPException(status_code=403, detail="无权删除")

    await db.delete(comment)
    await db.commit()
