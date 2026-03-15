"""文件端点"""
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import CurrentActiveUser, CurrentUser, DatabaseSession
from app.models.base import ErrorResponse
import app.models  # noqa: F401 — ensures all ORM relationships are resolved
from app.models.project import MediaFile, Annotation
from app.schemas.project import MediaFileResponse
from app.services.storage import LocalStorageBackend, temp_local_file
from app.services.storage_manager import get_storage_backend, get_storage_for_file
from app.utils.http_range import build_bytes_stream_response, build_file_stream_response
from app.analysis.ecg_detector import ecg_detect_scipy, ecg_detect_neurokit2, ecg_detect_wfdb
from app.analysis.pcg_detector import pcg_detect_scipy, pcg_detect_neurokit2, classify_s1s2


class FileTypeUpdate(BaseModel):
    file_type: str  # audio | video | ecg | pcg | other


VALID_FILE_TYPES = {"audio", "video", "ecg", "pcg", "other"}

# 各类型对应的检测配置
DETECT_CONFIG = {
    "pcg": {
        "types": ["s1", "s2"],
        "description": "心音 S1/S2 检测",
    },
    "audio": {
        "types": ["s1", "s2"],
        "description": "心音 S1/S2 检测",
    },
    "ecg": {
        "types": ["qrs", "p_wave", "t_wave"],
        "description": "心电 QRS/P/T 波检测",
    },
}

# 支持的检测算法
ALGORITHMS = {
    "scipy":     "SciPy 信号处理（内置，快速）",
    "neurokit2": "NeuroKit2（AI增强，精度更高）",
    "wfdb":      "WFDB/XQRS（PhysioNet 算法，适合标准 ECG）",
    "auto":      "自动选择最佳算法",
}


router = APIRouter()


async def _cleanup_file_references(db, file_uuid) -> None:
    """清理文件被引用的外键，防止约束冲突"""
    from sqlalchemy import update as sa_update
    from app.models.project import FileAssociation, CommunityPost
    await db.execute(sa_update(FileAssociation).where(FileAssociation.ecg_file_id == file_uuid).values(ecg_file_id=None))
    await db.execute(sa_update(FileAssociation).where(FileAssociation.pcg_file_id == file_uuid).values(pcg_file_id=None))
    await db.execute(sa_update(FileAssociation).where(FileAssociation.video_file_id == file_uuid).values(video_file_id=None))
    await db.execute(sa_update(CommunityPost).where(CommunityPost.file_id == file_uuid).values(file_id=None))


def _is_admin(user) -> bool:
    return bool(user.is_superuser or user.role == "admin")


@router.get(
    "/algorithms",
    summary="获取支持的检测算法列表",
)
async def list_algorithms(current_user: CurrentActiveUser):
    """返回当前支持的检测算法"""
    return {
        "algorithms": [
            {"id": k, "name": v, "available": True}
            for k, v in ALGORITHMS.items()
        ]
    }


@router.get(
    "/{file_id}",
    response_model=MediaFileResponse,
    responses={
        404: {"model": ErrorResponse, "description": "文件不存在"},
    },
)
async def get_file(
    db: DatabaseSession,
    file_id: str,
    current_user: CurrentActiveUser,
) -> MediaFileResponse:
    """获取文件详情"""
    from app.core.deps import get_project_member

    result = await db.execute(select(MediaFile).where(MediaFile.id == file_id))
    media_file = result.scalar_one_or_none()
    if not media_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    # 验证用户是否在项目中
    await get_project_member(db, current_user, str(media_file.project_id))

    return MediaFileResponse.model_validate(media_file)


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse, "description": "文件不存在"},
    },
)
async def delete_file(
    db: DatabaseSession,
    file_id: str,
    current_user: CurrentActiveUser,
) -> None:
    """删除文件"""
    from app.core.deps import require_project_role

    result = await db.execute(select(MediaFile).where(MediaFile.id == file_id))
    media_file = result.scalar_one_or_none()
    if not media_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    # 验证用户权限: 需要 admin 或以上
    await require_project_role(db, current_user, str(media_file.project_id), "admin")

    # Delete from storage backend
    storage = await get_storage_for_file(db, media_file)
    try:
        await storage.delete(media_file.file_path)
    except Exception:
        pass  # 即使存储删除失败也继续清理数据库记录

    # 清理外键引用，防止约束冲突
    await _cleanup_file_references(db, media_file.id)

    await db.delete(media_file)
    await db.commit()


