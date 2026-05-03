# 文件路径: ui/widgets/search_panel.py

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, 
    QComboBox, QPushButton
)
from PySide6.QtCore import Signal, Slot, QTimer, Qt

class SearchPanel(QWidget):
    """
    顶部搜索面板组件。
    纯视图组件，不包含任何具体的网络刮削逻辑。
    通过对外发射 `search_requested` 信号与主控制器交互。
    """
    
    # 定义自定义信号：参数1为搜索关键词 (str)，参数2为选择的数据源 (str)
    search_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """初始化 UI 元素与布局"""
        # 使用水平布局，并清除外边距（因为外层的主窗体 QFrame 已经有边距了）
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)  # 控件之间的间距

        # 1. 搜索输入框
        self.input_kw = QLineEdit()
        self.input_kw.setPlaceholderText("输入番剧或影视名称，按回车搜索...")
        self.input_kw.setMinimumHeight(32)
        self.input_kw.setClearButtonEnabled(True) # 现代 UI 细节：右侧自带清除小叉号
        self.input_kw.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 0 8px;
            }
            QLineEdit:focus {
                border: 1px solid #4a90e2;
            }
        """)

        # 2. 数据源选择下拉框
        self.combo_source = QComboBox()
        self.combo_source.addItems(["Bangumi", "TMDB"])
        self.combo_source.setMinimumHeight(32)
        self.combo_source.setFixedWidth(100)
        self.combo_source.setCursor(Qt.PointingHandCursor)

        # 3. 搜索按钮
        self.btn_search = QPushButton("🔍 搜索")
        self.btn_search.setMinimumHeight(32)
        self.btn_search.setFixedWidth(80)
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:disabled {
                background-color: #a0c4e8;
                color: #eeeeee;
            }
        """)

        # 将控件加入布局，给输入框设置拉伸系数 1，让它占据多余的空间
        layout.addWidget(self.input_kw, stretch=1)
        layout.addWidget(self.combo_source)
        layout.addWidget(self.btn_search)

    def _connect_signals(self):
        """连接内部信号槽"""
        # 回车键和按钮点击，都绑定到同一个私有槽函数
        self.input_kw.returnPressed.connect(self._on_search_triggered)
        self.btn_search.clicked.connect(self._on_search_triggered)

    @Slot()
    def _on_search_triggered(self):
        """处理内部触发逻辑：获取数据、校验、发广播、防抖"""
        keyword = self.input_kw.text().strip()
        
        # 拦截：如果内容为空则不执行
        if not keyword:
            return

        source = self.combo_source.currentText()
        
        # 将焦点从输入框移走，避免闪烁的输入光标干扰视觉
        self.input_kw.clearFocus()
        
        # 临时禁用按钮（防重复连点）
        self.btn_search.setEnabled(False)
        self.btn_search.setText("搜索中...")
        
        # 向外部（主窗口/控制器）发射包含数据的信号
        self.search_requested.emit(keyword, source)
        
        # 设置一个定时器，1.5 秒后自动恢复按钮状态
        # （实际项目中也可以通过主窗口接收 Worker 的结束信号来恢复，这里做 UI 内部的短时防抖保底）
        QTimer.singleShot(1500, self._restore_button_state)

    def _restore_button_state(self):
        """恢复按钮可用状态"""
        self.btn_search.setEnabled(True)
        self.btn_search.setText("🔍 搜索")
        
    def reset_state(self):
        """对外暴露的方法：强制重置 UI 状态"""
        self._restore_button_state()
        self.input_kw.clear()