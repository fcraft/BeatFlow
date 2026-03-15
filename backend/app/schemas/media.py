"""媒体文件相关 Pydantic schemas"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class MediaType(str, Enum):
    """媒体文件类型枚举"""
    AUDIO = "audio"     # 音频文件（WAV, MP3）
    VIDEO = "video"     # 视频文件（MP4, AVI）
    ECG = "ecg"        # 心电图文件
    PCG = "pcg"        # 心音图文件