@router.get(
    "/{file_id}/download",
    responses={
        404: {"model": ErrorResponse, "description": "文件不存在"},
    },
)
async def download_file(
    request: Request,
    db: DatabaseSession,
    file_id: str,
    current_user: CurrentUser = None,
    token: Optional[str] = None,  # 允许 ?token= 方式认证（供 <audio>/<video> 直接播放）
):
    """下载/流式播放文件。
    支持两种认证方式：
    1. Authorization: Bearer <token>  (标准，用于 fetch/XHR)
    2. ?token=<jwt>                   (URL 参数，用于 <audio src="..."> 元素)
    """
    # 如果 Bearer 认证未提供但有 ?token= query param，则用其验证身份
    if current_user is None:
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证")
        from app.utils.security import decode_token
        from app.crud.user import user_crud
        payload = decode_token(token)
        if not payload:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")
        user = await user_crud.get_by_uuid(db, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

    result = await db.execute(select(MediaFile).where(MediaFile.id == file_id))
    media_file = result.scalar_one_or_none()
    if not media_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    storage = await get_storage_for_file(db, media_file)

    # 根据文件扩展名推断 MIME 类型，供浏览器内联播放
    ext = os.path.splitext(media_file.file_path)[1].lower()
    mime_map = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".webm": "video/webm",
    }
    media_type = mime_map.get(ext, "application/octet-stream")

    range_header = request.headers.get("range")

    # 本地存储：显式支持 HTTP Range，供 <audio>/<video> seek
    if isinstance(storage, LocalStorageBackend):
        local_path = storage.get_local_path(media_file.file_path)
        if not os.path.exists(local_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件内容不存在")
        return build_file_stream_response(
            path=local_path,
            filename=media_file.original_filename,
            media_type=media_type,
            disposition="inline",
            range_header=range_header,
        )

    # S3/COS 存储：后端代理流式传输，同时补齐 Range 支持
    try:
        data = await storage.get(media_file.file_path)
        return build_bytes_stream_response(
            data=data,
            filename=media_file.original_filename,
            media_type=media_type,
            disposition="inline",
            range_header=range_header,
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件内容不存在")


@router.patch(
    "/{file_id}/type",
    response_model=MediaFileResponse,
    responses={
        404: {"model": ErrorResponse, "description": "文件不存在"},
    },
)
async def update_file_type(
    db: DatabaseSession,
    file_id: str,
    body: FileTypeUpdate,
    current_user: CurrentActiveUser,
) -> MediaFileResponse:
    """修改文件类型"""
    if body.file_type not in VALID_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的文件类型，可选: {', '.join(VALID_FILE_TYPES)}",
        )
    result = await db.execute(select(MediaFile).where(MediaFile.id == file_id))
    media_file = result.scalar_one_or_none()
    if not media_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    media_file.file_type = body.file_type
    await db.flush()
    await db.refresh(media_file)
    await db.commit()
    return MediaFileResponse.model_validate(media_file)


@router.post(
    "/{file_id}/detect",
    responses={
        404: {"model": ErrorResponse, "description": "文件不存在"},
        400: {"model": ErrorResponse, "description": "不支持该文件类型的检测"},
    },
)
async def detect_annotations(
    db: DatabaseSession,
    file_id: str,
    current_user: CurrentActiveUser,
    algorithm: str = Query(
        default="auto",
        description="检测算法: auto | scipy | neurokit2 | wfdb",
    ),
):
    """根据文件类型自动检测并生成标记（S1/S2 或 QRS/P/T）。

    algorithm 参数：
    - `auto`      — 自动选择（ECG: neurokit2, PCG: neurokit2 with fallback）
    - `scipy`     — 内置 SciPy 信号处理（最快，适合快速预览）
    - `neurokit2` — NeuroKit2 AI增强检测（精度更高，支持 ECG 全波形 P/Q/R/S/T）
    - `wfdb`      — PhysioNet WFDB/XQRS 算法（适合标准格式 ECG）
    """
    from app.core.deps import require_project_role

    if algorithm not in ALGORITHMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的算法 '{algorithm}'，可选: {', '.join(ALGORITHMS)}",
        )

    result = await db.execute(select(MediaFile).where(MediaFile.id == file_id))
    media_file = result.scalar_one_or_none()
    if not media_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    # 验证用户权限: 需要 member 或以上
    await require_project_role(db, current_user, str(media_file.project_id), "member")

    storage = await get_storage_for_file(db, media_file)
    file_exists = await storage.exists(media_file.file_path)
    if not file_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件内容不存在")

    config = DETECT_CONFIG.get(media_file.file_type)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件类型 '{media_file.file_type}' 暂不支持自动检测，请先将文件类型设置为 audio/pcg/ecg",
        )

    ext = os.path.splitext(media_file.file_path)[1].lower()
    if ext not in (".wav",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="自动检测仅支持 WAV 格式。MP3/OGG/FLAC 文件在上传时会自动转换为 WAV；"
                   "如果该文件是旧版本上传的，请重新上传以自动转换。",
        )

    # ── 读取 WAV（通过存储服务下载到临时文件）─────────────────────
    import wave as wave_module
    try:
        import numpy as np
        from scipy import signal as sp_signal

        async with temp_local_file(storage, media_file.file_path) as local_path:
            with wave_module.open(local_path, "r") as wf:
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                raw = wf.readframes(n_frames)

        dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
        dtype = dtype_map.get(sampwidth, np.int16)
        pcm = np.frombuffer(raw, dtype=dtype).astype(np.float64)
        if n_channels > 1:
            pcm = pcm[::n_channels]
        max_val = np.max(np.abs(pcm)) or 1.0
        samples = pcm / max_val
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"读取音频失败: {e}")

    duration = n_frames / sample_rate

    # ── 降采样 ──────────────────────────────────────────────────────
    if media_file.file_type in ("pcg", "audio"):
        target_sr = 2000
    else:  # ecg
        target_sr = 500

    if sample_rate != target_sr:
        from math import gcd
        g = gcd(sample_rate, target_sr)
        sig = sp_signal.resample_poly(samples, target_sr // g, sample_rate // g)
    else:
        sig = samples.copy()
    work_sr = target_sr

    # ── 算法分派 ──────────────────────────────────────────────────
    algo = algorithm
    if algo == "auto":
        # 默认首选 neurokit2（精度最高），wfdb 仅适合 ECG
        algo = "neurokit2"

    if media_file.file_type in ("pcg", "audio"):
        if algo == "neurokit2":
            detected = pcg_detect_neurokit2(sig, work_sr, duration)
        else:
            detected = pcg_detect_scipy(sig, work_sr, duration)
    else:  # ecg
        if algo == "neurokit2":
            detected = ecg_detect_neurokit2(sig, work_sr, duration)
        elif algo == "wfdb":
            detected = ecg_detect_wfdb(sig, work_sr, duration)
        else:
            detected = ecg_detect_scipy(sig, work_sr, duration)

    # ── 写入数据库（先删除同文件的旧 auto 标记） ──────────────────
    del_stmt = select(Annotation).where(
        Annotation.file_id == file_id,
        Annotation.source == "auto",
    )
    old = (await db.execute(del_stmt)).scalars().all()
    for o in old:
        await db.delete(o)

    created = []
    for d in detected:
        ann = Annotation(
            file_id=uuid.UUID(file_id),
            user_id=current_user.id,
            annotation_type=d["annotation_type"],
            start_time=d["start_time"],
            end_time=d["end_time"],
            confidence=d["confidence"],
            label=d["label"],
            source=d["source"],
        )
        db.add(ann)
        created.append(ann)

    await db.flush()
    for ann in created:
        await db.refresh(ann)
    await db.commit()

    from app.schemas.project import AnnotationResponse
    return {
        "file_id": file_id,
        "file_type": media_file.file_type,
        "algorithm_used": algo,
        "detected_count": len(created),
        "items": [AnnotationResponse.model_validate(a).model_dump() for a in created],
    }


# ─────────────────────────────────────────────────────────────────────────────
# BPM 突变检测与自适应重探查
# ─────────────────────────────────────────────────────────────────────────────

def _compute_bpm_analysis(
    beat_times: list[float],
    change_threshold: float = 0.20,
) -> dict:
    """
    从心搏时刻序列计算 BPM 分析结果：
    - 全局 BPM 统计（mean / median / min / max / std）
    - 逐拍瞬时 BPM 时间序列
    - 突变检测（相邻 RR 间期变化 > threshold）
    - 突变段索引（用于自适应重探查）
    """
    import numpy as np

    if len(beat_times) < 2:
        return {
            "beat_count": len(beat_times),
            "rr_intervals": [],
            "instant_bpm": [],
            "bpm_times": [],
            "mean_bpm": 0, "median_bpm": 0, "min_bpm": 0, "max_bpm": 0, "std_bpm": 0,
            "anomalies": [],
            "anomaly_count": 0,
            "anomaly_segments": [],
        }

    times = np.array(sorted(beat_times))
    rr = np.diff(times)  # RR intervals in seconds

    # 过滤掉不合理的 RR（< 0.2s = 300bpm 或 > 3s = 20bpm）
    valid_mask = (rr >= 0.2) & (rr <= 3.0)
    rr_valid = rr[valid_mask]

    if len(rr_valid) == 0:
        return {
            "beat_count": len(beat_times),
            "rr_intervals": rr.tolist(),
            "instant_bpm": [],
            "bpm_times": [],
            "mean_bpm": 0, "median_bpm": 0, "min_bpm": 0, "max_bpm": 0, "std_bpm": 0,
            "anomalies": [],
            "anomaly_count": 0,
            "anomaly_segments": [],
        }

    bpm = 60.0 / rr_valid
    bpm_times = ((times[:-1] + times[1:]) / 2)[valid_mask]  # 中点时间

    # ── 突变检测 ──────────────────────────────────────────────────
    anomalies = []
    for i in range(1, len(rr)):
        if rr[i - 1] <= 0 or rr[i] <= 0:
            continue
        ratio = abs(rr[i] - rr[i - 1]) / rr[i - 1]
        if ratio > change_threshold:
            bpm_before = 60.0 / rr[i - 1] if rr[i - 1] > 0 else 0
            bpm_after = 60.0 / rr[i] if rr[i] > 0 else 0
            anomalies.append({
                "beat_index": int(i),
                "time": round(float(times[i]), 4),
                "rr_before": round(float(rr[i - 1]), 4),
                "rr_after": round(float(rr[i]), 4),
                "bpm_before": round(float(bpm_before), 1),
                "bpm_after": round(float(bpm_after), 1),
                "change_ratio": round(float(ratio), 4),
                "type": "acceleration" if rr[i] < rr[i - 1] else "deceleration",
            })

    # ── 突变段合并（用于自适应重探查）──────────────────────────────
    # 把相邻突变点聚合为连续区间段，前后各扩展 0.5 秒
    anomaly_segments = []
    if anomalies:
        seg_start = anomalies[0]["time"] - 0.5
        seg_end = anomalies[0]["time"] + 0.5
        for a in anomalies[1:]:
            if a["time"] - seg_end < 1.0:
                # 合并到当前段
                seg_end = a["time"] + 0.5
            else:
                anomaly_segments.append({
                    "start": round(max(0.0, seg_start), 4),
                    "end": round(seg_end, 4),
                })
                seg_start = a["time"] - 0.5
                seg_end = a["time"] + 0.5
        anomaly_segments.append({
            "start": round(max(0.0, seg_start), 4),
            "end": round(seg_end, 4),
        })

    return {
        "beat_count": len(beat_times),
        "rr_intervals": [round(float(x), 4) for x in rr.tolist()],
        "instant_bpm": [round(float(x), 1) for x in bpm.tolist()],
        "bpm_times": [round(float(x), 4) for x in bpm_times.tolist()],
        "mean_bpm": round(float(np.mean(bpm)), 1),
        "median_bpm": round(float(np.median(bpm)), 1),
        "min_bpm": round(float(np.min(bpm)), 1),
        "max_bpm": round(float(np.max(bpm)), 1),
        "std_bpm": round(float(np.std(bpm)), 2),
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
        "anomaly_segments": anomaly_segments,
    }


def _read_wav_segment(file_path: str, t0: float, t1: float):
    """读取 WAV 文件的一段 PCM 数据，返回 (signal_float64, sample_rate)"""
    import wave as wave_module
    import numpy as np

    with wave_module.open(file_path, "r") as wf:
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        n_ch = wf.getnchannels()
        sw = wf.getsampwidth()

        frame_start = max(0, int(t0 * sr))
        frame_end = min(n_frames, int(t1 * sr))
        wf.setpos(frame_start)
        raw = wf.readframes(frame_end - frame_start)

    dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
    dtype = dtype_map.get(sw, np.int16)
    pcm = np.frombuffer(raw, dtype=dtype).astype(np.float64)
    if n_ch > 1:
        pcm = pcm[::n_ch]
    mx = np.max(np.abs(pcm)) or 1.0
    return pcm / mx, sr


@router.post(
    "/{file_id}/analyze",
    responses={
        404: {"model": ErrorResponse, "description": "文件不存在"},
        400: {"model": ErrorResponse, "description": "无法分析"},
    },
    summary="BPM 分析 + 突变检测 + 自适应重探查",
)
async def analyze_bpm(
    db: DatabaseSession,
    file_id: str,
    current_user: CurrentActiveUser,
    change_threshold: float = Query(
        default=0.20,
        ge=0.05,
        le=1.0,
        description="RR 间期突变阈值（相对变化率），默认 0.20 即 20%",
    ),
    auto_redetect: bool = Query(
        default=True,
        description="是否对突变段自动使用高精度算法重新检测",
    ),
):
    """
    基于已检测的心搏标记（QRS 或 S1）进行 BPM 分析：

    1. **BPM 统计**：均值/中位数/最值/标准差
    2. **逐拍 BPM 序列**：可用于前端绘制 BPM 趋势图
    3. **突变检测**：相邻 RR 间期变化超过阈值的位置
    4. **自适应重探查**：对突变段使用 neurokit2 高精度算法重新检测

    注意：需要先运行 `POST /files/{file_id}/detect` 生成标记。
    """
    from app.models.project import AnalysisResult

    result = await db.execute(select(MediaFile).where(MediaFile.id == file_id))
    media_file = result.scalar_one_or_none()
    if not media_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    # ── 获取心搏标记 ──────────────────────────────────────────────
    # ECG 使用 QRS，PCG/audio 使用 S1
    if media_file.file_type == "ecg":
        beat_type = "qrs"
    elif media_file.file_type in ("pcg", "audio"):
        beat_type = "s1"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件类型 '{media_file.file_type}' 不支持 BPM 分析",
        )

    ann_result = await db.execute(
        select(Annotation)
        .where(Annotation.file_id == file_id, Annotation.annotation_type == beat_type)
        .order_by(Annotation.start_time)
    )
    annotations = ann_result.scalars().all()

    if len(annotations) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"心搏标记不足（{beat_type.upper()}: {len(annotations)} 个）。"
                   f"请先运行 POST /files/{file_id}/detect 检测标记。",
        )

    # 取标记的中点时刻作为心搏时刻
    beat_times = [
        (float(a.start_time) + float(a.end_time)) / 2.0
        for a in annotations
    ]

    # ── 第一轮 BPM 分析 ──────────────────────────────────────────
    analysis = _compute_bpm_analysis(beat_times, change_threshold)

    # ── 自适应重探查 ─────────────────────────────────────────────
    redetected_segments = []

    if auto_redetect and analysis["anomaly_segments"]:
        storage = await get_storage_for_file(db, media_file)
        file_exists = await storage.exists(media_file.file_path)
        ext = os.path.splitext(media_file.file_path)[1].lower()
        if file_exists and ext == ".wav":
            import numpy as np
            from scipy import signal as sp_signal

            async with temp_local_file(storage, media_file.file_path) as local_path:
                for seg in analysis["anomaly_segments"]:
                    t0, t1 = seg["start"], seg["end"]
                    # 前后各扩展 1 秒的上下文
                    t0_ctx = max(0.0, t0 - 1.0)
                    t1_ctx = t1 + 1.0

                    try:
                        sig_seg, seg_sr = _read_wav_segment(local_path, t0_ctx, t1_ctx)
                        seg_dur = len(sig_seg) / seg_sr

                        # 降采样到工作采样率
                        if media_file.file_type == "ecg":
                            target_sr = 500
                        else:
                            target_sr = 2000

                        if seg_sr != target_sr:
                            from math import gcd
                            g = gcd(seg_sr, target_sr)
                            sig_seg = sp_signal.resample_poly(sig_seg, target_sr // g, seg_sr // g)
                        work_sr = target_sr

                        # 使用 neurokit2 高精度算法重新检测
                        if media_file.file_type == "ecg":
                            new_anns = ecg_detect_neurokit2(sig_seg, work_sr, seg_dur)
                        else:
                            new_anns = pcg_detect_neurokit2(sig_seg, work_sr, seg_dur)

                        # 偏移到全局时间轴
                        new_beat_times = []
                        for a in new_anns:
                            if a["annotation_type"] == beat_type:
                                global_t = (a["start_time"] + a["end_time"]) / 2.0 + t0_ctx
                                new_beat_times.append(global_t)

                        if len(new_beat_times) >= 2:
                            seg_analysis = _compute_bpm_analysis(new_beat_times, change_threshold)
                            redetected_segments.append({
                                "segment": seg,
                                "original_anomaly_count": len([
                                    a for a in analysis["anomalies"]
                                    if seg["start"] <= a["time"] <= seg["end"]
                                ]),
                                "redetected_beat_count": len(new_beat_times),
                                "redetected_mean_bpm": seg_analysis["mean_bpm"],
                                "remaining_anomalies": seg_analysis["anomaly_count"],
                                "conclusion": (
                                    "false_positive"
                                    if seg_analysis["anomaly_count"] == 0
                                    else "confirmed_anomaly"
                                ),
                            })

                    except Exception:
                        pass  # 单段失败不影响整体结果

    # ── 写入 AnalysisResult ──────────────────────────────────────
    result_data = {
        **analysis,
        "change_threshold": change_threshold,
        "auto_redetect": auto_redetect,
        "redetected_segments": redetected_segments,
    }

    # 删除旧的 BPM 分析结果
    old_results = await db.execute(
        select(AnalysisResult).where(
            AnalysisResult.file_id == file_id,
            AnalysisResult.analysis_type == "bpm",
        )
    )
    for old in old_results.scalars().all():
        await db.delete(old)

    ar = AnalysisResult(
        file_id=uuid.UUID(file_id),
        analysis_type="bpm",
        result_data=result_data,
    )
    db.add(ar)
    await db.commit()
    await db.refresh(ar)

    return {
        "analysis_id": str(ar.id),
        "file_id": file_id,
        "file_type": media_file.file_type,
        "beat_type": beat_type,
        **result_data,
    }


@router.get(
    "/{file_id}/waveform",
    responses={
        404: {"model": ErrorResponse, "description": "文件不存在"},
    },
)
async def get_waveform(
    db: DatabaseSession,
    file_id: str,
    current_user: CurrentActiveUser,
    max_points: int = 1000,
    start_time: float = None,
    end_time: float = None,
):
    """获取波形数据。支持 start_time/end_time 区间参数，仅读取指定时间段的 PCM，
    大幅提升长音频放大查看时的分辨率（相比固定全文件降采）。"""
    result = await db.execute(select(MediaFile).where(MediaFile.id == file_id))
    media_file = result.scalar_one_or_none()
    if not media_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    storage = await get_storage_for_file(db, media_file)
    file_exists = await storage.exists(media_file.file_path)
    if not file_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件内容不存在")

    # Try to read audio waveform using wave module for WAV files
    ext = os.path.splitext(media_file.file_path)[1].lower()
    samples = []
    sample_rate = media_file.sample_rate or 44100
    duration = media_file.duration or 0
    region_start = 0.0
    region_end = duration

    if ext == ".wav":
        try:
            import wave
            import numpy as _np
            async with temp_local_file(storage, media_file.file_path) as local_path:
                with wave.open(local_path, "r") as wf:
                    sample_rate = wf.getframerate()
                    n_frames = wf.getnframes()
                    n_channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    total_duration = n_frames / sample_rate
                    duration = total_duration

                    # 计算区间帧范围（支持按需读取，避免全文件加载）
                    t0 = max(0.0, float(start_time)) if start_time is not None else 0.0
                    t1 = min(total_duration, float(end_time)) if end_time is not None else total_duration
                    if t1 <= t0:
                        t1 = total_duration
                    frame_start = int(t0 * sample_rate)
                    frame_end = min(n_frames, int(t1 * sample_rate))
                    region_frames = frame_end - frame_start
                    region_start = t0
                    region_end = frame_end / sample_rate

                    # 定位并只读取目标区间
                    wf.setpos(frame_start)
                    raw = wf.readframes(region_frames)

                    # 解析 PCM（支持 8/16/32-bit）
                    dtype_map = {1: _np.int8, 2: _np.int16, 4: _np.int32}
                    dtype = dtype_map.get(sampwidth, _np.int16)
                    samples_raw = _np.frombuffer(raw, dtype=dtype)
                    # 取第一声道
                    if n_channels > 1:
                        samples_raw = samples_raw[::n_channels]
                    # 归一化为 [-1, 1]
                    max_val = float(_np.max(_np.abs(samples_raw))) if len(samples_raw) > 0 else 1.0
                    if max_val == 0.0:
                        max_val = 1.0
                    normalized = (samples_raw / max_val).astype(_np.float32)

                    total = len(normalized)
                    if total <= max_points:
                        # 样本数本来就少，直接全量返回
                        samples = normalized.tolist()
                    else:
                        # Min-Max 降采：每个输出点对应一段原始样本，取绝对值最大的样本
                        # 保留所有峰值，波形视觉上更真实（特别对高频PCG信号）
                        step = total / max_points
                        result_pts = []
                        for i in range(max_points):
                            lo = int(i * step)
                            hi = int((i + 1) * step)
                            if hi > total:
                                hi = total
                            chunk = normalized[lo:hi]
                            if len(chunk) == 0:
                                result_pts.append(0.0)
                            else:
                                idx = int(_np.argmax(_np.abs(chunk)))
                                result_pts.append(float(chunk[idx]))
                        samples = result_pts
        except Exception:
            pass

    return {
        "file_id": file_id,
        "sample_rate": sample_rate,
        "duration": duration,
        "region_start": region_start,
        "region_end": region_end,
        "num_samples": len(samples),
        "samples": samples,
    }
