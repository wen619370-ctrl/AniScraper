import logging
import sys
from PySide6.QtCore import QObject, Signal

# 1. 定义信号发射器 (必须继承 QObject)
class LogSignaler(QObject):
    log_signal = Signal(str, str)

# 2. 自定义 Handler
class QtLogHandler(logging.Handler):
    def __init__(self, signaler):
        super().__init__()
        self.signaler = signaler

    def emit(self, record):
        msg = self.format(record)
        self.signaler.log_signal.emit(record.levelname, msg)

# ==========================================
# ✅ 核心修复：分离基础日志与 Qt UI 日志
# ==========================================

# 1. 初始化纯 Python 基础 Logger (随时 import 都绝对安全，0 延迟)
logger = logging.getLogger("AniScraper")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s', '%H:%M:%S')

if not logger.handlers:
    # 纯后台写入：文件 + 控制台
    file_handler = logging.FileHandler("app.log", encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# 2. 专属挂载函数：只有在 QApplication 创建后，才能调用这个方法接通 UI
def attach_qt_ui_handler():
    """将日志管道接到 Qt 界面上，必须在主窗口初始化时调用"""
    if hasattr(logger, 'signaler'):
        return # 防止重复挂载
        
    signaler = LogSignaler()
    qt_handler = QtLogHandler(signaler)
    qt_handler.setFormatter(formatter)
    logger.addHandler(qt_handler)
    
    # 将 signaler 挂载在 logger 身上，供 MainWindow 连线
    logger.signaler = signaler