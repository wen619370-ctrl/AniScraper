import sys
import os
import multiprocessing
import ctypes  # ✅ 引入 C 底层调用模块，用于突破 Windows 任务栏限制

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon  # ✅ 引入图标引擎
from ui.main_window import MainWindow
from utils.path_resolver import get_resource_path  # ✅ 引入全局路径解析器

def main():
    app = QApplication(sys.argv)
    
    # ✅ 设置全局应用程序级别图标 (注意：QApplication 实例本身直接调用 setWindowIcon)
    try:
        global_icon_path = get_resource_path("resources/icons/app.png")
        app.setWindowIcon(QIcon(global_icon_path))
    except Exception as e:
        print(f"全局图标加载跳过: {e}")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    # 🛡️ 防弹装甲 1：防止 Windows 下打包后出现多进程“无限弹窗崩溃”
    multiprocessing.freeze_support()
    
    # 🛡️ 防弹装甲 2：将运行目录强制切换到可执行文件所在目录
    if getattr(sys, 'frozen', False):
        os.chdir(sys._MEIPASS)
        
    # 🛡️ 防弹装甲 3：彻底修复 Windows 任务栏图标丢失（致盲）问题
    # 必须在 QApplication 实例化之前进行系统级宣告
    if os.name == 'nt':  # 确保只在 Windows 系统下执行
        try:
            # 设定一个全局唯一的 AppID (公司名.产品名.子模块.版本号)
            my_app_id = 'myproduct.aniscraper.main.v6.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_app_id)
        except Exception:
            pass # 容错处理，防止非标准 Windows 环境报错

    # 启动主程序
    main()