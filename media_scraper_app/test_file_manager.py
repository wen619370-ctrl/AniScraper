# 临时测试脚本: test_file_manager.py

import os
from pathlib import Path
from core.file_manager import FileManager
from utils.logger import logger

def run_test():
    # 1. 测试文件名清理 (防御性)
    dirty_name = 'Fate/Stay Night: Unlimited Blade Works <1080p> *BDRip?.mkv'
    clean_name = FileManager.sanitize_filename(dirty_name)
    logger.info(f"原始文件名: {dirty_name}")
    logger.info(f"清理后文件名: {clean_name}")

    # 准备沙盒测试目录
    sandbox_dir = Path("sandbox_test")
    sandbox_dir.mkdir(exist_ok=True)
    
    # 创建一个虚拟的原始媒体文件
    dummy_src = sandbox_dir / "dummy_download.mkv"
    dummy_src.write_text("This is a dummy video file.")
    
    # 2. 测试硬链接/复制逻辑
    dest_video_path = sandbox_dir / "Anime_Library" / clean_name
    try:
        FileManager.create_hardlink_or_copy(str(dummy_src), str(dest_video_path))
    except Exception as e:
        logger.error(f"文件转移失败: {e}")

    # 3. 测试 NFO 生成逻辑 (兼容 Jellyfin/Emby)
    nfo_data = {
        "type": "movie",
        "title": "Fate/Stay Night UBW",
        "plot": "远坂凛与卫宫士郎参与圣杯战争的故事...",
        "year": "2014",
        "thumb": "https://example.com/poster.jpg"
    }
    
    # NFO 文件通常与视频文件同名，后缀改为 .nfo
    dest_nfo_path = dest_video_path.with_suffix(".nfo")
    try:
        FileManager.generate_nfo(nfo_data, str(dest_nfo_path))
    except Exception as e:
        logger.error(f"NFO 生成失败: {e}")

    logger.info("沙盒测试完成。请检查 sandbox_test 目录内的结果！")

if __name__ == "__main__":
    run_test()