import sys
import os

def get_resource_path(relative_path: str) -> str:
    """
    【全局资源路径解析器】
    兼容开发环境与 PyInstaller 冻结环境。
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # 冻结环境（打包后）：获取 PyInstaller 的临时解压目录 / 执行目录
        base_path = sys._MEIPASS
    else:
        # 开发环境：获取项目的根目录
        # 假设 path_resolver.py 在 utils 文件夹下，那么根目录就是它的上一级
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
    return os.path.join(base_path, relative_path)