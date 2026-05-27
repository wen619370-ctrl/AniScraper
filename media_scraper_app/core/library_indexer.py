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
        支持复杂文件结构：tvshow.nfo 在父目录，单集 NFO 在子目录（如 Season 1/）的情况。
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
            
            # 【终极平铺架构】：寻找当前目录下所有的 tvshow_*.nfo
            tvshow_nfos = [f for f in filenames if f.lower().startswith('tvshow_') and f.lower().endswith('.nfo')]
            
            # 兼容旧版：如果存在 tvshow.nfo，也把它加进来
            if 'tvshow.nfo' in [f.lower() for f in filenames]:
                tvshow_nfos.append('tvshow.nfo')
                
            # 如果当前目录没有任何 tvshow NFO，检查是否是纯平铺的独立视频 NFO 集合
            if not tvshow_nfos:
                other_nfos = [f for f in filenames if f.lower().endswith('.nfo')]
                if other_nfos:
                    # 检查当前目录是否在已记录的剧集目录下（避免重复收录子目录）
                    is_sub_dir = False
                    for existing_path in library_index.keys():
                        if dirpath.startswith(existing_path.split('_')[0] + os.sep):
                            is_sub_dir = True
                            break
                    if not is_sub_dir:
                        # --- 情况 B: 纯平铺结构 (无任何 tvshow NFO，但有多个独立视频 NFO) ---
                        for nfo_file in other_nfos:
                            nfo_file_path = current_dir / nfo_file
                            standalone_show = {
                                "title": nfo_file_path.stem,
                                "plot": "独立条目",
                                "episodes": [],
                                "dir_path": str(current_dir.absolute()),
                                "is_standalone": True
                            }
                            ep_data = cls._parse_episode_nfo(nfo_file_path)
                            if ep_data:
                                standalone_show["title"] = ep_data.get("title", nfo_file_path.stem)
                                standalone_show["episodes"].append(ep_data)
                                try:
                                    tree = ET.parse(nfo_file_path)
                                    b_id = tree.getroot().findtext("bangumiid") or tree.getroot().findtext("id")
                                    if b_id and b_id.isdigit():
                                        standalone_show["bangumi_id"] = int(b_id)
                                except: pass
                                
                                unique_key = f"{nfo_file_path.absolute()}"
                                library_index[unique_key] = standalone_show
                continue

            # --- 情况 A: 标准结构或终极平铺结构 (有 tvshow_*.nfo 或 tvshow.nfo) ---
            # 遍历当前目录下的每一个 tvshow NFO，它们各自代表一部独立的动画
            for tvshow_nfo_name in tvshow_nfos:
                tvshow_nfo_path = current_dir / tvshow_nfo_name
                show_data = {"title": current_dir.name, "plot": "暂无简介", "episodes": [], "dir_path": str(current_dir.absolute())}
                
                try:
                    tree = ET.parse(tvshow_nfo_path)
                    xml_root = tree.getroot()
                    title_node = xml_root.find("title")
                    if title_node is not None and title_node.text:
                        show_data["title"] = title_node.text
                    b_id_node = xml_root.find("bangumiid")
                    if b_id_node is not None and b_id_node.text:
                        show_data["bangumi_id"] = int(b_id_node.text)
                except Exception as e:
                    logger.warning(f"解析剧集 NFO 异常 [{tvshow_nfo_path}]: {e}")

                # 收集属于这部动画的单集
                # 逻辑：遍历所有单集 NFO，如果单集 NFO 内部的 bangumiid 与当前 tvshow 的 bangumiid 匹配，
                # 或者单集 NFO 没有 bangumiid（兼容旧版），则将其归入当前动画。
                for nfo_file_path in current_dir.rglob('*.nfo'):
                    if nfo_file_path.name.lower().startswith('tvshow'): continue
                    
                    ep_data = cls._parse_episode_nfo(nfo_file_path)
                    if not ep_data: continue
                    
                    # 检查归属权
                    belongs_to_this_show = False
                    try:
                        ep_tree = ET.parse(nfo_file_path)
                        ep_b_id = ep_tree.getroot().findtext("bangumiid")
                        if ep_b_id and str(ep_b_id) == str(show_data.get("bangumi_id")):
                            belongs_to_this_show = True
                        elif not ep_b_id:
                            # 兼容旧版：如果单集没有记录 ID，默认归属（可能会有误判，但这是旧数据的妥协）
                            belongs_to_this_show = True
                    except:
                        belongs_to_this_show = True
                        
                    if belongs_to_this_show:
                        show_data["episodes"].append(ep_data)

                def _safe_float_ep(x):
                    try: return float(x.get('ep', 9999))
                    except: return 9999.0
                show_data["episodes"].sort(key=_safe_float_ep)
                
                unique_key = f"{current_dir.absolute()}_{show_data.get('bangumi_id', show_data['title'])}"
                library_index[unique_key] = show_data

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
