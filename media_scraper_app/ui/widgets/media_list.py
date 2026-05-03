from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, 
    QPushButton, QListWidget, QListWidgetItem, QLabel
)
from PySide6.QtCore import Signal, Qt
import math

from utils.config_loader import ConfigLoader
from core.file_manager import FileManager

class MediaListPanel(QWidget):
    item_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigLoader()
        
        # ✅ 分页核心状态机
        self.all_merged_results = [] # 缓存底层的全量数据
        self.current_page = 1
        self.total_pages = 1
        
        self._setup_ui()
        self.update_library_combo()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # --- 顶部操作区 (保持原有代码) ---
        top_layout = QHBoxLayout()
        self.combo_libraries = QComboBox()
        self.combo_libraries.setMinimumHeight(35)
        self.combo_libraries.currentIndexChanged.connect(self._on_combo_changed)
        
        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.setMinimumHeight(35)
        self.btn_refresh.setFixedWidth(70)
        self.btn_refresh.clicked.connect(self.refresh_current_view)

        self.btn_remove_lib = QPushButton("🗑️ 移除")
        self.btn_remove_lib.setMinimumHeight(35)
        self.btn_remove_lib.setFixedWidth(70)
        self.btn_remove_lib.setStyleSheet("color: #d9534f;")
        self.btn_remove_lib.clicked.connect(self._on_remove_lib_clicked)
        
        top_layout.addWidget(self.combo_libraries, stretch=1)
        top_layout.addWidget(self.btn_refresh)
        top_layout.addWidget(self.btn_remove_lib)
        layout.addLayout(top_layout)

        # --- 列表区 ---
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        # ✅ --- 底部分页控制区 ---
        self.page_widget = QWidget()
        page_layout = QHBoxLayout(self.page_widget)
        page_layout.setContentsMargins(0, 5, 0, 0)
        
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

    def _on_combo_changed(self, index):
        self.btn_remove_lib.setEnabled(self.combo_libraries.currentData() != "ALL")
        self.refresh_current_view() # 切换库时触发全量拉取

    def refresh_current_view(self):
        """拉取底层全量数据，并重置分页"""
        self.current_page = 1 # ⚡ 核心防坑：刷新数据必定回到第一页
        libraries = self.config.get_libraries()
        
        if not libraries:
            self.list_widget.clear()
            self.page_widget.setVisible(False)
            item = QListWidgetItem("⚠️ 暂无媒体库数据")
            item.setFlags(Qt.NoItemFlags)
            self.list_widget.addItem(item)
            return

        current_data = self.combo_libraries.currentData()
        scan_paths = [lib['path'] for lib in libraries] if current_data == "ALL" else [current_data]

        # 拉取全量数据到内存缓存
        self.all_merged_results = []
        for path in scan_paths:
            folders = FileManager.scan_local_library(path)
            if folders:
                self.all_merged_results.extend(folders)
                
        # 执行排序干预
        auto_sort = self.config.config.get("auto_sort_scraped", False)
        if auto_sort:
            self.all_merged_results.sort(key=lambda x: (x.get('is_scraped', False), x.get('name', '')))
        else:
            self.all_merged_results.sort(key=lambda x: x.get('name', ''))

        # 进入切片渲染引擎
        self.render_page()

    def render_page(self):
        """【真分页切片引擎】：按需渲染 UI，并展示动画总数"""
        import math
        from PySide6.QtCore import Qt
        self.list_widget.clear()
        
        if not self.all_merged_results:
            self.page_widget.setVisible(False)
            self.list_widget.addItem(QListWidgetItem("该库下未扫描到有效番剧文件夹。"))
            return

        enable_pagination = self.config.config.get("enable_pagination", False)
        items_per_page = self.config.config.get("items_per_page", 50)

        # ✅ 这里就是当前库包含的真正“动画部数”
        total_anime_count = len(self.all_merged_results) 
        data_to_render = self.all_merged_results

        if enable_pagination and items_per_page > 0:
            self.page_widget.setVisible(True)
            self.total_pages = math.ceil(total_anime_count / items_per_page)
            if self.total_pages < 1: self.total_pages = 1
            if self.current_page > self.total_pages: self.current_page = self.total_pages
            
            start_idx = (self.current_page - 1) * items_per_page
            end_idx = self.current_page * items_per_page
            data_to_render = self.all_merged_results[start_idx:end_idx]

            # ✅ 拼接显示动画总数
            self.lbl_page_info.setText(f"第 {self.current_page}/{self.total_pages} 页 (库中共 {total_anime_count} 部动画)")
            self.btn_prev_page.setEnabled(self.current_page > 1)
            self.btn_next_page.setEnabled(self.current_page < self.total_pages)
        else:
            # 如果关闭了分页，也把统计条显示出来！
            self.page_widget.setVisible(True)
            self.lbl_page_info.setText(f"当前库中共 {total_anime_count} 部动画 (已展示全量)")
            self.btn_prev_page.setEnabled(False)
            self.btn_next_page.setEnabled(False)

        # 渲染极小部分切片数据
        for folder_data in data_to_render:
            name = folder_data.get('name', '未知文件夹')
            is_scraped = folder_data.get('is_scraped', False)
            
            icon = "✅" if is_scraped else "📁"
            # ✅ 还原干净清爽的名称，去掉了烦人的集数统计
            display_text = f"{icon} {name}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, folder_data)
            item.setForeground(Qt.darkGreen if is_scraped else Qt.black)
            self.list_widget.addItem(item)

    # --- 翻页槽函数 ---
    def _page_prev(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.render_page()

    def _page_next(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.render_page()
            
    # ... (保留原有的 _on_item_clicked, _on_remove_lib_clicked 等逻辑) ...

    def update_library_combo(self):
        """重新从 Config 读取并组装下拉菜单"""
        self.combo_libraries.blockSignals(True) 
        self.combo_libraries.clear()
        
        self.combo_libraries.addItem("🌍 全部媒体库", userData="ALL")
        
        libraries = self.config.get_libraries()
        for lib in libraries:
            self.combo_libraries.addItem(f"📁 {lib['name']}", userData=lib['path'])
            
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
        """点击列表项，发射选中信号"""
        data = item.data(Qt.UserRole)
        if data:
            self.item_selected.emit(data)

    def update_list(self, items_list: list, title: str = ""):
        """
        【外部数据注入通道】
        供主窗口的网络爬虫调用，直接把搜索结果覆盖渲染到当前列表。
        """
        self.list_widget.clear()
        # 如果是外部搜索结果，临时隐藏分页栏
        if hasattr(self, 'page_widget'):
            self.page_widget.setVisible(False)
        
        if title:
            title_item = QListWidgetItem(f"━━━ {title} ━━━")
            title_item.setFlags(Qt.NoItemFlags)
            title_item.setForeground(Qt.darkCyan)
            title_item.setTextAlignment(Qt.AlignCenter)
            self.list_widget.addItem(title_item)

        if not items_list:
            empty_item = QListWidgetItem("⚠️ 没有找到相关的网络结果。")
            empty_item.setFlags(Qt.NoItemFlags)
            self.list_widget.addItem(empty_item)
            return

        for data in items_list:
            display_name = data.get('name_cn') or data.get('name') or data.get('title') or "未知条目"
            list_item = QListWidgetItem(f"📺 {display_name}")
            list_item.setData(Qt.UserRole, data)
            self.list_widget.addItem(list_item)

    @property
    def current_local_root(self):
        """
        【向下兼容桥梁】
        主窗口切换 Tab 时会尝试读取这个旧属性。
        现在我们动态返回下拉框里当前选中的媒体库路径。
        """
        if not hasattr(self, 'combo_libraries'):
            return ""
            
        data = self.combo_libraries.currentData()
        if data == "ALL":
            libraries = self.config.get_libraries()
            return libraries[0]['path'] if libraries else ""
            
        return data if data else ""