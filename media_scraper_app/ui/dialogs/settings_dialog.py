from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QCheckBox, QPushButton, QHBoxLayout, 
    QMessageBox, QSpinBox, QLabel, QFormLayout
)
from PySide6.QtCore import Signal
from utils.config_loader import ConfigLoader

class SettingsDialog(QDialog):
    # ✅ 定义全局配置更新信号
    settings_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统设置")
        self.setMinimumWidth(400)
        
        self.config_loader = ConfigLoader()
        self.current_config = self.config_loader.config
        
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 1. 基础配置区 (表单布局)
        form_layout = QFormLayout()
        
        self.spin_min_size = QSpinBox()
        self.spin_min_size.setRange(0, 5000)
        self.spin_min_size.setSuffix(" MB")
        self.spin_min_size.setValue(self.current_config.get("min_video_size_mb", 150))
        form_layout.addRow("过滤视频体积小于:", self.spin_min_size)
        
        layout.addLayout(form_layout)

        # 2. UX 交互行为控制区
        self.chk_auto_sort = QCheckBox("启用智能排序 (已刮削的文件夹自动沉底)")
        self.chk_auto_sort.setChecked(self.current_config.get("auto_sort_scraped", False))
        layout.addWidget(self.chk_auto_sort)

        self.chk_auto_fill = QCheckBox("点击未刮削目录时，自动触发网络搜索")
        self.chk_auto_fill.setChecked(self.current_config.get("auto_fill_search", False))
        layout.addWidget(self.chk_auto_fill)

        # ==========================================
        # ✅ V6.0 优化：分页设置区 (逻辑联动与视觉层级)
        # ==========================================
        self.chk_pagination = QCheckBox("启用列表分页 (防止海量目录导致 UI 卡顿)")
        self.chk_pagination.setChecked(self.current_config.get("enable_pagination", False))
        layout.addWidget(self.chk_pagination)

        # 把页数设置单独拿出来，并且包一个带缩进的水平布局，使其在视觉上属于复选框的子项
        page_layout = QHBoxLayout()
        page_layout.setContentsMargins(25, 0, 0, 0) # ✅ 左侧缩进 25 像素，体现父子层级
        
        self.lbl_per_page = QLabel("每页显示目录数:")
        self.spin_per_page = QSpinBox()
        self.spin_per_page.setRange(10, 1000)
        self.spin_per_page.setValue(self.current_config.get("items_per_page", 50))
        
        page_layout.addWidget(self.lbl_per_page)
        page_layout.addWidget(self.spin_per_page)
        page_layout.addStretch() # 加个弹簧，把组件顶到左边框去
        
        layout.addLayout(page_layout)

        # ✅ 核心联动神经：复选框状态改变时，自动启用/禁用下方的文字和输入框
        self.chk_pagination.toggled.connect(self.spin_per_page.setEnabled)
        self.chk_pagination.toggled.connect(self.lbl_per_page.setEnabled)
        
        # ✅ 初始化时手动校准一次状态，确保打开设置面板时灰度正确
        is_pagination_enabled = self.chk_pagination.isChecked()
        self.spin_per_page.setEnabled(is_pagination_enabled)
        self.lbl_per_page.setEnabled(is_pagination_enabled)
        # ==========================================

        layout.addStretch()

        # 3. 底部按钮
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存设置")
        btn_save.clicked.connect(self.save_settings)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def save_settings(self):
        # 回写配置到单例
        self.current_config["min_video_size_mb"] = self.spin_min_size.value()
        self.current_config["auto_sort_scraped"] = self.chk_auto_sort.isChecked()
        self.current_config["auto_fill_search"] = self.chk_auto_fill.isChecked()

        # ----------------------------------------
        # 在 save_settings 方法中追加保存逻辑：
        self.current_config["enable_pagination"] = self.chk_pagination.isChecked()
        self.current_config["items_per_page"] = self.spin_per_page.value()
        
        # 物理落盘
        self.config_loader.save_config()
        
        # 发射信号并关闭弹窗
        self.settings_updated.emit()
        self.accept()