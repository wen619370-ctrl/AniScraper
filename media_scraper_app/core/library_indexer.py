# 文件路径: core/library_indexer.py

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from utils.logger import logger

class LibraryIndexer:
    """
    本地媒体库内存索引引擎。
    逆向解析 NFO，构建【逻辑剧集 -> 物理单集】的树状映射。
    """
    
    # 常见的视频文件后缀字典
    VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.rmvb', '.flv', '.ts', '.wmv'}

    @classmethod
    def build_library_index(cls, root_path: str) -> dict:
        """
        全盘扫描，构建逻辑库索引。
        :return: { 
            "文件夹绝对路径": {
                "title": "剧集名", "plot": "简介", 
                "episodes": [{"ep": 1, "title": "单集名", "path": "物理视频路径"}, ...]
            } 
        }
        """
        library_index = {}
        root = Path(root_path)
        
        if not root.exists() or not root.is_dir():
            logger.error(f"索引构建失败：根目录无效 - {root_path}")
            return library_index

        logger.info(f"开始构建本地媒体库索引: {root_path}")

        # 使用 os.walk 进行深度遍历，支持多级嵌套目录
        for dirpath, dirnames, filenames in os.walk(root):
            current_dir = Path(dirpath)
            
            # 1. 寻找剧集总元数据
            tvshow_nfo_path = current_dir / "tvshow.nfo"
            # 【核心修复】：把 .exists() 改成 .is_file()，明确它必须是一个文件，绝不能是文件夹！
            if not tvshow_nfo_path.is_file():
                continue
                
            show_data = {"title": current_dir.name, "plot": "暂无简介", "episodes": [], "dir_path": str(current_dir.absolute())}
            
            try:
                # 解析 tvshow.nfo
                tree = ET.parse(tvshow_nfo_path)
                xml_root = tree.getroot()
                
                title_node = xml_root.find("title")
                if title_node is not None and title_node.text:
                    show_data["title"] = title_node.text
                    
                # 【关键新增】：提取身份证号，供后续网络懒加载使用
                b_id_node = xml_root.find("bangumiid")
                if b_id_node is not None and b_id_node.text:
                    show_data["bangumi_id"] = int(b_id_node.text)
                    
            except Exception as e:
                logger.warning(f"解析剧集 NFO 异常 [{tvshow_nfo_path}]: {e}")

            # 2. 寻找并解析所有的单集 NFO
            for filename in filenames:
                file_path = current_dir / filename
                if file_path.suffix.lower() == '.nfo' and filename.lower() != 'tvshow.nfo':
                    ep_data = cls._parse_episode_nfo(file_path)
                    if ep_data:
                        show_data["episodes"].append(ep_data)

            # 3. 按集数进行排序，确保呈现时的连贯性
            show_data["episodes"].sort(key=lambda x: float(x.get('ep', 9999)))
            
            # 将该剧集节点挂载到总索引树上 (以目录路径为唯一键)
            library_index[str(current_dir.absolute())] = show_data

        logger.info(f"索引构建完毕，共收录 {len(library_index)} 部剧集。")
        return library_index

    @classmethod
    def _parse_episode_nfo(cls, nfo_path: Path) -> dict:
        """探针：解析单集 NFO，并寻找同名的物理视频文件"""
        ep_data = {"ep": "?", "title": nfo_path.stem, "path": "文件丢失"}
        
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            
            ep_node = root.find("episode")
            if ep_node is not None and ep_node.text:
                ep_data["ep"] = ep_node.text
                
            title_node = root.find("title")
            if title_node is not None and title_node.text:
                ep_data["title"] = title_node.text
        except Exception:
            pass # 容错：解析失败则保留默认字典结构

        # 【物理寻址魔法】：在同目录下寻找同名的视频文件
        for ext in cls.VIDEO_EXTS:
            possible_video = nfo_path.with_suffix(ext)
            if possible_video.exists():
                ep_data["path"] = str(possible_video.absolute())
                break
                
        return ep_data