from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QLabel
from PySide6.QtGui import QTextCursor, QColor
from PySide6.QtCore import Qt
from utils.config_loader import ConfigLoader


class LogConsole(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._line_count = 0
        self._setup_ui()

    def _get_max_lines(self) -> int:
        """从配置中读取日志最大保留行数"""
        config = ConfigLoader()
        return config.config.get("log_max_lines", 1000)

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
        """接收日志并上色，超出最大行数时自动裁剪"""
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
        self._line_count += 1

        # ✅ 超出最大行数时，裁剪掉最早的一半日志
        max_lines = self._get_max_lines()
        if self._line_count > max_lines:
            block = self.log_display.document().firstBlock()
            while self._line_count > max_lines // 2:
                cursor = QTextCursor(block)
                cursor.select(QTextCursor.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()  # 删除换行符
                self._line_count -= 1
                block = self.log_display.document().firstBlock()

        # 自动滚动到底部
        self.log_display.moveCursor(QTextCursor.End)

    def clear_log(self):
        self.log_display.clear()
        self._line_count = 0
