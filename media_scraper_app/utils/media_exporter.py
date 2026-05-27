"""
媒体库导出/导入模块。

将已刮削的媒体库（NFO 元数据 + 海报图片）打包导出为 ZIP 文件，
方便迁移到其他媒体服务器（如 Jellyfin、Plex）或备份。
"""
import os
import json
import zipfile
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from utils.logger import logger
from utils.config_loader import ConfigLoader


# 支持的图片扩展名
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


def export_media_library(export_path: str, library_paths: list[str] = None) -> dict:
    """
    导出媒体库的刮削数据（NFO + 海报图片）到 ZIP 文件。

    Args:
        export_path: 导出 ZIP 文件的目标路径
        library_paths: 要导出的媒体库根目录列表，为 None 时从配置读取

    Returns:
        dict: {"success": bool, "message": str, "file_count": int, "export_path": str}
    """
    if library_paths is None:
        config = ConfigLoader()
        library_paths = [lib['path'] for lib in config.get_libraries()]

    if not library_paths:
        return {"success": False, "message": "没有配置任何媒体库，无法导出", "file_count": 0, "export_path": ""}

    temp_dir = tempfile.mkdtemp(prefix="aniscraper_export_")
    file_count = 0

    try:
        # 收集所有已刮削的目录
        scraped_dirs = []
        for lib_path in library_paths:
            lib_root = Path(lib_path)
            if not lib_root.exists():
                logger.warning(f"媒体库路径不存在，跳过: {lib_path}")
                continue

            # 递归查找所有包含 tvshow.nfo 的目录
            for nfo_path in lib_root.rglob('tvshow.nfo'):
                show_dir = nfo_path.parent
                scraped_dirs.append(show_dir)
                logger.info(f"发现已刮削目录: {show_dir}")

        if not scraped_dirs:
            return {"success": False, "message": "未找到任何已刮削的目录（没有 tvshow.nfo）", "file_count": 0, "export_path": ""}

        # 将每个已刮削目录复制到临时目录
        for show_dir in scraped_dirs:
            # 保持相对路径结构
            rel_path = show_dir.relative_to(lib_root) if show_dir.is_relative_to(lib_root) else show_dir.name
            dest_dir = Path(temp_dir) / rel_path
            dest_dir.mkdir(parents=True, exist_ok=True)

            # 复制 NFO 文件
            for nfo_file in show_dir.glob('*.nfo'):
                shutil.copy2(nfo_file, dest_dir / nfo_file.name)
                file_count += 1

            # 复制图片文件
            for img_ext in IMAGE_EXTS:
                for img_file in show_dir.glob(f'*{img_ext}'):
                    shutil.copy2(img_file, dest_dir / img_file.name)
                    file_count += 1

            # 递归复制子目录中的 NFO 和图片（如 Season 1/ 中的单集 NFO）
            for sub_dir in show_dir.iterdir():
                if sub_dir.is_dir():
                    for nfo_file in sub_dir.rglob('*.nfo'):
                        rel_sub_path = nfo_file.relative_to(show_dir)
                        dest_sub_path = dest_dir / rel_sub_path
                        dest_sub_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(nfo_file, dest_sub_path)
                        file_count += 1

                    for img_ext in IMAGE_EXTS:
                        for img_file in sub_dir.rglob(f'*{img_ext}'):
                            rel_sub_path = img_file.relative_to(show_dir)
                            dest_sub_path = dest_dir / rel_sub_path
                            dest_sub_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(img_file, dest_sub_path)
                            file_count += 1

        # 生成导出清单
        manifest = {
            "exported_at": datetime.now().isoformat(),
            "aniscraper_version": "v1.0",
            "show_count": len(scraped_dirs),
            "file_count": file_count,
            "shows": [str(s.relative_to(lib_root) if s.is_relative_to(lib_root) else s.name) for s in scraped_dirs]
        }
        manifest_path = Path(temp_dir) / "export_manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # 打包为 ZIP
        with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zf.write(file_path, arcname)

        logger.info(f"媒体库导出成功: {export_path}，共 {file_count} 个文件，{len(scraped_dirs)} 部剧集")
        return {
            "success": True,
            "message": f"导出成功！共 {file_count} 个文件，{len(scraped_dirs)} 部剧集",
            "file_count": file_count,
            "show_count": len(scraped_dirs),
            "export_path": export_path
        }

    except Exception as e:
        logger.error(f"导出媒体库失败: {e}")
        return {"success": False, "message": f"导出失败: {str(e)}", "file_count": 0, "export_path": ""}

    finally:
        # 清理临时目录
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


def import_media_library(import_path: str, target_dir: str) -> dict:
    """
    从 ZIP 文件导入刮削数据到指定目录。

    Args:
        import_path: ZIP 文件路径
        target_dir: 目标媒体库根目录

    Returns:
        dict: {"success": bool, "message": str, "file_count": int, "show_count": int}
    """
    if not os.path.exists(import_path):
        return {"success": False, "message": f"导入文件不存在: {import_path}", "file_count": 0, "show_count": 0}

    if not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception as e:
            return {"success": False, "message": f"无法创建目标目录: {str(e)}", "file_count": 0, "show_count": 0}

    temp_dir = tempfile.mkdtemp(prefix="aniscraper_import_")
    file_count = 0
    show_count = 0

    try:
        # 解压到临时目录
        with zipfile.ZipFile(import_path, 'r') as zf:
            zf.extractall(temp_dir)

        # 读取清单
        manifest_path = Path(temp_dir) / "export_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                show_count = manifest.get("show_count", 0)
            except Exception:
                pass

        # 复制文件到目标目录
        for root, dirs, files in os.walk(temp_dir):
            # 跳过清单文件
            if "export_manifest.json" in files:
                files.remove("export_manifest.json")

            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, temp_dir)
                dest_path = os.path.join(target_dir, rel_path)

                # 创建目标目录
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                # 复制文件（不覆盖已存在的）
                if not os.path.exists(dest_path):
                    shutil.copy2(src_path, dest_path)
                    file_count += 1
                else:
                    logger.info(f"文件已存在，跳过: {dest_path}")

        logger.info(f"媒体库导入成功: 共 {file_count} 个文件")
        return {
            "success": True,
            "message": f"导入成功！共 {file_count} 个文件",
            "file_count": file_count,
            "show_count": show_count
        }

    except Exception as e:
        logger.error(f"导入媒体库失败: {e}")
        return {"success": False, "message": f"导入失败: {str(e)}", "file_count": 0, "show_count": 0}

    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
