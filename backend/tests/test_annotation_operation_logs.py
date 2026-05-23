"""标注操作日志 & 撤销系统 — 集成测试

使用 asyncio.run() 管理 event loop，绕开 pytest-asyncio 与 asyncpg 冲突。

运行方式（需单独执行）：
    PYTHONPATH=. .venv/bin/pytest tests/test_annotation_operation_logs.py -v --sw

或逐个测试类运行：
    PYTHONPATH=. .venv/bin/pytest tests/test_annotation_operation_logs.py::TestLogging -v
    PYTHONPATH=. .venv/bin/pytest tests/test_annotation_operation_logs.py::TestQuery -v
    PYTHONPATH=. .venv/bin/pytest tests/test_annotation_operation_logs.py::TestUndo -v

注意：由于 asyncio.run() 与 pytest-asyncio 的 event loop 管理不兼容，
      此文件不能与其他 async 测试文件一起运行。
      默认通过 --ignore 排除。
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from sqlalchemy import select

from app.db.session import db_manager
from app.models.project import Annotation, OperationLog
from app.models.user import User

FID = uuid.UUID("e0942a49-8cd3-49a6-886a-277e8173e846")
_prefix = uuid.uuid4().hex[:8]


def _lbl(name: str) -> str:
    return f"{_prefix}-{name}"


async def _get_admin() -> User:
    from sqlalchemy import select
    async with db_manager.async_session_factory() as s:
        result = await s.execute(select(User).where(User.email == "admin@beatflow.com"))
        return result.scalar_one()


def _run(coro):
    """在独立 event loop 中运行协程，前后清理连接池"""
    # 先清理上次残留的连接（已绑定旧 event loop）
    try:
        asyncio.run(_dispose_pool())
    except Exception:
        pass
    result = asyncio.run(coro)
    # 恢复新 event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return result


async def _dispose_pool():
    await db_manager.engine.dispose()


# ──────────────────────────────────────────────────────────────────────────────
# 1. OperationLog 模型（纯单元测试）
# ──────────────────────────────────────────────────────────────────────────────

class TestOperationLogModel:
    _uid = uuid.UUID("00000000-0000-0000-0000-000000000001")

    def test_defaults(self):
        log = OperationLog(
            file_id=FID, user_id=self._uid, operation_type="delete",
            description="测试", details={"key": "val"}, is_undone=False,
        )
        assert log.is_undone is False
        assert log.undone_at is None

    def test_to_dict(self):
        now = datetime.now(timezone.utc)
        log = OperationLog(
            id=uuid.uuid4(), file_id=FID, user_id=self._uid,
            operation_type="create", description="测试",
            details={"id": "abc"}, is_undone=False, created_at=now,
        )
        d = log.to_dict()
        assert d["id"] == str(log.id)
        assert d["file_id"] == str(FID)
        assert d["operation_type"] == "create"
        assert d["is_undone"] is False

    def test_undone_to_dict(self):
        undone = datetime(2026, 5, 23, 12, 0, 0, tzinfo=timezone.utc)
        log = OperationLog(
            file_id=FID, user_id=self._uid, operation_type="delete",
            description="x", is_undone=True, undone_at=undone,
        )
        d = log.to_dict()
        assert d["is_undone"] is True
        assert d["undone_at"] == "2026-05-23T12:00:00+00:00"


# ──────────────────────────────────────────────────────────────────────────────
# 2. 日志埋点 — 集成测试
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.db_integration
class TestLogging:
    def test_create_log(self):
        from app.api.v1.endpoints.annotations import create_annotation, AnnotationCreate
        from app.schemas.project import AnnotationType

        async def _test():
            user = await _get_admin()
            label = _lbl("create-log")
            async with db_manager.async_session_factory() as s:
                ann_in = AnnotationCreate(file_id=str(FID), annotation_type=AnnotationType.S1,
                                           start_time=1.0, end_time=1.08, label=label)
                await create_annotation(s, ann_in, user)
                logs = (await s.execute(
                    select(OperationLog).where(
                        OperationLog.file_id == FID, OperationLog.operation_type == "create",
                        OperationLog.description.contains(label),
                    ).order_by(OperationLog.created_at.desc()).limit(1)
                )).scalars().all()
                assert len(logs) == 1
                snap = logs[0].details["created_annotation"]
                assert snap["annotation_type"] == "s1"
                assert snap["label"] == label
                for k in ("id", "file_id", "annotation_type", "start_time", "end_time", "label", "source"):
                    assert k in snap

        _run(_test())

    def test_delete_log(self):
        from app.api.v1.endpoints.annotations import create_annotation, delete_annotation
        from app.schemas.project import AnnotationCreate, AnnotationType

        async def _test():
            user = await _get_admin()
            label = _lbl("to-delete")
            async with db_manager.async_session_factory() as s:
                ann = await create_annotation(s, AnnotationCreate(
                    file_id=str(FID), annotation_type=AnnotationType.S2,
                    start_time=3.0, end_time=3.08, label=label,
                ), user)
                await delete_annotation(s, str(ann.id), user)
                logs = (await s.execute(
                    select(OperationLog).where(
                        OperationLog.file_id == FID, OperationLog.operation_type == "delete",
                        OperationLog.description.contains(label),
                    ).order_by(OperationLog.created_at.desc()).limit(1)
                )).scalars().all()
                assert len(logs) == 1
                snap = logs[0].details["deleted_annotation"]
                assert snap["annotation_type"] == "s2"
                assert snap["start_time"] == 3.0
                assert "id" in snap

        _run(_test())

    def test_update_log(self):
        from app.api.v1.endpoints.annotations import create_annotation, update_annotation
        from app.schemas.project import AnnotationCreate, AnnotationType, AnnotationUpdate

        async def _test():
            user = await _get_admin()
            before, after = _lbl("before"), _lbl("after")
            async with db_manager.async_session_factory() as s:
                ann = await create_annotation(s, AnnotationCreate(
                    file_id=str(FID), annotation_type=AnnotationType.S1,
                    start_time=7.0, end_time=7.08, label=before,
                ), user)
                await update_annotation(s, str(ann.id), AnnotationUpdate(
                    start_time=7.5, end_time=7.58, label=after,
                ), user)
                logs = (await s.execute(
                    select(OperationLog).where(
                        OperationLog.file_id == FID, OperationLog.operation_type == "update",
                        OperationLog.description.contains(after),
                    ).order_by(OperationLog.created_at.desc()).limit(1)
                )).scalars().all()
                assert len(logs) == 1
                assert logs[0].details["old_values"]["label"] == before
                assert logs[0].details["new_values"]["label"] == after

        _run(_test())

    def test_batch_delete_log(self):
        from app.api.v1.endpoints.annotations import create_annotation, batch_annotations, BatchAnnotationUpdate
        from app.schemas.project import AnnotationCreate, AnnotationType

        async def _test():
            user = await _get_admin()
            labels = [_lbl(f"batch-{i}") for i in range(3)]
            async with db_manager.async_session_factory() as s:
                ids = []
                for i, lbl in enumerate(labels):
                    ann = await create_annotation(s, AnnotationCreate(
                        file_id=str(FID), annotation_type=AnnotationType.S1,
                        start_time=50.0 + i, end_time=50.08 + i, label=lbl,
                    ), user)
                    ids.append(str(ann.id))
                await batch_annotations(s, BatchAnnotationUpdate(ids=ids, action="delete"), user)
                logs = (await s.execute(
                    select(OperationLog).where(
                        OperationLog.file_id == FID, OperationLog.operation_type == "batch_delete",
                    ).order_by(OperationLog.created_at.desc()).limit(1)
                )).scalars().all()
                assert logs[0].details["count"] == 3
                got = sorted([d["label"] for d in logs[0].details["deleted_annotations"]])
                assert got == sorted(labels)

        _run(_test())

    def test_accept_log(self):
        from app.api.v1.endpoints.annotations import accept_annotations, AnnotationAcceptRequest, AnnotationAcceptItem

        async def _test():
            user = await _get_admin()
            a1, a2 = _lbl("accept-1"), _lbl("accept-2")
            async with db_manager.async_session_factory() as s:
                req = AnnotationAcceptRequest(file_id=str(FID), items=[
                    AnnotationAcceptItem(annotation_type="s1", start_time=100.0, end_time=100.08, label=a1, confidence=0.95),
                    AnnotationAcceptItem(annotation_type="s2", start_time=100.5, end_time=100.58, label=a2, confidence=0.88),
                ])
                await accept_annotations(s, req, user)
                # 查最新的 accept 日志（按时间倒序取第一条）
                logs = (await s.execute(
                    select(OperationLog).where(
                        OperationLog.file_id == FID, OperationLog.operation_type == "accept",
                    ).order_by(OperationLog.created_at.desc()).limit(1)
                )).scalars().all()
                assert len(logs) == 1
                details = logs[0].details
                assert details["accepted_count"] == 2
                assert len(details["new_annotations"]) == 2
                # 验证新标注的 label 匹配
                new_labels = {snap["label"] for snap in details["new_annotations"]}
                assert a1 in new_labels
                assert a2 in new_labels
                for snap in details["new_annotations"]:
                    assert "id" in snap
                    assert snap["source"] == "auto"

        _run(_test())


# ──────────────────────────────────────────────────────────────────────────────
# 3. 查询
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.db_integration
class TestQuery:
    def test_list_desc_order(self):
        async def _test():
            from app.api.v1.endpoints.annotations import list_operation_logs
            user = await _get_admin()
            async with db_manager.async_session_factory() as s:
                result = await list_operation_logs(s, user, str(FID), limit=20)
                items = result.items
                if len(items) >= 2:
                    timestamps = [i.created_at for i in items if i.created_at]
                    assert timestamps == sorted(timestamps, reverse=True)
        _run(_test())

    def test_limit(self):
        async def _test():
            from app.api.v1.endpoints.annotations import list_operation_logs
            user = await _get_admin()
            async with db_manager.async_session_factory() as s:
                result = await list_operation_logs(s, user, str(FID), limit=2)
                assert len(result.items) <= 2
        _run(_test())

    def test_total_count(self):
        async def _test():
            from app.api.v1.endpoints.annotations import list_operation_logs
            user = await _get_admin()
            async with db_manager.async_session_factory() as s:
                result = await list_operation_logs(s, user, str(FID))
                assert isinstance(result.total, int)
                assert result.total >= len(result.items)
        _run(_test())

    def test_empty_for_nonexistent_file(self):
        async def _test():
            from app.api.v1.endpoints.annotations import list_operation_logs
            user = await _get_admin()
            async with db_manager.async_session_factory() as s:
                result = await list_operation_logs(s, user, "00000000-0000-0000-0000-000000000000")
                assert result.items == []
                assert result.total == 0
        _run(_test())


# ──────────────────────────────────────────────────────────────────────────────
# 4-5. 撤销 — 正常路径 + 边界条件
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.db_integration
class TestUndo:
    def test_undo_delete_restores(self):
        from app.api.v1.endpoints.annotations import (
            create_annotation, delete_annotation, list_operation_logs, undo_operation,
        )
        from app.schemas.project import AnnotationCreate, AnnotationType

        async def _test():
            user = await _get_admin()
            label = _lbl("undo-del")
            async with db_manager.async_session_factory() as s:
                ann = await create_annotation(s, AnnotationCreate(
                    file_id=str(FID), annotation_type=AnnotationType.S1,
                    start_time=20.0, end_time=20.08, label=label,
                ), user)
                ann_id = str(ann.id)
                await delete_annotation(s, ann_id, user)
                logs = await list_operation_logs(s, user, str(FID), limit=10)
                del_log = next(l for l in logs.items if l.operation_type == "delete" and label in l.description)
                result = await undo_operation(s, del_log.id, user)
                assert result.success is True
                assert result.recreated_count == 1
                restored = (await s.execute(
                    select(Annotation).where(Annotation.file_id == FID, Annotation.label == label)
                )).scalars().all()
                assert len(restored) == 1
                assert restored[0].start_time == 20.0
                assert str(restored[0].id) != ann_id
        _run(_test())

    def test_undo_preserves_all_fields(self):
        from app.api.v1.endpoints.annotations import (
            create_annotation, delete_annotation, list_operation_logs, undo_operation,
        )
        from app.schemas.project import AnnotationCreate, AnnotationType

        async def _test():
            user = await _get_admin()
            label = _lbl("full-snap")
            async with db_manager.async_session_factory() as s:
                ann = await create_annotation(s, AnnotationCreate(
                    file_id=str(FID), annotation_type=AnnotationType.S2,
                    start_time=40.0, end_time=40.12, label=label, confidence=0.73,
                ), user)
                await delete_annotation(s, str(ann.id), user)
                logs = await list_operation_logs(s, user, str(FID), limit=10)
                del_log = next(l for l in logs.items if l.operation_type == "delete" and label in l.description)
                await undo_operation(s, del_log.id, user)
                restored = (await s.execute(
                    select(Annotation).where(Annotation.file_id == FID, Annotation.label == label)
                )).scalars().all()
                assert len(restored) == 1
                assert restored[0].confidence == 0.73
                assert restored[0].source == "manual"
                assert restored[0].end_time == 40.12
        _run(_test())

    def test_undo_batch_restores_all(self):
        from app.api.v1.endpoints.annotations import (
            create_annotation, batch_annotations, BatchAnnotationUpdate,
            list_operation_logs, undo_operation,
        )
        from app.schemas.project import AnnotationCreate, AnnotationType

        async def _test():
            user = await _get_admin()
            labels = [_lbl(f"ubatch-{i}") for i in range(4)]
            async with db_manager.async_session_factory() as s:
                ids = []
                for i, lbl in enumerate(labels):
                    ann = await create_annotation(s, AnnotationCreate(
                        file_id=str(FID), annotation_type=AnnotationType.S1,
                        start_time=200.0 + i, end_time=200.08 + i, label=lbl,
                    ), user)
                    ids.append(str(ann.id))
                await batch_annotations(s, BatchAnnotationUpdate(ids=ids, action="delete"), user)
                logs = await list_operation_logs(s, user, str(FID), limit=10)
                batch_log = next(l for l in logs.items if l.operation_type == "batch_delete")
                result = await undo_operation(s, batch_log.id, user)
                assert result.recreated_count == 4
                prefix = _lbl("ubatch-")
                restored = (await s.execute(
                    select(Annotation).where(Annotation.file_id == FID, Annotation.label.startswith(prefix))
                )).scalars().all()
                assert len(restored) == 4
        _run(_test())

    def test_undo_accept(self):
        from app.api.v1.endpoints.annotations import (
            accept_annotations, AnnotationAcceptRequest, AnnotationAcceptItem,
            list_operation_logs, undo_operation,
        )

        async def _test():
            user = await _get_admin()
            a1 = _lbl("undoacc-1")
            async with db_manager.async_session_factory() as s:
                req = AnnotationAcceptRequest(file_id=str(FID), items=[
                    AnnotationAcceptItem(annotation_type="s1", start_time=300.0, end_time=300.08, label=a1),
                    AnnotationAcceptItem(annotation_type="s2", start_time=300.5, end_time=300.58, label=_lbl("undoacc-2")),
                ])
                await accept_annotations(s, req, user)
                logs = await list_operation_logs(s, user, str(FID), limit=10)
                accept_log = next(l for l in logs.items if l.operation_type == "accept" and a1 in str(l.details))
                new_ids = {a["id"] for a in accept_log.details["new_annotations"]}
                result = await undo_operation(s, accept_log.id, user)
                assert result.success is True
                assert result.deleted_count == len(new_ids)
                for nid in new_ids:
                    existing = (await s.execute(select(Annotation).where(Annotation.id == nid))).scalar_one_or_none()
                    assert existing is None
        _run(_test())

    def test_double_undo_rejected(self):
        from app.api.v1.endpoints.annotations import (
            create_annotation, delete_annotation, list_operation_logs, undo_operation,
        )
        from app.schemas.project import AnnotationCreate, AnnotationType

        async def _test():
            user = await _get_admin()
            label = _lbl("dbl-undo")
            async with db_manager.async_session_factory() as s:
                ann = await create_annotation(s, AnnotationCreate(
                    file_id=str(FID), annotation_type=AnnotationType.S1,
                    start_time=60.0, end_time=60.08, label=label,
                ), user)
                await delete_annotation(s, str(ann.id), user)
                logs = await list_operation_logs(s, user, str(FID), limit=10)
                del_log = next(l for l in logs.items if l.operation_type == "delete" and label in l.description)
                r = await undo_operation(s, del_log.id, user)
                assert r.success is True
                from fastapi import HTTPException
                with pytest.raises(HTTPException) as exc:
                    await undo_operation(s, del_log.id, user)
                assert exc.value.status_code == 400
                assert "已被撤销" in exc.value.detail
        _run(_test())

    def test_undo_create_rejected(self):
        async def _test():
            from app.api.v1.endpoints.annotations import list_operation_logs, undo_operation
            user = await _get_admin()
            async with db_manager.async_session_factory() as s:
                logs = await list_operation_logs(s, user, str(FID), limit=50)
                create_logs = [l for l in logs.items if l.operation_type == "create"]
                if not create_logs:
                    pytest.skip("No create logs")
                from fastapi import HTTPException
                with pytest.raises(HTTPException) as exc:
                    await undo_operation(s, create_logs[0].id, user)
                assert exc.value.status_code == 400
                assert "不支持撤销" in exc.value.detail
        _run(_test())

    def test_undo_update_rejected(self):
        async def _test():
            from app.api.v1.endpoints.annotations import list_operation_logs, undo_operation
            user = await _get_admin()
            async with db_manager.async_session_factory() as s:
                logs = await list_operation_logs(s, user, str(FID), limit=50)
                upd_logs = [l for l in logs.items if l.operation_type == "update"]
                if not upd_logs:
                    pytest.skip("No update logs")
                from fastapi import HTTPException
                with pytest.raises(HTTPException) as exc:
                    await undo_operation(s, upd_logs[0].id, user)
                assert exc.value.status_code == 400
        _run(_test())

    def test_undo_nonexistent_404(self):
        async def _test():
            from app.api.v1.endpoints.annotations import undo_operation
            from fastapi import HTTPException
            user = await _get_admin()
            async with db_manager.async_session_factory() as s:
                with pytest.raises(HTTPException) as exc:
                    await undo_operation(s, "00000000-0000-0000-0000-000000000000", user)
                assert exc.value.status_code == 404
        _run(_test())

    def test_undo_writes_undo_log(self):
        from app.api.v1.endpoints.annotations import (
            create_annotation, delete_annotation, list_operation_logs, undo_operation,
        )
        from app.schemas.project import AnnotationCreate, AnnotationType

        async def _test():
            user = await _get_admin()
            label = _lbl("undo-audit")
            async with db_manager.async_session_factory() as s:
                ann = await create_annotation(s, AnnotationCreate(
                    file_id=str(FID), annotation_type=AnnotationType.S1,
                    start_time=70.0, end_time=70.08, label=label,
                ), user)
                await delete_annotation(s, str(ann.id), user)
                logs = await list_operation_logs(s, user, str(FID), limit=10)
                del_log = next(l for l in logs.items if l.operation_type == "delete" and label in l.description)
                await undo_operation(s, del_log.id, user)
                logs2 = await list_operation_logs(s, user, str(FID), limit=10)
                undo_logs = [l for l in logs2.items if l.operation_type == "undo"]
                assert len(undo_logs) >= 1
                assert "撤销了操作" in undo_logs[0].description
                assert undo_logs[0].details["original_operation"] == "delete"
        _run(_test())
