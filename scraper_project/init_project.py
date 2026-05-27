import os
from pathlib import Path

# 定义项目根目录名称
PROJECT_NAME = "media_scraper_app"

# 定义目录树结构
DIRECTORIES = [
    "models",
    "ui/widgets",
    "ui/dialogs",
    "core",
    "workers",
    "utils",
    "resources/icons",
    "resources/styles"
]

# 定义需要创建的初始空文件
FILES = [
    "main.py",
    "config.yaml",
    "models/__init__.py",
    "models/media_entity.py",
    "models/scraper_result.py",
    "ui/__init__.py",
    "ui/main_window.py",
    "ui/widgets/__init__.py",
    "ui/widgets/search_panel.py",
    "ui/widgets/media_list.py",
    "ui/widgets/detail_card.py",
    "ui/dialogs/__init__.py",
    "ui/dialogs/settings_dialog.py",
    "ui/dialogs/progress_dialog.py",
    "core/__init__.py",
    "core/parser.py",
    "core/api_client.py",
    "core/file_manager.py",
    "workers/__init__.py",
    "workers/scrape_worker.py",
    "workers/file_io_worker.py",
    "utils/__init__.py",
    "utils/config_loader.py",
    "utils/logger.py",
    "utils/exceptions.py",
]

def init_project():
    root = Path(PROJECT_NAME)
    
    # 创建所有目录
    for dir_path in DIRECTORIES:
        (root / dir_path).mkdir(parents=True, exist_ok=True)
        print(f"📁 创建目录: {root / dir_path}")

    # 创建所有文件
    for file_path in FILES:
        target_file = root / file_path
        # 确保父目录存在（防万一）
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.touch(exist_ok=True)
        print(f"📄 创建文件: {target_file}")
        
    print(f"\n✅ 项目骨架初始化完成！请进入 {PROJECT_NAME} 目录开始开发。")

if __name__ == "__main__":
    init_project()