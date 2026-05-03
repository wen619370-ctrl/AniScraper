# 文件路径: ui/widgets/detail_card.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QTextEdit, QPushButton
)
from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtGui import QPixmap

class DetailCardPanel(QWidget):
    """
    右侧详情卡片组件。
    负责展示选中条目的详细元数据，并提供最终执行动作的入口。
    纯视图组件，不包含图片网络下载逻辑。
    """
    
    # 定义自定义信号：当点击底部按钮时，将当前缓存的完整数据抛出
    execute_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_data = None  # 用于缓存当前展示的原始数据
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """初始化 UI 元素与精美排版布局"""
        # 最外层使用垂直布局：上边是信息区，下边是按钮区
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        # --- 上半部分：左右分栏 (左海报，右信息) ---
        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)

        # 1. 左侧：海报区
        self.lbl_poster = QLabel("暂无海报")
        self.lbl_poster.setAlignment(Qt.AlignCenter)
        self.lbl_poster.setFixedWidth(200)
        self.lbl_poster.setMinimumHeight(300)
        self.lbl_poster.setStyleSheet("""
            background-color: #e9ecef; 
            border: 1px solid #dee2e6; 
            border-radius: 6px;
            color: #adb5bd;
        """)
        # 核心设置：允许内部的 QPixmap 自适应 QLabel 的大小
        self.lbl_poster.setScaledContents(True) 
        top_layout.addWidget(self.lbl_poster)

        # 2. 右侧：文字信息区
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)

        # 标题与年份
        self.lbl_title = QLabel("请在左侧选择一个条目")
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #212529;")
        info_layout.addWidget(self.lbl_title)

        # 附属信息 (如总集数/开播日期)
        self.lbl_subinfo = QLabel("")
        self.lbl_subinfo.setStyleSheet("font-size: 13px; color: #6c757d;")
        info_layout.addWidget(self.lbl_subinfo)

        # 剧情简介 (使用可编辑的富文本框，允许用户手动润色)
        self.txt_plot = QTextEdit()
        self.txt_plot.setPlaceholderText("暂无剧情简介...")
        self.txt_plot.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa; 
                border: 1px solid #dee2e6; 
                border-radius: 4px;
                padding: 6px;
                color: #495057;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        info_layout.addWidget(self.txt_plot)

        # 将右侧文字区推入上半部分布局
        top_layout.addLayout(info_layout)
        
        # 将上半部分推入主布局
        main_layout.addLayout(top_layout)

        # --- 下半部分：执行动作区 ---
        self.btn_execute = QPushButton("✅ 确认刮削并生成 NFO")
        self.btn_execute.setEnabled(False) # 初始状态禁用
        self.btn_execute.setMinimumHeight(45)
        self.btn_execute.setCursor(Qt.PointingHandCursor)
        self.btn_execute.setStyleSheet("""
            QPushButton {
                background-color: #2fb565;
                color: white;
                font-size: 15px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #279e56;
            }
            QPushButton:disabled {
                background-color: #a8dcb9;
                color: #f1f1f1;
                cursor: not-allowed;
            }
        """)
        main_layout.addWidget(self.btn_execute)

    def _connect_signals(self):
        """连接内部按钮的点击信号"""
        self.btn_execute.clicked.connect(self._on_execute_clicked)

    @Slot()
    def _on_execute_clicked(self):
        """处理执行点击：提取最新的文本框内容更新到内存，并发射信号"""
        if self.current_data:
            # 防御性更新：用户可能在 UI 上微调了简介，需要同步回数据字典
            if isinstance(self.current_data, dict):
                self.current_data['plot'] = self.txt_plot.toPlainText()
            
            self.execute_requested.emit(self.current_data)

    def clear_data(self):
        """清空面板数据，重置为初始状态"""
        self.current_data = None
        self.lbl_poster.clear()
        self.lbl_poster.setText("暂无海报")
        self.lbl_title.setText("请在左侧选择一个条目")
        self.lbl_subinfo.setText("")
        self.txt_plot.clear()
        self.btn_execute.setEnabled(False)

    def update_data(self, media_data: dict):
        """接收并渲染新数据，激活确认按钮"""
        # 深浅拷贝的防坑：确保修改不会污染原始列表数据
        self.current_data = media_data.copy() if isinstance(media_data, dict) else media_data
        
        # 提取数据 (兼容 Bangumi 的字段)
        title = media_data.get('name_cn') or media_data.get('name') or "未知标题"
        date = media_data.get('air_date', '')
        year = date[:4] if date else "未知年份"
        
        self.lbl_title.setText(f"{title} ({year})")
        
        eps = media_data.get('total_episodes') or media_data.get('eps', '未知')
        self.lbl_subinfo.setText(f"📺 总集数: {eps}   |   📅 首播: {date or '未知'}")
        
        plot = media_data.get('summary') or media_data.get('plot', '')
        self.txt_plot.setPlainText(plot)
        
        self.btn_execute.setEnabled(True)

    def set_poster(self, pixmap: QPixmap):
        """提供给外部调用的海报更新接口 (已加入防拉伸/保持宽高比逻辑)"""
        if not pixmap.isNull():
            # 1. 关闭 QLabel 默认的无脑拉伸
            self.lbl_poster.setScaledContents(False)

            # 2. 获取当前 QLabel 相框的实际尺寸
            label_size = self.lbl_poster.size()

            # 3. 让图片在“保持原始宽高比 (KeepAspectRatio)”的前提下，平滑缩放以适应相框
            scaled_pixmap = pixmap.scaled(
                label_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation  # 开启抗锯齿平滑渲染
            )

            # 4. 把缩放好的图片挂上去
            self.lbl_poster.setPixmap(scaled_pixmap)
        else:
            self.lbl_poster.setText("图片加载失败")