# 文件路径: models/media_entity.py

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

class MediaType(Enum):
    MOVIE = "movie"
    TV_SHOW = "tv_show"
    EPISODE = "episode"
    UNKNOWN = "unknown"

@dataclass
class MediaEntity:
    """所有影视元数据的基类"""
    file_path: str = ""                # 原始文件完整路径
    original_filename: str = ""        # 原始文件名
    media_type: MediaType = MediaType.UNKNOWN
    
    # 解析出的基础信息
    title: str = ""                    # 影视名称
    year: Optional[int] = None         # 年份
    resolution: Optional[str] = None   # 分辨率 (如 1080p, 4K)
    video_codec: Optional[str] = None  # 视频编码 (如 x264, HEVC)
    audio_codec: Optional[str] = None  # 音频编码 (如 AAC, FLAC)
    release_group: Optional[str] = None # 压制组/发布组
    
    # 刮削后补充的信息 (准备写入 NFO 的数据)
    tmdb_id: Optional[int] = None      # TMDB 唯一标识符
    plot: str = ""                     # 剧情简介
    poster_path: str = ""              # 海报本地或网络路径
    genres: List[str] = field(default_factory=list) # 类型标签

@dataclass
class Movie(MediaEntity):
    """电影实体"""
    def __post_init__(self):
        self.media_type = MediaType.MOVIE

@dataclass
class Episode(MediaEntity):
    """单集数据模型"""
    ep_number: float          # 集数 (可能存在 SP0.5 这种，所以用 float，但通常是 int)
    title: str                # 单集标题 (通常是日文/中文标题)
    summary: str = ""         # 单集简介
    air_date: str = ""        # 播出日期
    local_file_path: str = "" # 【核心枢纽】：绑定的本地物理文件路径

@dataclass
class TVShow(MediaEntity):
    """剧集数据模型 (已升级)"""
    id: int
    title: str
    original_title: str = ""
    year: str = ""
    plot: str = ""
    poster_url: str = ""
    # 新增：包含的单集列表
    episodes: List[Episode] = field(default_factory=list)