# 文件路径: ui/dialogs/progress_dialog.py

from PySide6.QtWidgets import QDialog, QVBoxLayout, QProgressBar, QLabel
from PySide6.QtCore import Qt, Slot

class ProgressDialog(QDialog):
    """
    全局任务进度弹窗。
    使用模态（Modal）锁定主界面，防止在底层文件 IO 时用户误操作。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统处理中")
        self.setMinimumSize(350, 100)
        self.resize(400, 110)
        # 设置为应用程序模态，阻塞底层窗口交互
        self.setWindowModality(Qt.ApplicationModal)
        # 移除原生的关闭按钮，强迫症防坑：文件移动一半被用户强制关掉容易产生碎片
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        self.lbl_status = QLabel("准备执行底层文件操作...", self)
        self.lbl_status.setStyleSheet("color: #333; font-weight: bold;")
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        layout.addWidget(self.lbl_status)
        layout.addWidget(self.progress_bar)

    @Slot(int, str)
    def update_progress(self, value: int, text: str):
        """接收 Worker 发来的进度信号并刷新 UI"""
        self.progress_bar.setValue(value)
        self.lbl_status.setText(text)