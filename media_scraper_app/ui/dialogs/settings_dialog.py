from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QCheckBox, QPushButton, QHBoxLayout,
    QMessageBox, QSpinBox, QLabel, QFormLayout, QComboBox
)
from PySide6.QtCore import Signal
from utils.config_loader import ConfigLoader


class ViewSettingsDialog(QDialog):
    """
    视图设置 — 直接影响界面展示的配置项。
    菜单路径：视图(&V) → 界面设置...
    """
    settings_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("视图设置")
        self.setMinimumWidth(420)

        self.config_loader = ConfigLoader()
        self.current_config = self.config_loader.config

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- 主题选择 ---
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("界面主题:"))
        self.combo_theme = QComboBox()
        self.combo_theme.addItem("☀️ 浅色模式", "light")
        self.combo_theme.addItem("🌙 深色模式", "dark")
        current_theme = self.current_config.get("theme", "light")
        idx = self.combo_theme.findData(current_theme)
        if idx >= 0:
            self.combo_theme.setCurrentIndex(idx)
        theme_layout.addWidget(self.combo_theme)
        theme_layout.addStretch()
        layout.addLayout(theme_layout)

        layout.addSpacing(10)

        # --- 界面展示相关 ---
        self.chk_word_wrap = QCheckBox("媒体库自动换行 (超出部分名称换到下一行，行高增加)")
        self.chk_word_wrap.setChecked(self.current_config.get("media_list_word_wrap", False))
        layout.addWidget(self.chk_word_wrap)

        # 智能排序：禁用 / 已刮削置顶 / 已刮削置底
        smart_layout = QHBoxLayout()
        smart_layout.addWidget(QLabel("智能排序:"))
        self.combo_smart_sort = QComboBox()
        self.combo_smart_sort.addItem("禁用", "off")
        self.combo_smart_sort.addItem("已刮削置顶", "top")
        self.combo_smart_sort.addItem("已刮削置底", "bottom")
        current_smart = self.current_config.get("auto_sort_scraped", "off")
        if current_smart == "top":
            self.combo_smart_sort.setCurrentIndex(1)
        elif current_smart == "bottom":
            self.combo_smart_sort.setCurrentIndex(2)
        else:
            self.combo_smart_sort.setCurrentIndex(0)
        smart_layout.addWidget(self.combo_smart_sort)
        smart_layout.addStretch()
        layout.addLayout(smart_layout)

        # --- 分页设置 ---
        self.chk_pagination = QCheckBox("启用列表分页 (防止海量目录导致 UI 卡顿)")
        self.chk_pagination.setChecked(self.current_config.get("enable_pagination", False))
        layout.addWidget(self.chk_pagination)

        page_layout = QHBoxLayout()
        page_layout.setContentsMargins(25, 0, 0, 0)

        self.lbl_per_page = QLabel("每页显示目录数:")
        self.spin_per_page = QSpinBox()
        self.spin_per_page.setRange(10, 1000)
        self.spin_per_page.setValue(self.current_config.get("items_per_page", 50))

        page_layout.addWidget(self.lbl_per_page)
        page_layout.addWidget(self.spin_per_page)
        page_layout.addStretch()
        layout.addLayout(page_layout)

        # 联动：分页复选框控制子项启用状态
        self.chk_pagination.stateChanged.connect(self._on_pagination_toggled)
        self._on_pagination_toggled(self.chk_pagination.isChecked())

        layout.addSpacing(10)

        # --- 日志保留行数 ---
        log_layout = QHBoxLayout()
        log_layout.addWidget(QLabel("日志面板最大保留行数:"))
        self.spin_log_lines = QSpinBox()
        self.spin_log_lines.setRange(100, 10000)
        self.spin_log_lines.setSingleStep(100)
        self.spin_log_lines.setValue(self.current_config.get("log_max_lines", 1000))
        log_layout.addWidget(self.spin_log_lines)
        log_layout.addStretch()
        layout.addLayout(log_layout)

        layout.addStretch()

        # --- 底部按钮 ---
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self.save_settings)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _on_pagination_toggled(self, checked):
        """分页复选框状态变化时，控制子项启用/禁用"""
        disabled = not bool(checked)
        self.spin_per_page.setDisabled(disabled)
        self.lbl_per_page.setDisabled(disabled)

    def save_settings(self):
        self.current_config["theme"] = self.combo_theme.currentData()
        self.current_config["media_list_word_wrap"] = self.chk_word_wrap.isChecked()
        self.current_config["auto_sort_scraped"] = self.combo_smart_sort.currentData()
        self.current_config["enable_pagination"] = self.chk_pagination.isChecked()
        self.current_config["items_per_page"] = self.spin_per_page.value()
        self.current_config["log_max_lines"] = self.spin_log_lines.value()

        self.config_loader.save_config()
        self.settings_updated.emit()
        self.accept()


class PreferenceSettingsDialog(QDialog):
    """
    偏好设置 — 后台行为相关的配置项，用户不会直接看到效果。
    菜单路径：偏好(&P) → 行为设置...
    """
    settings_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("偏好设置")
        self.setMinimumWidth(420)

        self.config_loader = ConfigLoader()
        self.current_config = self.config_loader.config

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- 表单布局 ---
        form_layout = QFormLayout()

        self.spin_min_size = QSpinBox()
        self.spin_min_size.setRange(0, 5000)
        self.spin_min_size.setSuffix(" MB")
        self.spin_min_size.setValue(self.current_config.get("min_video_size_mb", 150))
        form_layout.addRow("过滤视频体积小于:", self.spin_min_size)

        layout.addLayout(form_layout)

        self.chk_auto_fill = QCheckBox("点击未刮削目录时，自动触发网络搜索")
        self.chk_auto_fill.setChecked(self.current_config.get("auto_fill_search", False))
        layout.addWidget(self.chk_auto_fill)

        self.chk_cache_on_scrape = QCheckBox("刮削时缓存 (在刮削作业台完成刮削时，自动将剧集数据写入本地缓存)")
        self.chk_cache_on_scrape.setChecked(self.current_config.get("cache_on_scrape", False))
        layout.addWidget(self.chk_cache_on_scrape)

        self.chk_auto_load = QCheckBox("启动时自动加载上次媒体库 (启动后自动切换到上次关闭时选择的媒体库路径)")
        self.chk_auto_load.setChecked(self.current_config.get("auto_load_last_library", False))
        layout.addWidget(self.chk_auto_load)

        self.chk_auto_overwrite = QCheckBox("发现旧 NFO 时自动覆盖 (不再弹出确认对话框)")
        self.chk_auto_overwrite.setChecked(self.current_config.get("auto_overwrite_nfo", False))
        layout.addWidget(self.chk_auto_overwrite)

        layout.addStretch()

        # --- 底部按钮 ---
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self.save_settings)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def save_settings(self):
        self.current_config["min_video_size_mb"] = self.spin_min_size.value()
        self.current_config["auto_fill_search"] = self.chk_auto_fill.isChecked()
        self.current_config["cache_on_scrape"] = self.chk_cache_on_scrape.isChecked()
        self.current_config["auto_load_last_library"] = self.chk_auto_load.isChecked()
        self.current_config["auto_overwrite_nfo"] = self.chk_auto_overwrite.isChecked()

        self.config_loader.save_config()
        self.settings_updated.emit()
        self.accept()
