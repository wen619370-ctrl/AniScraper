import json
import os
from pathlib import Path
from utils.logger import logger

from utils.path_resolver import get_resource_path

# 修改 CONFIG_FILE 的声明
class ConfigLoader:
    _instance = None
    # 动态获取绝对路径
    CONFIG_FILE = get_resource_path("config.json")
    
    """
    V6.0 全局配置中枢 (单例模式)
    负责多媒体库的持久化与读取
    """

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._init_config()
        return cls._instance

    def _init_config(self):
        self.config = {
            "libraries": [],
            "min_video_size_mb": 150,
            "auto_sort_scraped": False,
            "auto_fill_search": False,
            # ✅ 新增：分页引擎配置
            "enable_pagination": False,   
            "items_per_page": 50          
        }
        self.load_config()

    def load_config(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
            except Exception as e:
                logger.error(f"读取配置失败: {e}")

    def save_config(self):
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            logger.info("全局配置已落盘保存。")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def get_libraries(self) -> list[dict]:
        """返回媒体库列表，如 [{'name': '主PT库', 'path': 'D:/PT'}]"""
        return self.config.get("libraries", [])

    def add_library(self, name: str, path: str):
        """追加新库并立即落盘"""
        libraries = self.get_libraries()
        
        # 防呆设计：如果路径已经存在，则更新名称，不重复添加
        for lib in libraries:
            if lib.get('path') == path:
                lib['name'] = name
                self.save_config()
                return

        libraries.append({'name': name, 'path': path})
        self.config['libraries'] = libraries
        self.save_config()

    def remove_library(self, path: str):
        """
        【安全移除】
        移除指定的媒体库并落盘保存（仅移除配置项，绝对不删本地物理文件）
        """
        libraries = self.get_libraries()
        # 利用列表推导式，过滤掉目标路径的库
        original_count = len(libraries)
        libraries = [lib for lib in libraries if lib.get('path') != path]
        
        # 如果数量发生变化，说明成功剔除，执行落盘
        if len(libraries) < original_count:
            self.config['libraries'] = libraries
            self.save_config()