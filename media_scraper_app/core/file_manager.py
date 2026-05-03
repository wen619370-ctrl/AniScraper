# 文件路径: core/file_manager.py

import os
import re
import errno
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

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
        r"""
        清理文件名中的非法字符，防止在 Windows/Linux 文件系统上创建文件失败。
        将 < > : " / \ | ? * 替换为单个空格，并去除首尾多余空白。
        """
        if not name:
            return "Unknown"
        # 使用正则替换非法字符
        clean_name = re.sub(r'[<>:"/\\|?*]', ' ', name)
        # 替换多个连续空格为一个空格，并去除首尾空白
        return re.sub(r'\s+', ' ', clean_name).strip()

    @staticmethod
    def create_hardlink_or_copy(src_path: str, dest_path: str) -> bool:
        """
        将源文件转移到目标路径。优先尝试创建硬链接 (Hardlink)，若失败（如跨盘符），则降级为物理复制。
        如果目标文件已存在，则安全跳过。
        """
        src = Path(src_path)
        dest = Path(dest_path)

        # 检查源文件是否存在
        if not src.exists() or not src.is_file():
            raise FileOperationError(filepath=src_path, operation="读取源文件", details="源文件不存在或不是标准文件")

        # 防御性逻辑：文件已存在则跳过
        if dest.exists():
            logger.info(f"目标文件已存在，跳过操作: {dest}")
            return True

        # 确保目标文件夹存在
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise FileOperationError(filepath=str(dest.parent), operation="创建目录", details=f"权限不足或路径无效 ({str(e)})")

        # 核心转移逻辑
        try:
            logger.debug(f"尝试为 {src.name} 创建硬链接...")
            os.link(src, dest)
            logger.info(f"硬链接创建成功: {dest}")
            return True

        except OSError as e:
            # 捕获跨盘符/跨设备链接错误 (Cross-device link)
            if e.errno == errno.EXDEV:
                logger.warning(f"触发跨盘符/设备限制，硬链接失败，正在自动降级为物理复制: {src.name} -> {dest.parent}")
                try:
                    shutil.copy2(src, dest)
                    logger.info(f"物理复制成功: {dest}")
                    return True
                except Exception as copy_e:
                    raise FileOperationError(filepath=str(dest), operation="降级复制", details=str(copy_e))
            else:
                # 其他系统级错误（如权限被拒 Permission denied）
                raise FileOperationError(filepath=str(dest), operation="硬链接", details=str(e))
        except Exception as e:
            raise FileOperationError(filepath=str(dest), operation="文件转移", details=str(e))

    @staticmethod
    def generate_nfo(media_data: dict, dest_dir: str, overwrite: bool = False) -> bool:
        nfo_path = Path(dest_dir) / "tvshow.nfo"
        
        # 【核心修改】：加上 not overwrite 判断
        if nfo_path.exists() and not overwrite:
            return True
        dest_path = str(nfo_path)
        r"""
        生成兼容 Emby/Jellyfin 标准的 NFO 元数据文件。
        """
        dest = Path(dest_path)

        if dest.exists():
            logger.info(f"NFO 文件已存在，跳过生成: {dest}")
            return True

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            # 【核心修复】：强制指定根节点为 tvshow，绝不能使用 API 返回的数字 type
            root = ET.Element("tvshow")

            # 提取标题 (优先中文名)
            title = media_data.get("name_cn") or media_data.get("name") or media_data.get("title", "未知标题")
            ET.SubElement(root, "title").text = str(title)
            
            # 提取原始标题 (日文名)
            original_title = media_data.get("name") or ""
            if original_title and original_title != title:
                ET.SubElement(root, "originaltitle").text = str(original_title)
            
            # 提取剧情简介
            plot = media_data.get("summary") or media_data.get("plot", "")
            if plot:
                ET.SubElement(root, "plot").text = str(plot)
                
            # 提取年份与首播日期
            date = media_data.get("air_date", "")
            year = date[:4] if date else str(media_data.get("year", ""))
            if year:
                ET.SubElement(root, "year").text = str(year)
            if date:
                ET.SubElement(root, "premiered").text = str(date)
            
            # 【新增】：保存 Bangumi ID，用于日后一键自动追番
            bangumi_id = media_data.get("id")
            if bangumi_id:
                ET.SubElement(root, "bangumiid").text = str(bangumi_id)
                
            # 提取海报图链接
            images = media_data.get("images") or {}
            thumb = images.get("large") or media_data.get("thumb", "")
            if thumb:
                ET.SubElement(root, "thumb").text = str(thumb)

            # 创建 ElementTree 并美化 XML 缩进
            tree = ET.ElementTree(root)
            ET.indent(tree, space="  ", level=0)

            # 使用 UTF-8 编码写入文件
            tree.write(dest, encoding="utf-8", xml_declaration=True)
            logger.info(f"NFO 文件生成成功: {dest}")
            return True

        except Exception as e:
            raise FileOperationError(filepath=dest_path, operation="生成 NFO", details=str(e))
    @staticmethod
    @staticmethod
    def scan_local_library(root_path: str) -> list[dict]:
        """扫描根目录，统计有几部动画"""
        import os
        from pathlib import Path

        root_obj = Path(root_path)
        if not root_obj.exists() or not root_obj.is_dir():
            return []

        result = []
        for folder in root_obj.iterdir():
            if folder.is_dir():
                is_scraped = (folder / "tvshow.nfo").exists()
                result.append({
                    "name": folder.name,
                    "path": str(folder),
                    "is_scraped": is_scraped
                    # 把 episode_count 彻底删掉！
                })
        return result
    
    @staticmethod
    def scan_local_library(root_path: str) -> list[dict]:
        """
        扫描本地媒体库一级子文件夹，极速检测 .nfo 刮削状态。
        :param root_path: 本地库根目录路径
        :return: [{'name': '文件夹名', 'path': '绝对路径', 'is_scraped': bool, 'type': 'local_folder'}]
        """
        results = []
        root = Path(root_path)
        
        if not root.exists() or not root.is_dir():
            logger.warning(f"本地扫描失败：路径无效或不是目录 - {root_path}")
            return results

        try:
            for entry in root.iterdir():
                if entry.is_dir():
                    try:
                        # 核心提速策略：使用生成器和 any()，匹配到第一个 .nfo 立即停止遍历当前目录
                        is_scraped = any(f.suffix.lower() == '.nfo' for f in entry.iterdir() if f.is_file())
                        
                        results.append({
                            "name": entry.name,
                            "path": str(entry.absolute()),
                            "is_scraped": is_scraped,
                            "type": "local_folder" # 附加类型标识，方便接收端判断
                        })
                    except PermissionError:
                        logger.warning(f"跳过无读取权限的文件夹: {entry.name}")
                        continue
                        
        except Exception as e:
            logger.error(f"媒体库根目录扫描异常 [{root_path}]: {e}")
            
        # 排序优化：优先显示“未刮削”的文件夹，其次按名称拼音/字母排序
        results.sort(key=lambda x: (x['is_scraped'], x['name']))
        return results

    @staticmethod
    def write_episode_nfo(video_path: str, ep_data: dict, show_data: dict = None, overwrite: bool = False) -> bool:
        """
        V5.0 绝对静止写入：与视频同名生成 NFO，并强行注入 <showtitle>
        """
        import xml.etree.ElementTree as ET
        from pathlib import Path
        
        v_path = Path(video_path)
        # 1. 绝对静止：名字直接拿视频的后缀替换，原文件一根汗毛都不动
        nfo_path = v_path.with_suffix('.nfo')

        if nfo_path.exists() and not overwrite:
            return True

        # 构建基础 XML
        root = ET.Element("episodedetails")
        
        # 单集专属数据
        title_text = ep_data.get("name_cn") or ep_data.get("name") or v_path.stem
        ET.SubElement(root, "title").text = title_text
        ET.SubElement(root, "episode").text = str(ep_data.get("sort") or ep_data.get("ep", ""))
        ET.SubElement(root, "plot").text = ep_data.get("desc", "暂无简介")
        
        # ==========================================
        # 💡 [V5.0 核心黑魔法]：强行注入番剧元数据认亲
        # ==========================================
        if show_data:
            # 填入番剧的总名称 (比如 "千年女优")
            show_title = show_data.get("name_cn") or show_data.get("name") or show_data.get("title", "")
            if show_title:
                ET.SubElement(root, "showtitle").text = show_title
            
            # 顺手强制加上 season 标签，解决某些播放器在混乱目录下识别不到第 1 季的问题
            season_num = show_data.get("season", "1")
            ET.SubElement(root, "season").text = str(season_num)

        try:
            # 格式化并写入硬盘
            xml_str = ET.tostring(root, encoding='utf-8')
            import xml.dom.minidom
            parsed_xml = xml.dom.minidom.parseString(xml_str)
            pretty_xml_as_string = parsed_xml.toprettyxml(indent="  ")
            
            with open(nfo_path, 'w', encoding='utf-8') as f:
                f.write(pretty_xml_as_string)
            return True
        except Exception as e:
            return False

    @staticmethod
    def read_bangumi_id_from_nfo(nfo_path: str) -> int:
        """从已有的 tvshow.nfo 中读取 bangumiid，用于静默追番"""
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            b_id = root.find("bangumiid")
            if b_id is not None and b_id.text and b_id.text.isdigit():
                return int(b_id.text)
        except Exception:
            pass
        return None
    

    # 在 core/file_manager.py 中追加
    @classmethod
    def get_valid_video_files(cls, root_dir: str, min_size_mb: int = 0) -> list[dict]:
        """
        V5.1 深度递归扫描：穿透所有子文件夹获取视频，并释放所有体积的文件
        """
        import os
        from pathlib import Path
        
        valid_files = []
        root_path = Path(root_dir)

        if not root_path.exists() or not root_path.is_dir():
            return valid_files

        # 使用 rglob('*') 深度递归遍历目录下所有层级的文件
        for file_path in root_path.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in cls.VIDEO_EXTS:
                
                # 获取体积大小
                size_bytes = file_path.stat().st_size
                
                # 🛑 【撤销物理拦截】：去掉了 if size_bytes >= ... 的判断
                # 让所有扫描到的文件都能往下走
                
                # 计算相对路径 (例如: Season 2/01.mkv)
                rel_path_obj = file_path.relative_to(root_path)
                
                # 强制将 Windows 的 '\' 替换为 '/'
                rel_path_str = str(rel_path_obj).replace(os.sep, '/')

                valid_files.append({
                    'path': str(file_path.absolute()),  # 绝对物理路径
                    'filename': file_path.name,         # 纯文件名
                    'relative_path': rel_path_str,      # 相对路径 
                    'size_bytes': size_bytes            # 必须携带体积信息给 UI
                })

        return valid_files

    @staticmethod
    def get_video_files_in_dir(directory_path: str) -> list[dict]:
        """扫描并提取目录下的视频文件，释放数据交由 UI 层软隐藏"""
        valid_extensions = {'.mp4', '.mkv', '.avi', '.rmvb'} # 可根据需要补充
        
        # 从单例拉取阈值，转换为 Bytes
        config = ConfigLoader().config
        min_size_bytes = config.get("min_video_size_mb", 150) * 1024 * 1024
        
        result_files = []
        path_obj = Path(directory_path)
        
        if not path_obj.exists():
            return result_files

        for item in path_obj.rglob('*'):
            if item.is_file() and item.suffix.lower() in valid_extensions:
                file_size = item.stat().st_size
                
                # 🛑 【撤销绝杀拦截】：把这里的拦截逻辑注释掉或删掉！
                # 只有去掉了这层拦截，不足 150MB 的文件才能被送入到核对弹窗中。
                # if file_size < min_size_bytes:
                #     continue
                    
                result_files.append({
                    "path": str(item.resolve()),
                    "size_bytes": file_size, # 这里一定要有 size_bytes
                    "relative_path": str(item.relative_to(path_obj))
                })
                
        return result_files

    @staticmethod
    def scan_local_library(root_path: str) -> list[dict]:
        """扫描根目录并统计每个目录内的有效单集数"""
        import os
        from pathlib import Path

        root_obj = Path(root_path)
        if not root_obj.exists() or not root_obj.is_dir():
            return []

        result = []
        for folder in root_obj.iterdir():
            if folder.is_dir():
                is_scraped = (folder / "tvshow.nfo").exists()
                
                # ✅ 含金量探针：统计单集 NFO 数量 (剔除 tvshow.nfo)
                episode_count = 0
                for nfo_file in folder.glob("*.nfo"):
                    if nfo_file.name.lower() != "tvshow.nfo":
                        episode_count += 1

                result.append({
                    "name": folder.name,
                    "path": str(folder),
                    "is_scraped": is_scraped,
                    "episode_count": episode_count # ✅ 装载统计数据
                })
        return result