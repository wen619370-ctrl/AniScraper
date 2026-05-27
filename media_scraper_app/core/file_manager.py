
# 文件路径: core/file_manager.py

import os
import re
import errno
import shutil
import xml.etree.ElementTree as ET
import xml.dom.minidom
from pathlib import Path
from typing import List, Dict, Optional, Any

from utils.logger import logger
from utils.exceptions import FileOperationError
from utils.config_loader import ConfigLoader


class FileManager:
    """
    核心文件系统操作类。
    负责本地物理文件的重命名、跨盘硬链接/复制，以及兼容 Emby/Jellyfin 标准的 NFO 生成。
    完全脱离 GUI 环境，保证绝对解耦。
    """
    VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.rmvb', '.flv', '.ts', '.wmv', '.iso'}

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """
        清理文件名中的非法字符，防止在 Windows/Linux 文件系统上创建文件失败。
        将 < > : " / \\ | ? * 替换为单个空格，并去除首尾多余空白。
        
        Args:
            name: 原始文件名
            
        Returns:
            清理后的文件名
        """
        if not name:
            return "Unknown"
        clean_name = re.sub(r'[<>:"/\\|?*]', ' ', name)
        return re.sub(r'\s+', ' ', clean_name).strip()

    @staticmethod
    def create_hardlink_or_copy(src_path: str, dest_path: str) -> bool:
        """
        将源文件转移到目标路径。优先尝试创建硬链接 (Hardlink)，若失败（如跨盘），则降级为物理复制。
        如果目标文件已存在，则安全跳过。
        
        Args:
            src_path: 源文件路径
            dest_path: 目标文件路径
            
        Returns:
            操作是否成功
            
        Raises:
            FileOperationError: 当文件操作失败时
        """
        src = Path(src_path)
        dest = Path(dest_path)

        if not src.exists() or not src.is_file():
            raise FileOperationError(
                filepath=src_path, 
                operation="读取源文件", 
                details="源文件不存在或不是标准文件"
            )

        if dest.exists():
            logger.info(f"目标文件已存在，跳过操作: {dest}")
            return True

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise FileOperationError(
                filepath=str(dest.parent), 
                operation="创建目录", 
                details=f"权限不足或路径无效 ({str(e)})"
            )

        try:
            logger.debug(f"尝试为 {src.name} 创建硬链接...")
            os.link(src, dest)
            logger.info(f"硬链接创建成功: {dest}")
            return True

        except OSError as e:
            if e.errno == errno.EXDEV:
                logger.warning(
                    f"触发跨盘/设备限制，硬链接失败，正在自动降级为物理复制: "
                    f"{src.name} -> {dest.parent}"
                )
                try:
                    shutil.copy2(src, dest)
                    logger.info(f"物理复制成功: {dest}")
                    return True
                except Exception as copy_e:
                    raise FileOperationError(
                        filepath=str(dest), 
                        operation="降级复制", 
                        details=str(copy_e)
                    )
            else:
                raise FileOperationError(
                    filepath=str(dest), 
                    operation="硬链接", 
                    details=str(e)
                )
        except Exception as e:
            raise FileOperationError(
                filepath=str(dest), 
                operation="文件转移", 
                details=str(e)
            )

    @staticmethod
    def generate_nfo(media_data: Dict[str, Any], dest_dir: str, overwrite: bool = False) -> bool:
        """
        生成兼容 Emby/Jellyfin 标准的 NFO 元数据文件。
        【终极平铺架构】：不再生成全局唯一的 tvshow.nfo，而是生成带有 bangumi_id 的专属 NFO。
        例如：tvshow_12345.nfo。这样同一个目录下可以共存无数个 TV 动画和剧场版。
        
        Args:
            media_data: 包含标题、简介、年份等元数据的字典
            dest_dir: 目标目录路径
            overwrite: 是否覆盖已存在的 NFO 文件
            
        Returns:
            是否成功生成 NFO 文件
        """
        bangumi_id = media_data.get("id")
        if not bangumi_id:
            logger.error("生成 NFO 失败：缺少 bangumi_id，无法生成专属 NFO 文件名。")
            return False
            
        nfo_filename = f"tvshow_{bangumi_id}.nfo"
        nfo_path = Path(dest_dir) / nfo_filename

        # 如果目标路径是一个文件夹（极小概率），先删除它
        if nfo_path.exists():
            if nfo_path.is_dir():
                logger.warning(f"检测到 {nfo_path} 是一个文件夹，正在删除以释放路径...")
                shutil.rmtree(nfo_path)
            elif not overwrite:
                return True

        try:
            nfo_path.parent.mkdir(parents=True, exist_ok=True)

            root = ET.Element("tvshow")

            title = media_data.get("name_cn") or media_data.get("name") or media_data.get("title", "未知标题")
            ET.SubElement(root, "title").text = str(title)

            original_title = media_data.get("name") or ""
            if original_title and original_title != title:
                ET.SubElement(root, "originaltitle").text = str(original_title)

            plot = media_data.get("summary") or media_data.get("plot", "")
            if plot:
                ET.SubElement(root, "plot").text = str(plot)

            date = media_data.get("air_date", "")
            year = date[:4] if date else str(media_data.get("year", ""))
            if year:
                ET.SubElement(root, "year").text = str(year)
            if date:
                ET.SubElement(root, "premiered").text = str(date)

            bangumi_id = media_data.get("id")
            if bangumi_id:
                ET.SubElement(root, "bangumiid").text = str(bangumi_id)

            images = media_data.get("images") or {}
            thumb = images.get("large") or media_data.get("thumb", "")
            if thumb:
                ET.SubElement(root, "thumb").text = str(thumb)

            tree = ET.ElementTree(root)
            ET.indent(tree, space="  ", level=0)
            tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
            logger.info(f"NFO 文件生成成功: {nfo_path}")
            return True

        except Exception as e:
            raise FileOperationError(
                filepath=str(nfo_path), 
                operation="生成 NFO", 
                details=str(e)
            )

    @staticmethod
    def scan_local_library(root_path: str) -> List[Dict[str, Any]]:
        """
        扫描本地媒体库一级子文件夹，检测 .nfo 刮削状态并统计单集数。
        
        Args:
            root_path: 本地库根目录路径
            
        Returns:
            包含文件夹信息的列表，格式为：
            [{'name': '文件夹名', 'path': '绝对路径', 'is_scraped': bool,
              'episode_count': int, 'anime_count': int}]
        """
        root_obj = Path(root_path)
        if not root_obj.exists() or not root_obj.is_dir():
            logger.warning(f"本地扫描失败：路径无效或不是目录 - {root_path}")
            return []

        result = []
        try:
            # 性能优化：预先递归扫描根目录下所有的 .nfo 文件，建立路径索引
            # 【终极平铺架构】：扫描所有以 tvshow_ 开头的 nfo 文件 (代表一部动画/剧集)
            all_tvshow_nfos = []
            for p in root_obj.rglob("*.nfo"):
                if p.name.lower().startswith("tvshow_"):
                    all_tvshow_nfos.append(p)
            
            tvshow_path_strings = [str(p.parent.absolute()) for p in all_tvshow_nfos]

            # 扫描所有非 tvshow_ 开头的 .nfo 文件 (代表单集或平铺的剧场版)
            all_other_nfos = []
            for p in root_obj.rglob("*.nfo"):
                if not p.name.lower().startswith("tvshow_"):
                    all_other_nfos.append(p)
                    
            other_nfo_path_strings = [str(p.parent.absolute()) for p in all_other_nfos]
            
            for folder in root_obj.iterdir():
                if folder.is_dir():
                    try:
                        folder_abs_str = str(folder.absolute())
                        
                        # 统计该文件夹下包含几部动画
                        # 1. 统计该文件夹及其子目录下 tvshow_*.nfo 的数量
                        tvshow_count = sum(1 for p_str in tvshow_path_strings if p_str.startswith(folder_abs_str))
                        
                        # 2. 平铺结构支持：统计该文件夹下（不递归）所有非 tvshow_*.nfo 的 .nfo 数量
                        standalone_nfo_count = 0
                        if tvshow_count == 0:
                            # 检查该文件夹下是否有任何非 tvshow_*.nfo 的 nfo 文件
                            has_other_nfos = any(p_str == folder_abs_str for p_str in other_nfo_path_strings)
                            if has_other_nfos:
                                standalone_nfo_count = 1 # 视为一个平铺的合集条目
                        
                        anime_count = tvshow_count + standalone_nfo_count

                        # 判定“已刮削”状态：只要 anime_count > 0，就认为该文件夹已被识别/刮削
                        is_scraped = anime_count > 0

                        episode_count = 0
                        if is_scraped:
                            # 统计单集 NFO 数量（仅限当前文件夹下，不递归）
                            for nfo_file in folder.glob("*.nfo"):
                                if not nfo_file.name.lower().startswith("tvshow_"):
                                    episode_count += 1

                        result.append({
                            "name": folder.name,
                            "path": str(folder),
                            "is_scraped": is_scraped,
                            "episode_count": episode_count,
                            "anime_count": anime_count
                        })
                    except PermissionError:
                        logger.warning(f"跳过无读取权限的文件夹: {folder.name}")
                        continue
        except Exception as e:
            logger.error(f"媒体库根目录扫描异常 [{root_path}]: {e}")

        result.sort(key=lambda x: (x['is_scraped'], x['name']))
        return result

    @staticmethod
    def write_episode_nfo(
        video_path: str, 
        ep_data: Dict[str, Any], 
        show_data: Dict[str, Any] = None, 
        overwrite: bool = False
    ) -> bool:
        """
        与视频同名生成 NFO，并强行注入 <showtitle>。
        支持多季：优先从 ep_data 中读取 season，再 fallback 到 show_data。
        
        Args:
            video_path: 视频文件路径
            ep_data: 单集数据
            show_data: 节目数据（可选）
            overwrite: 是否覆盖已存在的文件
            
        Returns:
            是否成功写入
        """
        v_path = Path(video_path)
        nfo_path = v_path.with_suffix('.nfo')

        if nfo_path.exists() and not overwrite:
            return True

        root = ET.Element("episodedetails")

        title_text = ep_data.get("name_cn") or ep_data.get("name") or v_path.stem
        ET.SubElement(root, "title").text = title_text
        ET.SubElement(root, "episode").text = str(ep_data.get("sort") or ep_data.get("ep", ""))
        ET.SubElement(root, "plot").text = ep_data.get("desc", "暂无简介")

        # 多季支持：season 优先级链
        # ep_data.season > ep_data.season_number > show_data.season > 1
        season_num = (
            ep_data.get("season")
            or ep_data.get("season_number")
            or (show_data.get("season") if show_data else None)
            or 1
        )
        ET.SubElement(root, "season").text = str(season_num)

        if show_data:
            show_title = show_data.get("name_cn") or show_data.get("name") or show_data.get("title", "")
            if show_title:
                ET.SubElement(root, "showtitle").text = show_title
                
            # 【终极平铺架构】：在单集 NFO 中强行注入所属的 bangumiid
            # 这样在读取时，就能知道这个单集属于哪个 tvshow_xxx.nfo
            b_id = show_data.get("id") or show_data.get("bangumi_id")
            if b_id:
                ET.SubElement(root, "bangumiid").text = str(b_id)

        try:
            tree = ET.ElementTree(root)
            ET.indent(tree, space="  ", level=0)
            tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
            return True
        except Exception as e:
            logger.error(f"写入单集 NFO 失败 [{nfo_path}]: {e}")
            return False

    @staticmethod
    def read_bangumi_id_from_nfo(nfo_path: str) -> Optional[int]:
        """
        从已有的 tvshow.nfo 中读取 bangumiid，用于静默追番
        
        Args:
            nfo_path: NFO 文件路径
            
        Returns:
            Bangumi ID，如果读取失败则返回 None
        """
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            b_id = root.find("bangumiid")
            if b_id is not None and b_id.text and b_id.text.isdigit():
                return int(b_id.text)
        except Exception as e:
            logger.debug(f"读取 NFO 中的 Bangumi ID 失败: {e}")
            pass
        return None

    @classmethod
    def get_valid_video_files(cls, root_dir: str, min_size_mb: int = 0) -> List[Dict[str, Any]]:
        """
        深度递归扫描：穿透所有子文件夹获取视频文件。
        支持按最小体积过滤（从配置读取 min_video_size_mb）。
        
        Args:
            root_dir: 根目录路径
            min_size_mb: 最小文件大小（MB），0 表示从配置读取
            
        Returns:
            视频文件信息列表
        """
        valid_files = []
        root_path = Path(root_dir)

        if not root_path.exists() or not root_path.is_dir():
            return valid_files

        # 如果调用方没有显式传 min_size_mb，从配置读取
        if min_size_mb <= 0:
            config = ConfigLoader().config
            min_size_mb = config.get("min_video_size_mb", 0)
        min_size_bytes = min_size_mb * 1024 * 1024

        for file_path in root_path.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in cls.VIDEO_EXTS:
                size_bytes = file_path.stat().st_size
                if min_size_bytes > 0 and size_bytes < min_size_bytes:
                    continue  # 跳过小于阈值的文件
                rel_path_obj = file_path.relative_to(root_path)
                rel_path_str = str(rel_path_obj).replace(os.sep, '/')

                valid_files.append({
                    'path': str(file_path.absolute()),
                    'filename': file_path.name,
                    'relative_path': rel_path_str,
                    'size_bytes': size_bytes
                })

        return valid_files

