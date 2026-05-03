from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QLabel
from PySide6.QtGui import QTextCursor, QColor
from PySide6.QtCore import Qt

class LogConsole(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # 顶部工具栏
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("📝 系统实时日志"))
        header_layout.addStretch()
        
        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_clear.setFixedWidth(60)
        self.btn_clear.setStyleSheet("QPushButton { font-size: 11px; padding: 2px; }")
        self.btn_clear.clicked.connect(self.clear_log)
        header_layout.addWidget(self.btn_clear)
        
        layout.addLayout(header_layout)

        # 日志展示区
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                border: 1px solid #333;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.log_display)

    def append_log(self, level: str, msg: str):
        """接收日志并上色"""
        color_map = {
            "DEBUG": "#808080",      # 灰色
            "INFO": "#ffffff",       # 白色
            "WARNING": "#ce9178",    # 橙色
            "ERROR": "#f44336",      # 红色
            "CRITICAL": "#ff0000"    # 深红
        }
        color = color_map.get(level, "#ffffff")
        
        # 使用 HTML 渲染带颜色的行
        html_msg = f'<span style="color: {color};">{msg}</span>'
        self.log_display.appendHtml(html_msg)
        
        # 自动滚动到底部
        self.log_display.moveCursor(QTextCursor.End)

    def clear_log(self):
        self.log_display.clear()