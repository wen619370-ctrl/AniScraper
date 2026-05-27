"""
图片缓存管理模块。

管理从网络下载的海报图片（poster.jpg, folder.jpg 等）的本地缓存。
提供缓存大小统计、清理等功能。
"""
import os
import shutil
from pathlib import Path
from utils.logger import logger
from utils.path_resolver import get_resource_path


# 图片缓存目录：项目根目录下的 cache/images/
IMAGE_CACHE_DIR = get_resource_path("cache/images")


def _ensure_cache_dir():
    """确保图片缓存目录存在"""
    os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)


def get_image_cache_size() -> str:
    """
    计算图片缓存目录的总大小，返回人类可读的字符串。
    如果缓存目录不存在，返回 "0 B"。
    """
    if not os.path.exists(IMAGE_CACHE_DIR):
        return "0 B"

    total_bytes = 0
    for fname in os.listdir(IMAGE_CACHE_DIR):
        fpath = os.path.join(IMAGE_CACHE_DIR, fname)
        if os.path.isfile(fpath):
            total_bytes += os.path.getsize(fpath)

    for unit in ['B', 'KB', 'MB', 'GB']:
        if total_bytes < 1024:
            return f"{total_bytes:.2f} {unit}"
        total_bytes /= 1024
    return f"{total_bytes:.2f} GB"


def get_image_cache_count() -> int:
    """返回图片缓存文件数量"""
    if not os.path.exists(IMAGE_CACHE_DIR):
        return 0
    return len([f for f in os.listdir(IMAGE_CACHE_DIR) if os.path.isfile(os.path.join(IMAGE_CACHE_DIR, f))])


def clear_image_cache() -> int:
    """
    清空所有图片缓存文件。
    返回被删除的文件数量。
    """
    if not os.path.exists(IMAGE_CACHE_DIR):
        return 0

    count = 0
    for fname in os.listdir(IMAGE_CACHE_DIR):
        fpath = os.path.join(IMAGE_CACHE_DIR, fname)
        if os.path.isfile(fpath):
            try:
                os.remove(fpath)
                count += 1
            except Exception as e:
                logger.warning(f"删除图片缓存文件失败 {fpath}: {e}")

    logger.info(f"已清除 {count} 个图片缓存文件")
    return count


def cache_poster_image(subject_id: int, image_data: bytes) -> str | None:
    """
    将海报图片缓存到本地。
    返回缓存文件路径，失败返回 None。
    """
    _ensure_cache_dir()
    cache_path = os.path.join(IMAGE_CACHE_DIR, f"poster_{subject_id}.jpg")
    try:
        with open(cache_path, 'wb') as f:
            f.write(image_data)
        logger.info(f"海报图片已缓存 (subject_id={subject_id})")
        return cache_path
    except Exception as e:
        logger.warning(f"缓存海报图片失败 (subject_id={subject_id}): {e}")
        return None


def get_cached_poster_path(subject_id: int) -> str | None:
    """获取已缓存的海报图片路径，不存在返回 None"""
    cache_path = os.path.join(IMAGE_CACHE_DIR, f"poster_{subject_id}.jpg")
    return cache_path if os.path.exists(cache_path) else None
