"""
网络数据本地缓存模块。

将 Bangumi 拉取的剧集数据（episodes）按 subject_id 持久化到本地 JSON 文件，
避免每次进入逻辑媒体库都要重新网络请求。

缓存目录：项目根目录下的 cache/ 文件夹
"""
import json
import os
import time
from pathlib import Path
from utils.logger import logger
from utils.path_resolver import get_resource_path


# 缓存目录：项目根目录下的 cache/
CACHE_DIR = get_resource_path("cache")
# 缓存永久有效，不再设置过期时间


def _ensure_cache_dir():
    """确保缓存目录存在"""
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(subject_id: int) -> str:
    """返回某个 subject_id 对应的缓存文件路径"""
    return os.path.join(CACHE_DIR, f"episodes_{subject_id}.json")


def get_cached_episodes(subject_id: int) -> list | None:
    """
    读取本地缓存的剧集数据。
    缓存永久有效，不会自动过期。
    """
    cache_file = _cache_path(subject_id)
    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        episodes = data.get("episodes", [])
        logger.info(f"命中本地缓存 (subject_id={subject_id})，共 {len(episodes)} 集")
        return episodes

    except Exception as e:
        logger.warning(f"读取缓存失败 (subject_id={subject_id}): {e}")
        return None


def save_cached_episodes(subject_id: int, episodes: list):
    """
    将剧集数据持久化到本地缓存。
    """
    _ensure_cache_dir()
    cache_file = _cache_path(subject_id)

    try:
        data = {
            "cached_at": time.time(),
            "subject_id": subject_id,
            "episodes": episodes
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"剧集数据已缓存到本地 (subject_id={subject_id}, {len(episodes)} 集)")
    except Exception as e:
        logger.warning(f"写入缓存失败 (subject_id={subject_id}): {e}")


def get_cache_size() -> str:
    """
    计算缓存目录的总大小，返回人类可读的字符串（如 "12.34 MB"）。
    如果缓存目录不存在，返回 "0 B"。
    """
    if not os.path.exists(CACHE_DIR):
        return "0 B"

    total_bytes = 0
    for fname in os.listdir(CACHE_DIR):
        fpath = os.path.join(CACHE_DIR, fname)
        if os.path.isfile(fpath):
            total_bytes += os.path.getsize(fpath)

    # 转换为人类可读格式
    for unit in ['B', 'KB', 'MB', 'GB']:
        if total_bytes < 1024:
            return f"{total_bytes:.2f} {unit}"
        total_bytes /= 1024
    return f"{total_bytes:.2f} GB"


def clear_all_cache() -> int:
    """
    清空所有缓存文件。
    返回被删除的文件数量。
    """
    if not os.path.exists(CACHE_DIR):
        return 0

    count = 0
    for fname in os.listdir(CACHE_DIR):
        fpath = os.path.join(CACHE_DIR, fname)
        if os.path.isfile(fpath):
            try:
                os.remove(fpath)
                count += 1
            except Exception as e:
                logger.warning(f"删除缓存文件失败 {fpath}: {e}")

    logger.info(f"已清除 {count} 个缓存文件")
    return count
