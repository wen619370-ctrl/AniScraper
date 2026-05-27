from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, 
    QPushButton, QLabel, QMenu,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QBrush, QAction
import math
import os

from utils.config_loader import ConfigLoader
from core.file_manager import FileManager


class MediaListPanel(QWidget):
    """
    媒体库文件夹列表面板。
    使用 QTableWidget 双列布局：
    - 第 0 列：文件夹名（自动拉伸）
    - 第 1 列：动画计数 "X部"（固定 60px，始终可见）

    支持排序：按名称、按修改时间，以及递增/递减。
    智能排序（已刮削的优先/沉底）在"设置 → 视图"中控制。
    """
    item_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigLoader()
        
        # ✅ 分页核心状态机
        self.all_merged_results = [] # 缓存底层的全量数据
        self.current_page = 1
        self.total_pages = 1

        # ✅ 排序状态
        self.sort_mode = "name"       # "name" | "mtime"
        self.sort_ascending = True    # True = 递增, False = 递减
        
        self._setup_ui()
        self.update_library_combo()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # --- 顶部操作区（媒体库选择 + 刷新/移除 + 排序控件，全部在一行） ---
        top_layout = QHBoxLayout()
        top_layout.setSpacing(4)

        self.combo_libraries = QComboBox()
        self.combo_libraries.setMinimumHeight(30)
        self.combo_libraries.currentIndexChanged.connect(self._on_combo_changed)
        top_layout.addWidget(self.combo_libraries, stretch=1)

        # 排序按钮（点击弹出菜单，参照 Windows 资源管理器风格）
        self.btn_sort = QPushButton("排序")
        self.btn_sort.setMinimumHeight(30)
        self.btn_sort.setFixedWidth(80)
        self.btn_sort.setCursor(Qt.PointingHandCursor)
        self.btn_sort.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 0 8px;
                text-align: left;
                color: #333;
            }
            QPushButton:hover { background-color: #e0e0e0; border-color: #999; }
            QPushButton:pressed { background-color: #d0d0d0; }
        """)
        self._sort_menu = QMenu(self)
        self._sort_menu.setStyleSheet("""
            QMenu { padding: 4px; }
            QMenu::item { padding: 6px 24px 6px 8px; }
            QMenu::item:selected { background-color: #e0e8f0; }
            QMenu::separator { height: 1px; background: #ddd; margin: 4px 8px; }
        """)
        self._sort_actions = {}  # key -> QAction
        self._build_sort_menu()
        self.btn_sort.setMenu(self._sort_menu)
        top_layout.addWidget(self.btn_sort)

        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setMinimumHeight(30)
        self.btn_refresh.setFixedWidth(36)
        self.btn_refresh.setToolTip("刷新当前视图")
        self.btn_refresh.clicked.connect(self.refresh_current_view)
        top_layout.addWidget(self.btn_refresh)

        self.btn_remove_lib = QPushButton("🗑️")
        self.btn_remove_lib.setMinimumHeight(30)
        self.btn_remove_lib.setFixedWidth(36)
        self.btn_remove_lib.setToolTip("移除当前媒体库")
        self.btn_remove_lib.setStyleSheet("color: #d9534f;")
        self.btn_remove_lib.clicked.connect(self._on_remove_lib_clicked)
        top_layout.addWidget(self.btn_remove_lib)

        layout.addLayout(top_layout)

        # --- 列表区：使用 QTableWidget 双列布局 ---
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(2)
        # 第 0 列：文件夹名（自动拉伸，占满剩余空间）
        # 第 1 列：动画计数（固定 60px，始终可见，不会被挤压）
        self.table_widget.horizontalHeader().setStretchLastSection(False)
        self.table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table_widget.setColumnWidth(1, 60)
        # 隐藏表头
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.horizontalHeader().setVisible(False)
        # 禁止编辑
        self.table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
        # 选中整行
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_widget.setSelectionMode(QTableWidget.SingleSelection)
        # 点击信号
        self.table_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.table_widget)

        # ✅ --- 底部分页控制区 ---
        self.page_widget = QWidget()
        page_layout = QHBoxLayout(self.page_widget)
        page_layout.setContentsMargins(0, 4, 0, 0)
        
        self.btn_prev_page = QPushButton("< 上一页")
        self.btn_prev_page.clicked.connect(self._page_prev)
        
        self.lbl_page_info = QLabel("1 / 1")
        self.lbl_page_info.setAlignment(Qt.AlignCenter)
        self.lbl_page_info.setStyleSheet("color: #555; font-weight: bold;")
        
        self.btn_next_page = QPushButton("下一页 >")
        self.btn_next_page.clicked.connect(self._page_next)
        
        page_layout.addWidget(self.btn_prev_page)
        page_layout.addWidget(self.lbl_page_info, stretch=1)
        page_layout.addWidget(self.btn_next_page)
        
        layout.addWidget(self.page_widget)

    def _build_sort_menu(self):
        """构建排序下拉菜单（参照 Windows 资源管理器风格）"""
        items = [
            ("name_asc",  "📛 名称",    "↑"),
            ("name_desc", "📛 名称",    "↓"),
            None,  # 分隔线
            ("mtime_asc",  "🕐 修改时间", "↑"),
            ("mtime_desc", "🕐 修改时间", "↓"),
        ]
        for item in items:
            if item is None:
                self._sort_menu.addSeparator()
                continue
            key, label, arrow = item
            action = QAction(f"{label} {arrow}", self)
            action.setData(key)
            action.triggered.connect(lambda checked=False, k=key: self._on_sort_selected(k))
            self._sort_actions[key] = action
            self._sort_menu.addAction(action)

        # 默认选中 name_asc
        self._update_sort_button("name_asc")

    def _on_sort_selected(self, key: str):
        """用户从菜单中选择了排序项"""
        parts = key.split("_")
        self.sort_mode = parts[0]          # "name" | "mtime"
        self.sort_ascending = (parts[1] == "asc")  # True=递增, False=递减
        self._update_sort_button(key)
        self._apply_sort()
        self.render_page()

    def _update_sort_button(self, key: str):
        """更新菜单项的选中标记（✓），按钮始终显示「排序」"""
        for k, action in self._sort_actions.items():
            action.setChecked(k == key)

    def _apply_sort(self):
        """根据当前排序模式和方向对 all_merged_results 排序"""
        if not self.all_merged_results:
            return

        reverse = not self.sort_ascending  # 递增=False, 递减=True

        # 先按用户选择的排序方式排序
        if self.sort_mode == "name":
            self.all_merged_results.sort(
                key=lambda x: x.get('name', '').lower(),
                reverse=reverse
            )
        elif self.sort_mode == "mtime":
            def _get_mtime(x):
                folder_path = x.get('path', '')
                try:
                    return os.path.getmtime(folder_path) if os.path.exists(folder_path) else 0
                except OSError:
                    return 0
            self.all_merged_results.sort(
                key=_get_mtime,
                reverse=reverse
            )

        # 如果启用了智能排序，在普通排序基础上叠加
        auto_sort = self.config.config.get("auto_sort_scraped", "off")
        if auto_sort == "top":
            # 已刮削置顶：已刮削的排前面（False < True）
            self.all_merged_results.sort(
                key=lambda x: (not x.get('is_scraped', False), 0),
                reverse=False
            )
        elif auto_sort == "bottom":
            # 已刮削置底：已刮削的排后面（True > False）
            self.all_merged_results.sort(
                key=lambda x: (x.get('is_scraped', False), 0),
                reverse=False
            )

    def _on_combo_changed(self, index):
        self.btn_remove_lib.setEnabled(self.combo_libraries.currentData() != "ALL")
        # ✅ 保存上次选择的媒体库路径到配置
        current_data = self.combo_libraries.currentData()
        if current_data and current_data != "ALL":
            self.config.config["last_library_path"] = current_data
            self.config.save_config()
        elif current_data == "ALL":
            self.config.config["last_library_path"] = "ALL"
            self.config.save_config()
        self.refresh_current_view()

    def refresh_current_view(self):
        """拉取底层全量数据，并重置分页"""
        self.current_page = 1
        libraries = self.config.get_libraries()
        
        if not libraries:
            self.table_widget.setRowCount(0)
            self.page_widget.setVisible(False)
            return

        current_data = self.combo_libraries.currentData()
        scan_paths = [lib['path'] for lib in libraries] if current_data == "ALL" else [current_data]

        self.all_merged_results = []
        for path in scan_paths:
            folders = FileManager.scan_local_library(path)
            if folders:
                self.all_merged_results.extend(folders)

        # 应用当前排序
        self._apply_sort()

        self.render_page()

    def render_page(self):
        """渲染当前页数据到 QTableWidget"""
        self.table_widget.setRowCount(0)
        
        if not self.all_merged_results:
            self.page_widget.setVisible(False)
            return

        enable_pagination = self.config.config.get("enable_pagination", False)
        items_per_page = self.config.config.get("items_per_page", 50)

        # 统计逻辑：计算所有文件夹中 anime_count 的总和，而不是文件夹的数量
        total_anime_count = sum(f.get('anime_count', 0) for f in self.all_merged_results)
        data_to_render = self.all_merged_results

        if enable_pagination and items_per_page > 0:
            self.page_widget.setVisible(True)
            self.total_pages = math.ceil(total_anime_count / items_per_page)
            if self.total_pages < 1: self.total_pages = 1
            if self.current_page > self.total_pages: self.current_page = self.total_pages
            
            start_idx = (self.current_page - 1) * items_per_page
            end_idx = self.current_page * items_per_page
            data_to_render = self.all_merged_results[start_idx:end_idx]

            self.lbl_page_info.setText(f"第 {self.current_page}/{self.total_pages} 页 (库中共 {total_anime_count} 部动画)")
            self.btn_prev_page.setEnabled(self.current_page > 1)
            self.btn_next_page.setEnabled(self.current_page < self.total_pages)
        else:
            self.page_widget.setVisible(True)
            self.lbl_page_info.setText(f"当前库中共 {total_anime_count} 部动画 (已展示全量)")
            self.btn_prev_page.setEnabled(False)
            self.btn_next_page.setEnabled(False)

        # 读取自动换行配置
        word_wrap = self.config.config.get("media_list_word_wrap", False)
        # 设置表格全局换行行为
        self.table_widget.setWordWrap(word_wrap)

        # 填充数据到表格
        self.table_widget.setRowCount(len(data_to_render))
        for row, folder_data in enumerate(data_to_render):
            name = folder_data.get('name', '未知文件夹')
            is_scraped = folder_data.get('is_scraped', False)
            anime_count = folder_data.get('anime_count', 0)

            # 第 0 列：图标 + 文件夹名
            icon = "✅" if is_scraped else "📁"
            name_item = QTableWidgetItem(f"{icon} {name}")
            name_item.setData(Qt.UserRole, folder_data)
            # 已刮削的文件夹用绿色
            if is_scraped:
                name_item.setForeground(QBrush(QColor(Qt.darkGreen)))
            self.table_widget.setItem(row, 0, name_item)

            # 第 1 列：动画计数（仅已刮削的文件夹显示）
            if is_scraped and anime_count > 0:
                count_text = f"{anime_count}部"
                count_item = QTableWidgetItem(count_text)
                count_item.setTextAlignment(Qt.AlignCenter)
                # 蓝色/灰色圆角标签样式
                bg_color = "#4a90e2" if anime_count > 1 else "#888"
                count_item.setForeground(QBrush(QColor("white")))
                count_item.setBackground(QBrush(QColor(bg_color)))
                self.table_widget.setItem(row, 1, count_item)
            else:
                # 未刮削的文件夹，第 1 列留空
                empty_item = QTableWidgetItem("")
                self.table_widget.setItem(row, 1, empty_item)

        # 设置行高：统一基准 30px
        self.table_widget.verticalHeader().setDefaultSectionSize(30)
        if word_wrap:
            # 自动换行模式：根据内容自适应行高，但保证不低于 30px
            self.table_widget.resizeRowsToContents()
            for row in range(self.table_widget.rowCount()):
                current = self.table_widget.rowHeight(row)
                if current < 30:
                    self.table_widget.setRowHeight(row, 30)

    # --- 翻页槽函数 ---
    def _page_prev(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.render_page()

    def _page_next(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.render_page()

    def update_library_combo(self):
        """重新从 Config 读取并组装下拉菜单"""
        self.combo_libraries.blockSignals(True) 
        self.combo_libraries.clear()
        
        self.combo_libraries.addItem("🌍 全部媒体库", userData="ALL")
        
        libraries = self.config.get_libraries()
        for lib in libraries:
            self.combo_libraries.addItem(f"📁 {lib['name']}", userData=lib['path'])

        # ✅ 如果启用了"启动时自动加载上次媒体库"，尝试选中上次的路径
        auto_load = self.config.config.get("auto_load_last_library", False)
        last_path = self.config.config.get("last_library_path", None)
        if auto_load and last_path:
            for i in range(self.combo_libraries.count()):
                if self.combo_libraries.itemData(i) == last_path:
                    self.combo_libraries.setCurrentIndex(i)
                    break
            
        self.combo_libraries.blockSignals(False)
        self.refresh_current_view()

    def _on_remove_lib_clicked(self):
        """执行移除媒体库的逻辑"""
        from PySide6.QtWidgets import QMessageBox

        current_data = self.combo_libraries.currentData()
        if not current_data or current_data == "ALL":
            return
            
        current_name = self.combo_libraries.currentText().replace("📁 ", "")
        
        reply = QMessageBox.question(
            self, 
            "移除媒体库", 
            f"确定要从软件中移除媒体库【{current_name}】吗？\n\n(提示：这仅会删除软件的索引配置，绝对不会删除您的本地物理文件！)",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.config.remove_library(current_data)
            self.update_library_combo()

    def _on_item_clicked(self, item):
        """点击表格项，发射选中信号
        - 点击第 0 列（文件夹名）：仅选中，不跳转
        - 点击第 1 列（计数标签）：选中并跳转到逻辑媒体库
        """
        row = item.row()
        data_item = self.table_widget.item(row, 0)
        if not data_item:
            return
        
        data = data_item.data(Qt.UserRole)
        if not data:
            return

        col = item.column()
        if col == 0:
            # ✅ 点击文件夹名：仅选中，不跳转（只发射一个"仅选中"信号）
            # 复制一份数据，标记为仅选中
            select_data = dict(data)
            select_data['_just_select'] = True
            self.item_selected.emit(select_data)
        elif col == 1:
            # ✅ 点击计数标签：选中并跳转到逻辑媒体库
            jump_data = dict(data)
            jump_data['_jump_to_library'] = True
            self.item_selected.emit(jump_data)

    def update_list(self, items_list: list, title: str = ""):
        """
        【外部数据注入通道】
        供主窗口的网络爬虫调用，直接把搜索结果覆盖渲染到当前列表。
        """
        self.table_widget.setRowCount(0)
        if hasattr(self, 'page_widget'):
            self.page_widget.setVisible(False)
        
        if title:
            self.table_widget.setRowCount(1)
            title_item = QTableWidgetItem(f"━━━ {title} ━━━")
            title_item.setFlags(Qt.NoItemFlags)
            title_item.setForeground(QBrush(QColor(Qt.darkCyan)))
            title_item.setTextAlignment(Qt.AlignCenter)
            self.table_widget.setItem(0, 0, title_item)
            self.table_widget.setSpan(0, 0, 1, 2)

        if not items_list:
            self.table_widget.setRowCount(1)
            empty_item = QTableWidgetItem("⚠️ 没有找到相关的网络结果。")
            empty_item.setFlags(Qt.NoItemFlags)
            self.table_widget.setItem(0, 0, empty_item)
            self.table_widget.setSpan(0, 0, 1, 2)
            return

        self.table_widget.setRowCount(len(items_list))
        for row, data in enumerate(items_list):
            display_name = data.get('name_cn') or data.get('name') or data.get('title') or "未知条目"
            name_item = QTableWidgetItem(f"📺 {display_name}")
            name_item.setData(Qt.UserRole, data)
            self.table_widget.setItem(row, 0, name_item)
            # 第 1 列留空
            self.table_widget.setItem(row, 1, QTableWidgetItem(""))

        # 统一行高基准 30px，与本地库渲染保持一致
        self.table_widget.verticalHeader().setDefaultSectionSize(30)

    @property
    def current_local_root(self):
        """
        【向下兼容桥梁】
        主窗口切换 Tab 时会尝试读取这个旧属性。
        """
        if not hasattr(self, 'combo_libraries'):
            return ""
            
        data = self.combo_libraries.currentData()
        if data == "ALL":
            libraries = self.config.get_libraries()
            return libraries[0]['path'] if libraries else ""
            
        return data if data else ""
