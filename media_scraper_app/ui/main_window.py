# 文件路径: ui/main_window.py

from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QTabWidget, QMessageBox, QDialog,
    QInputDialog, QFileDialog, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QHBoxLayout, QApplication
)

from core.file_manager import FileManager
from core.library_indexer import LibraryIndexer
from core.matcher import EpisodeMatcher
from ui.dialogs.match_dialog import MatchDialog
from ui.dialogs.progress_dialog import ProgressDialog
from ui.dialogs.settings_dialog import ViewSettingsDialog, PreferenceSettingsDialog
from ui.widgets.detail_card import DetailCardPanel
from ui.widgets.library_panel import LibraryPanel
from ui.widgets.log_console import LogConsole
from ui.widgets.media_list import MediaListPanel
from ui.widgets.search_panel import SearchPanel
from utils.config_loader import ConfigLoader
from utils.logger import logger, attach_qt_ui_handler
from utils.path_resolver import get_resource_path
from utils.network_cache import get_cached_episodes, save_cached_episodes, get_cache_size, clear_all_cache
from utils.image_cache import get_image_cache_size, get_image_cache_count, clear_image_cache
from utils.media_exporter import export_media_library, import_media_library
from workers.file_io_worker import FileIOWorker
from workers.scrape_worker import ScrapeWorker


class MainWindow(QMainWindow):
    """
    全局主窗体控制器。
    负责 UI 组件的排版拼装，以及前端与底层异步 Worker 的神经连线。
    """
    def __init__(self):
        super().__init__()

        attach_qt_ui_handler()

        self.setWindowTitle("AniScraper v1.0")

        try:
            icon_path = get_resource_path("resources/icons/app.png")
            self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

        self.setMinimumSize(1024, 768)

        self.current_local_path = None

        self._setup_menu_bar()
        self._setup_status_bar()
        self._setup_ui()
        self._connect_global_signals()
        self._setup_main_layout()
        self._connect_logger()

        # ✅ 应用保存的主题设置
        self.apply_theme()


    # ==========================================
    # 布局与 UI 初始化
    # ==========================================

    def _setup_main_layout(self):
        """嵌入日志面板，加装状态栏抽屉开关"""
        original_main_widget = self.centralWidget()

        self.v_splitter = QSplitter(Qt.Vertical)
        self.v_splitter.setHandleWidth(6)
        self.v_splitter.setStyleSheet("""
            QSplitter::handle:vertical {
                background-color: #f0f0f0;
                border-top: 1px solid #ddd;
                border-bottom: 1px solid #ddd;
            }
            QSplitter::handle:vertical:hover {
                background-color: #d0d0d0;
            }
        """)

        if original_main_widget:
            self.v_splitter.addWidget(original_main_widget)

        self.log_console = LogConsole()
        self.v_splitter.addWidget(self.log_console)

        self.v_splitter.setSizes([800, 200])
        self.setCentralWidget(self.v_splitter)

        self.log_console.setVisible(False)

        self.btn_toggle_log = QPushButton("📝 运行日志")
        self.btn_toggle_log.setCheckable(True)
        self.btn_toggle_log.setChecked(False)
        self.btn_toggle_log.setFlat(True)
        self.btn_toggle_log.setStyleSheet("QPushButton:checked { color: #4a90e2; font-weight: bold; }")
        self.btn_toggle_log.clicked.connect(self._toggle_log_console)

        self.statusBar().addPermanentWidget(self.btn_toggle_log)

    def _toggle_log_console(self, checked: bool):
        """控制日志面板的呼出与收起"""
        self.log_console.setVisible(checked)
        if checked:
            self.v_splitter.setSizes([1000, 120])

    def _connect_logger(self):
        """将 logger 的信号跨线程连接到 UI"""
        if hasattr(logger, 'signaler'):
            logger.signaler.log_signal.connect(self.log_console.append_log)
        logger.info("AniScraper V6.0 系统启动成功，日志监控已就绪。")

    def _setup_status_bar(self):
        self.statusBar().showMessage("系统就绪。")

    def _setup_ui(self):
        """主窗体 UI 组装"""
        self.search_panel = SearchPanel(self)
        self.media_list_panel = MediaListPanel(self)
        self.detail_card_panel = DetailCardPanel(self)

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.search_panel)
        right_layout.addWidget(self.detail_card_panel)

        right_widget = QWidget()
        right_widget.setLayout(right_layout)

        scraping_splitter = QSplitter(Qt.Horizontal)
        scraping_splitter.addWidget(self.media_list_panel)
        scraping_splitter.addWidget(right_widget)
        # ✅ 媒体库面板是核心部件，设置最小宽度防止被隐藏
        self.media_list_panel.setMinimumWidth(200)
        scraping_splitter.setSizes([300, 700])
        # ✅ 设置子部件最小宽度，防止 splitter 将其完全隐藏
        scraping_splitter.setCollapsible(0, False)
        scraping_splitter.setCollapsible(1, False)

        self.main_tab = QTabWidget()
        self.main_tab.setStyleSheet("""
            QTabWidget::pane { border-top: 2px solid #4a90e2; }
            QTabBar::tab { padding: 10px 20px; font-size: 14px; font-weight: bold; }
            QTabBar::tab:selected { color: #4a90e2; background: #f0f8ff; }
        """)

        self.main_tab.addTab(scraping_splitter, "🛠️ 刮削作业台")

        self.library_panel = LibraryPanel()
        if hasattr(self.library_panel, 'btn_refresh'):
            self.library_panel.btn_refresh.clicked.connect(self._on_manual_refresh_clicked)

        self.main_tab.addTab(self.library_panel, "📊 逻辑媒体库")

        self.setCentralWidget(self.main_tab)

        try:
            icon_path = get_resource_path("resources/icons/app.ico")
            self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

    def _setup_menu_bar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件(&F)")

        add_lib_action = QAction("添加新媒体库...", self)
        add_lib_action.triggered.connect(self._on_add_new_library)
        file_menu.addAction(add_lib_action)

        file_menu.addSeparator()

        # ✅ 导出/导入菜单
        export_action = QAction("导出刮削数据...", self)
        export_action.triggered.connect(self._on_export_library)
        file_menu.addAction(export_action)

        import_action = QAction("导入刮削数据...", self)
        import_action.triggered.connect(self._on_import_library)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # ✅ "设置" — 一级菜单，下拉包含"视图"、"偏好"、"清除缓存"和"清除图片缓存"
        settings_menu = menubar.addMenu("设置(&S)")

        view_action = QAction("视图", self)
        view_action.triggered.connect(self._open_view_settings)
        settings_menu.addAction(view_action)

        pref_action = QAction("偏好", self)
        pref_action.triggered.connect(self._open_preference_settings)
        settings_menu.addAction(pref_action)

        settings_menu.addSeparator()

        clear_cache_action = QAction("清除网络数据缓存...", self)
        clear_cache_action.triggered.connect(self._on_clear_cache)
        settings_menu.addAction(clear_cache_action)

        clear_image_cache_action = QAction("清除图片缓存...", self)
        clear_image_cache_action.triggered.connect(self._on_clear_image_cache)
        settings_menu.addAction(clear_image_cache_action)

        help_menu = menubar.addMenu("帮助(&H)")
        about_action = QAction("关于 AniScraper", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

    # ==========================================
    # 主题管理
    # ==========================================

    def apply_theme(self, theme_name=None):
        """
        应用主题样式表到整个应用程序。
        从 resources/styles/ 目录加载对应的 .qss 文件。
        """
        if theme_name is None:
            config = ConfigLoader()
            theme_name = config.config.get("theme", "light")

        qss_filename = f"{theme_name}.qss"
        qss_path = get_resource_path(f"resources/styles/{qss_filename}")

        try:
            with open(qss_path, 'r', encoding='utf-8') as f:
                qss_content = f.read()
            self.setStyleSheet(qss_content)
            logger.info(f"🎨 已应用主题: {theme_name}")
        except FileNotFoundError:
            logger.warning(f"⚠️ 主题文件未找到: {qss_path}，使用默认样式")
            self.setStyleSheet("")
        except Exception as e:
            logger.error(f"❌ 加载主题失败: {e}")
            self.setStyleSheet("")

    # ==========================================
    # 信号连接
    # ==========================================

    def _connect_global_signals(self):
        """主控台中枢神经网：整合所有组件与后台 Worker 的连线"""
        # 刮削作业台连线
        self.media_list_panel.item_selected.connect(self._route_list_selection)
        self.search_panel.search_requested.connect(self._start_scraping)
        self.detail_card_panel.execute_requested.connect(self._handle_execution)

        # 逻辑媒体库连线
        self.main_tab.currentChanged.connect(self._on_main_tab_changed)
        self.library_panel.request_network_episodes.connect(self._handle_library_show_request)
        self.library_panel.request_manual_link.connect(self._handle_manual_link)
        self.library_panel.request_batch_download.connect(self._on_batch_download)

    # ==========================================
    # 设置相关
    # ==========================================

    def _open_view_settings(self):
        """打开视图设置面板"""
        dialog = ViewSettingsDialog(self)
        dialog.settings_updated.connect(self._on_settings_updated)
        dialog.exec()

    def _open_preference_settings(self):
        """打开偏好设置面板"""
        dialog = PreferenceSettingsDialog(self)
        dialog.settings_updated.connect(self._on_settings_updated)
        dialog.exec()

    def _on_settings_updated(self):
        """设置保存成功时触发 UI 热重载"""
        # ✅ 重新应用主题（可能在设置中更改了主题）
        self.apply_theme()
        if hasattr(self, 'media_list_panel'):
            self.media_list_panel.refresh_current_view()
        self.statusBar().showMessage("⚙️ 设置已更新，媒体库视图已自动重载。", 4000)

    def _on_clear_cache(self):
        """清除缓存：弹出确认窗口，显示当前缓存体积"""
        cache_size = get_cache_size()
        reply = QMessageBox.question(
            self,
            "清除缓存",
            f"确定要清除所有网络数据缓存吗？\n\n当前缓存体积: {cache_size}\n\n清除后，下次进入逻辑媒体库时将重新从网络拉取数据。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            count = clear_all_cache()
            QMessageBox.information(self, "清除完成", f"已成功清除 {count} 个缓存文件。")
            self.statusBar().showMessage(f"✅ 已清除 {count} 个缓存文件", 5000)

    def _on_clear_image_cache(self):
        """清除图片缓存：显示当前图片缓存大小，确认后清理"""
        cache_size = get_image_cache_size()
        cache_count = get_image_cache_count()
        reply = QMessageBox.question(
            self,
            "清除图片缓存",
            f"确定要清除所有图片缓存吗？\n\n当前图片缓存: {cache_count} 个文件，共 {cache_size}\n\n清除后，下次查看剧集详情时将重新从网络下载海报图片。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            count = clear_image_cache()
            QMessageBox.information(self, "清除完成", f"已成功清除 {count} 个图片缓存文件。")
            self.statusBar().showMessage(f"✅ 已清除 {count} 个图片缓存文件", 5000)

    def _on_export_library(self):
        """导出刮削数据：选择导出路径，打包 NFO + 海报图片为 ZIP"""
        # 先检查是否有媒体库
        config = ConfigLoader()
        libraries = config.get_libraries()
        if not libraries:
            QMessageBox.warning(self, "无法导出", "当前没有配置任何媒体库，请先添加媒体库。")
            return

        # 选择导出路径
        export_path, _ = QFileDialog.getSaveFileName(
            self, "选择导出路径", "AniScraper_Export.zip",
            "ZIP 文件 (*.zip)"
        )
        if not export_path:
            return

        self.statusBar().showMessage("正在打包导出刮削数据，请稍候...")
        QApplication.processEvents()

        result = export_media_library(export_path)

        if result["success"]:
            QMessageBox.information(
                self, "导出成功",
                f"{result['message']}\n\n导出路径: {result['export_path']}"
            )
            self.statusBar().showMessage(f"✅ 导出成功：{result['file_count']} 个文件，{result['show_count']} 部剧集", 5000)
        else:
            QMessageBox.warning(self, "导出失败", result["message"])
            self.statusBar().showMessage("❌ 导出失败", 5000)

    def _on_import_library(self):
        """导入刮削数据：选择 ZIP 文件，解压到目标目录"""
        # 选择导入的 ZIP 文件
        import_path, _ = QFileDialog.getOpenFileName(
            self, "选择要导入的 ZIP 文件", "",
            "ZIP 文件 (*.zip)"
        )
        if not import_path:
            return

        # 选择目标目录
        target_dir = QFileDialog.getExistingDirectory(self, "选择导入目标目录（媒体库根目录）", "")
        if not target_dir:
            return

        self.statusBar().showMessage("正在导入刮削数据，请稍候...")
        QApplication.processEvents()

        result = import_media_library(import_path, target_dir)

        if result["success"]:
            QMessageBox.information(
                self, "导入成功",
                f"{result['message']}\n\n目标目录: {target_dir}\n\n"
                f"💡 提示：导入完成后，请切换到【逻辑媒体库】Tab 查看导入的剧集。"
            )
            self.statusBar().showMessage(f"✅ 导入成功：{result['file_count']} 个文件", 5000)

            # 刷新逻辑媒体库索引
            self.full_library_index = None
            if self.main_tab.currentIndex() == 1:
                self._on_main_tab_changed(1)
        else:
            QMessageBox.warning(self, "导入失败", result["message"])
            self.statusBar().showMessage("❌ 导入失败", 5000)

    # ==========================================
    # 关于对话框
    # ==========================================

    def _show_about_dialog(self):
        """显示关于 AniScraper 的详细信息"""
        from PySide6.QtWidgets import QTextEdit, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("关于 AniScraper")
        dialog.setMinimumSize(600, 500)
        dialog.resize(640, 520)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        # 标题
        title = QLabel("📺 AniScraper — 动画媒体库刮削工具")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #4a90e2; padding: 8px 0;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 版本信息
        version_info = QLabel(
            "版本: v1.0 (Build 2026)\n"
            "数据源: Bangumi.tv (bgm.tv)\n"
            "运行环境: Python 3.12 + PySide6"
        )
        version_info.setStyleSheet("font-size: 13px; color: #555; padding: 4px 0;")
        version_info.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_info)

        # 分隔线
        sep = QLabel("━" * 50)
        sep.setStyleSheet("color: #ddd;")
        sep.setAlignment(Qt.AlignCenter)
        layout.addWidget(sep)

        # 详细说明
        details = QTextEdit()
        details.setReadOnly(True)
        details.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 12px;
                background-color: #fafafa;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        details.setHtml("""
<h3>📖 项目说明</h3>
<p>AniScraper 是一款专为动画爱好者设计的本地媒体库管理工具，灵感来源于 TinyMediaManager (TMM)。</p>
<p>核心功能：通过 <b>Bangumi.tv</b> 的开放 API，自动为本地视频文件匹配网络剧集信息，生成兼容 Emby / Jellyfin 标准的 NFO 元数据文件，实现动画媒体库的自动化刮削与整理。</p>

<h3>🔧 使用流程</h3>
<ol>
  <li><b>选择媒体库</b> — 在「刮削作业台」左侧点击「选择/刷新媒体库」，指定本地动画文件夹的根目录</li>
  <li><b>网络搜索</b> — 在右侧搜索框输入番剧名称，从 Bangumi 检索匹配条目</li>
  <li><b>核对匹配</b> — 点击「生成匹配」按钮，系统自动将本地视频与网络剧集进行智能匹配</li>
  <li><b>执行写盘</b> — 确认匹配无误后，系统将生成 tvshow.nfo 和单集 NFO 文件</li>
  <li><b>逻辑媒体库</b> — 切换到「逻辑媒体库」Tab，查看已刮削番剧的完整剧集列表</li>
</ol>

<h3>💡 不易察觉的使用细节</h3>
<ul>
  <li><b>点击文件夹名 vs 点击计数标签</b> — 在刮削作业台左侧列表中，点击文件夹名称仅选中（不跳转），点击右侧的计数标签（如 "3 集"）才会跳转到逻辑媒体库</li>
  <li><b>自动搜索</b> — 在「设置 → 偏好」中开启「auto_fill_search」后，点击未刮削的文件夹会自动触发网络搜索</li>
  <li><b>刮削时缓存</b> — 在「设置 → 偏好」中开启「cache_on_scrape」后，每次刮削完成会自动将剧集数据写入本地磁盘缓存</li>
  <li><b>多季支持</b> — 系统会自动从 NFO 中读取 season 信息，支持多季番剧的正确归类</li>
  <li><b>子文件夹递归</b> — 逻辑媒体库使用 rglob 递归扫描所有子文件夹中的 NFO 文件，支持复杂的目录结构</li>
  <li><b>视频文件过滤</b> — 系统会跳过小于配置阈值（min_video_size_mb）的视频文件，避免将预告片、花絮等小文件误匹配为剧集</li>
  <li><b>硬链接优先</b> — 文件整理时优先尝试创建硬链接（秒级完成），跨盘符时自动降级为物理复制</li>
  <li><b>缓存机制</b> — 网络剧集数据会缓存到本地磁盘，下次访问时无需重复请求网络，大幅提升响应速度</li>
  <li><b>日志面板</b> — 点击状态栏右下角的「📝 运行日志」按钮，可展开实时日志面板，方便排查问题</li>
</ul>

<h3>📁 文件结构</h3>
<pre style="background: #f0f0f0; padding: 8px; border-radius: 4px;">
媒体库根目录/
├── 番剧名称/
│   ├── tvshow.nfo          ← 剧集元数据
│   ├── poster.jpg           ← 海报图片
│   ├── Season 1/
│   │   ├── S01E01.mkv
│   │   ├── S01E01.nfo       ← 单集元数据
│   │   └── ...
│   └── Season 2/
│       └── ...
└── ...
</pre>
        """)
        layout.addWidget(details)

        # 关闭按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(dialog.accept)
        layout.addWidget(btn_box)

        dialog.exec()

    # ==========================================
    # 媒体库管理
    # ==========================================

    def _on_add_new_library(self):
        """添加媒体库的全过程闭环"""
        lib_name, ok = QInputDialog.getText(self, "添加新媒体库", "请输入媒体库昵称 (如: 主PT库, 老番库):")
        if not ok or not lib_name.strip():
            return

        lib_path = QFileDialog.getExistingDirectory(self, "选择媒体库根目录", "")
        if not lib_path:
            return

        ConfigLoader().add_library(lib_name.strip(), lib_path)
        self.statusBar().showMessage(f"✅ 成功添加媒体库：{lib_name}", 5000)

        if hasattr(self, 'media_list_panel'):
            self.media_list_panel.update_library_combo()

    # ==========================================
    # 网络刮削
    # ==========================================

    @Slot(str, str)
    def _start_scraping(self, keyword: str, source: str = "Bangumi"):
        """处理搜索请求，配置并启动异步线程"""
        if hasattr(self, 'scrape_worker'):
            try:
                if self.scrape_worker.isRunning():
                    self.scrape_worker.cancel()
                    self.scrape_worker.quit()
                    self.scrape_worker.wait()
            except RuntimeError:
                pass

        self.scrape_worker = ScrapeWorker(keyword=keyword)
        self.scrape_worker.progress_signal.connect(self.statusBar().showMessage)
        self.scrape_worker.result_signal.connect(self._on_scrape_finished)
        self.scrape_worker.error_signal.connect(self._on_scrape_error)

        self.detail_card_panel.clear_data()
        self.scrape_worker.start()

    @Slot(object, bytes)
    def _on_scrape_finished(self, results, poster_bytes):
        """处理网络数据和图片的最终回传"""
        if isinstance(results, list):
            self.media_list_panel.update_list(results, title="网络检索结果")
            self.statusBar().showMessage("✅ 检索完成！请在左侧选择正确条目。", 5000)

        elif isinstance(results, dict) and "details" in results:
            self.current_episodes = results.get("episodes", [])

            if getattr(self, '_is_library_fetching', False):
                self._is_library_fetching = False
                b_id = results['details']['id']
                # ✅ 保存到本地磁盘缓存
                save_cached_episodes(int(b_id), self.current_episodes)
                self._render_combined_episodes(self._current_library_show, self.current_episodes)
                return

            details_data = results["details"]
            self.detail_card_panel.update_data(details_data)

            if poster_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(poster_bytes)
                self.detail_card_panel.set_poster(pixmap)

            # ✅ 如果开启了"刮削时缓存"，在刮削完成时自动写入本地缓存
            config = ConfigLoader()
            if config.config.get("cache_on_scrape", False):
                b_id = details_data.get('id')
                if b_id and self.current_episodes:
                    save_cached_episodes(int(b_id), self.current_episodes)
                    logger.info(f"刮削时缓存已写入 (subject_id={b_id})")

            self.statusBar().showMessage("✅ 详情与海报加载完毕！", 5000)

    @Slot(str)
    def _on_scrape_error(self, err_msg):
        """网络或解析错误处理"""
        self.search_panel.reset_state()
        self.statusBar().showMessage(f"❌ 刮削失败: {err_msg}", 5000)

    @Slot(dict)
    def _on_auto_pop_match_dialog(self, remote_data: dict):
        """后台拿到剧集数据后，全自动模拟点击，呼出核对弹窗"""
        self.statusBar().showMessage("剧集数据恢复成功，正在打开核对窗口...")
        self.current_episodes = remote_data.get('episodes', [])
        details_data = remote_data.get('details', remote_data)
        if hasattr(self, '_handle_execution'):
            self._handle_execution(details_data)

    @Slot(object)
    def _fetch_details(self, raw_data):
        """点击列表项时，启动 Worker 获取详情和海报"""
        subject_id = raw_data.get('id')
        if not subject_id:
            return

        self.detail_card_panel.clear_data()

        # ✅ 安全清理旧 Worker
        self._cleanup_old_worker()

        self.scrape_worker = ScrapeWorker(subject_id=subject_id)
        self.scrape_worker.progress_signal.connect(self.statusBar().showMessage)
        self.scrape_worker.result_signal.connect(self._on_scrape_finished)
        self.scrape_worker.error_signal.connect(self._on_scrape_error)
        self.scrape_worker.start()

    # ==========================================
    # 列表点击路由
    # ==========================================

    @Slot(object)
    def _route_list_selection(self, data: dict):
        """左侧列表点击事件的路由分发"""
        # ✅ 处理仅选中（点击文件夹名，不跳转）
        if data.get('_just_select', False):
            # 移除标记，只记录当前路径
            data.pop('_just_select', None)
            folder_path = data.get('path', '')
            # 🐛 修复：只有当文件夹路径存在时（本地条目），才更新 current_local_path
            if folder_path:
                self.current_local_path = folder_path
                self.statusBar().showMessage(f"已选中: {data.get('name', '')}", 3000)
            # ⚠️ 注意：网络检索结果也有 _just_select 标记，但它们是网络条目（有 id 无 path），
            # 需要继续执行下面的逻辑来获取详情，不能直接 return！
            if 'id' in data and 'path' not in data:
                pass  # 继续执行，不要 return
            else:
                return

        # ✅ 处理跳转到逻辑媒体库（点击计数标签）
        if data.get('_jump_to_library', False):
            data.pop('_jump_to_library', None)
            folder_path = data.get('path', '')
            # 🐛 修复：只有当文件夹路径存在时（本地条目），才更新 current_local_path
            if folder_path:
                self.current_local_path = folder_path
                if data.get('is_scraped', False):
                    self._jump_to_logical_library(folder_path)
            return

        if 'id' in data and 'path' not in data:
            subject_id = data['id']
            self.statusBar().showMessage(f"正在拉取条目详情 (ID: {subject_id})...")

            # ✅ 安全清理旧 Worker
            self._cleanup_old_worker()

            self.scrape_worker = ScrapeWorker(subject_id=subject_id)
            self.scrape_worker.progress_signal.connect(self.statusBar().showMessage)
            self.scrape_worker.result_signal.connect(self._on_scrape_finished)
            self.scrape_worker.error_signal.connect(self._on_scrape_error)
            self.scrape_worker.start()
            return
        
        # 适配从手动刷新传过来的数据
        if data.get('is_manual_refresh', False):
            folder_path = data.get('local_dir')
            self._jump_to_logical_library(folder_path)
            return

        is_scraped = data.get('is_scraped', False)
        folder_path = data.get('path', '')

        # 🐛 修复：只有当文件夹路径存在时（本地条目），才更新 current_local_path
        if folder_path:
            self.current_local_path = folder_path

        # ==========================================
        # ✅ 实现 auto_fill_search：点击未刮削目录时自动触发网络搜索
        # ==========================================
        if not is_scraped:
            config = ConfigLoader()
            auto_fill = config.config.get("auto_fill_search", False)
            if auto_fill:
                folder_name = data.get('name', '')
                if folder_name:
                    self.statusBar().showMessage(f"🔍 自动搜索: {folder_name}")
                    self._start_scraping(folder_name, "bangumi")
                    return

        if is_scraped:
            # ✅ 点击已刮削文件夹 → 跳转到逻辑媒体库
            self._jump_to_logical_library(folder_path)

    def _jump_to_logical_library(self, folder_path: str):
        """点击已刮削文件夹时，跳转到逻辑媒体库并打开对应动画的剧集列表"""
        # 1. 先用 LibraryIndexer 扫描该文件夹下的所有剧集
        index_data = LibraryIndexer.build_library_index(folder_path)

        if not index_data:
            QMessageBox.information(
                self, "未找到剧集",
                f"在 {folder_path} 下未找到任何 tvshow.nfo 文件。\n请先在刮削作业台完成刮削。"
            )
            return

        # 2. 确定要跳转的目标剧集
        target_show = None
        if len(index_data) == 1:
            target_show = list(index_data.values())[0]
        else:
            dialog = QDialog(self)
            dialog.setWindowTitle("选择要查看的动画")
            dialog.setMinimumSize(400, 300)
            layout = QVBoxLayout(dialog)

            lbl = QLabel("该文件夹下包含多部动画，请选择要查看的：")
            layout.addWidget(lbl)

            list_widget = QListWidget()
            for dir_path, show_data in index_data.items():
                title = show_data.get('title', '未知剧集')
                item = QListWidgetItem(f"📺 {title}")
                item.setData(Qt.UserRole, show_data)
                list_widget.addItem(item)
            layout.addWidget(list_widget)

            btn_layout = QHBoxLayout()
            btn_cancel = QPushButton("取消")
            btn_cancel.clicked.connect(dialog.reject)
            btn_ok = QPushButton("查看")
            btn_ok.clicked.connect(dialog.accept)
            btn_layout.addStretch()
            btn_layout.addWidget(btn_cancel)
            btn_layout.addWidget(btn_ok)
            layout.addLayout(btn_layout)

            if dialog.exec() == QDialog.Accepted:
                selected_items = list_widget.selectedItems()
                if selected_items:
                    target_show = selected_items[0].data(Qt.UserRole)

        if not target_show:
            return

        # 3. 确保媒体库根目录已选择
        root_dir = self.media_list_panel.current_local_root
        if not root_dir:
            QMessageBox.warning(
                self, "未选择媒体库",
                "请先在【刮削作业台】左侧点击'选择/刷新媒体库'按钮选择整个大盘根目录！"
            )
            return

        # ✅ 补上 local_dir：build_library_index 返回的是 dir_path，而 load_library 用的是 local_dir
        target_show['local_dir'] = target_show.get('dir_path') or folder_path

        # 4. 切换到逻辑媒体库 Tab（切换时会触发 _on_main_tab_changed 自动加载完整索引）
        self.main_tab.setCurrentIndex(1)

        # 5. 在已加载的左侧列表中选中目标剧集（仅选中，不触发信号加载）
        self.library_panel.select_show_by_data(target_show)

        # 6. 安全清理可能正在运行的旧 scrape_worker，避免 QThread 报错
        if hasattr(self, 'scrape_worker') and self.scrape_worker is not None:
            try:
                if self.scrape_worker.isRunning():
                    self.scrape_worker.cancel()
                    self.scrape_worker.quit()
                    self.scrape_worker.wait()
            except RuntimeError:
                pass

        # 7. 直接触发剧集数据加载（同步调用，不依赖信号异步处理）
        self._handle_library_show_request(target_show)
        self.statusBar().showMessage(f"✅ 已跳转到【{target_show.get('title')}】", 5000)

    def _show_local_scraped_info(self, folder_path: str) -> dict:
        """读取本地 NFO，提取媒体 ID 以备弹窗使用"""
        import os
        import xml.etree.ElementTree as ET

        nfo_path = os.path.join(folder_path, "tvshow.nfo")
        folder_name = os.path.basename(folder_path)

        local_meta = {
            'name': folder_name,
            'summary': '暂无简介',
            'date': '',
            'is_local_cache': True,
            'folder_path': folder_path,
            'subject_id': None
        }

        if os.path.exists(nfo_path):
            try:
                with open(nfo_path, 'rb') as f:
                    xml_content = f.read()

                if xml_content.strip():
                    root = ET.fromstring(xml_content)
                    title = root.findtext('title') or root.findtext('localtitle')
                    if title:
                        local_meta['name'] = title
                    local_meta['summary'] = root.findtext('plot', '暂无简介')
                    local_meta['date'] = root.findtext('year', '')

                    subject_id = None
                    for uid in root.findall('uniqueid'):
                        if uid.text:
                            subject_id = uid.text
                            break
                    if not subject_id:
                        subject_id = root.findtext('bangumiid')

                    local_meta['subject_id'] = subject_id

            except Exception as e:
                logger.error(f"读取本地 NFO 失败: {e}")

        poster_path = os.path.join(folder_path, "poster.jpg")
        if not os.path.exists(poster_path):
            poster_path = os.path.join(folder_path, "folder.jpg")
        if os.path.exists(poster_path):
            local_meta['cover_image'] = poster_path

        if hasattr(self, 'detail_card_panel'):
            self.detail_card_panel.update_data(local_meta)

        return local_meta

    def _parse_local_episode_nfos(self, folder_path: str) -> list:
        """纯本地提取：递归扫描所有单集 NFO，但只保留与 get_valid_video_files 扫描到的视频文件匹配的条目"""
        import os
        import xml.etree.ElementTree as ET

        # ✅ 先获取所有被认可的视频文件路径集合（受 min_video_size_mb 过滤）
        valid_video_files = FileManager.get_valid_video_files(folder_path)
        valid_video_paths = set(v['path'] for v in valid_video_files)

        episodes = []
        for nfo_path_obj in Path(folder_path).rglob('*.nfo'):
            file_name = nfo_path_obj.name
            nfo_path = str(nfo_path_obj)

            if file_name.lower() == 'tvshow.nfo':
                continue

            try:
                with open(nfo_path, 'rb') as f:
                    xml_content = f.read()
                if not xml_content.strip():
                    continue

                root = ET.fromstring(xml_content)

                title = root.findtext('title') or root.findtext('localtitle') or '未知单集'
                ep_num = root.findtext('episode')
                season = root.findtext('season', '1')

                if ep_num and ep_num.isdigit():
                    base_name = nfo_path_obj.stem
                    parent_dir_name = nfo_path_obj.parent.name.lower()

                    video_path = ""
                    logger.debug(f"[探针准备] 正在为 NFO: {nfo_path_obj.name} 寻找旁边同名的视频文件...")

                    for ext in ['.mkv', '.mp4', '.avi', '.ts', '.rmvb']:
                        vid_file = nfo_path_obj.with_suffix(ext)
                        if vid_file.exists():
                            video_path = str(vid_file)
                            logger.info(f"🎯 [探针命中] 成功找到视频实体: {video_path}")
                            break

                    if not video_path:
                        logger.warning(
                            f"⚠️ [探针落空] 在 {nfo_path_obj.parent} 目录下，没有找到名为 {base_name} 的任何视频文件！"
                        )

                    # ✅ 核心过滤：只保留 video_path 在 get_valid_video_files 结果中的 NFO
                    if video_path and video_path not in valid_video_paths:
                        logger.debug(f"⏭️ [跳过] NFO {nfo_path_obj.name} 对应的视频不在 get_valid_video_files 结果中，跳过")
                        continue

                    real_id_str = root.findtext('bangumiid') or root.findtext('id')
                    real_id = int(real_id_str) if real_id_str and real_id_str.isdigit() else int(ep_num)
                    item_type = 'movie' if 'movie' in parent_dir_name or '剧场版' in base_name else 'episode'

                    ep_dict = {
                        'id': real_id,
                        'name': title,
                        'title': title,
                        'type': item_type,
                        'ep_name': title,
                        'ep_number': int(ep_num),
                        'episode': int(ep_num),
                        'sort': int(ep_num),
                        'season': int(season),
                        'season_number': int(season),
                        'overview': root.findtext('plot', '') or '暂无简介',
                        'plot': root.findtext('plot', '') or '暂无简介',
                        'local_filename': base_name,
                        'video_path': video_path,
                        'local_file': video_path,
                        'path': video_path
                    }

                    logger.debug(
                        f"[数据组装] 第 {ep_num} 集字典打包完毕，video_path 状态: {'有值' if video_path else '空'}"
                    )
                    episodes.append(ep_dict)
            except Exception:
                pass

        episodes.sort(key=lambda x: x.get('ep_number', 0))
        return episodes

    # ==========================================
    # 执行写盘
    # ==========================================

    @Slot(object)
    def _handle_execution(self, data):
        """处理最终的确认执行操作，弹出匹配核对框，确认后真实物理写盘"""
        # ✅ 防重入锁：防止 _on_scrape_finished 异步回调再次触发 _handle_execution
        if getattr(self, '_is_executing', False):
            logger.warning("⚠️ _handle_execution 正在执行中，跳过重复调用")
            return
        self._is_executing = True

        try:
            if not self.current_local_path:
                QMessageBox.warning(self, "操作异常", "请先在左侧【本地库】中选择一个需要刮削的文件夹！")
                return

            video_dicts = FileManager.get_valid_video_files(self.current_local_path)
            remote_episodes = getattr(self, 'current_episodes', [])

            if not video_dicts:
                QMessageBox.warning(self, "无视频文件", "当前目录未扫描到任何支持的视频文件，无法执行核对！")
                return

            if not remote_episodes:
                QMessageBox.warning(
                    self,
                    "网络数据缺失",
                    "缺少网络剧集数据，无法进行视频匹配！\n\n"
                    "💡 提示：如果您想重新刮削此文件夹，请先在右侧面板进行【网络搜索】，"
                    "并点击选中一部正确的网络影视条目，然后再点击此生成按钮。"
                )
                return

            match_result = EpisodeMatcher.smart_match(video_dicts, remote_episodes)

            dialog = MatchDialog(video_dicts, remote_episodes, match_result, self)

            if dialog.exec() == QDialog.Accepted:
                final_mapping = dialog.get_final_mapping()
            else:
                return

            if not final_mapping:
                self.statusBar().showMessage("没有有效的匹配项需要写入。")
                return

            # ✅ 修复：对于复杂文件结构，tvshow.nfo 应该写入视频文件所在的目录，而不是 current_local_path
            # 从 final_mapping 中取第一个视频文件的目录作为目标目录
            first_video_path = next(iter(final_mapping.keys()))
            local_dir = Path(first_video_path).parent

            # NFO 冲突检测与覆盖弹窗
            existing_nfos = []
            
            # 1. 检测 tvshow.nfo：只有当 ID 匹配时才考虑覆盖（说明是更新），ID 不匹配时直接忽略（说明是平铺结构下的另一个动画）
            dest_nfo_path = local_dir / "tvshow.nfo"
            if dest_nfo_path.exists():
                current_b_id = data.get('id')
                existing_b_id = FileManager.read_bangumi_id_from_nfo(str(dest_nfo_path))
                # 只有当 ID 相同（更新）或者无法读取 ID（旧数据）时，才加入覆盖提醒
                if not existing_b_id or (current_b_id and int(existing_b_id) == int(current_b_id)):
                    existing_nfos.append("tvshow.nfo")

            # 2. 检测单集 NFO：只检测本次匹配到的视频对应的 NFO
            for v_path in final_mapping.keys():
                nfo_p = Path(v_path).with_suffix('.nfo')
                if nfo_p.exists():
                    existing_nfos.append(nfo_p.name)

            overwrite_all = False

            if existing_nfos:
                # 优化逻辑：从配置中读取是否自动覆盖
                config = ConfigLoader()
                auto_overwrite = config.config.get("auto_overwrite_nfo", False)
                
                if auto_overwrite:
                    overwrite_all = True
                    logger.info("检测到旧 NFO，根据配置自动执行覆盖。")
                else:
                    reply = QMessageBox.question(
                        self,
                        "发现旧版 NFO 数据",
                        f"检测到当前目录下已存在 {len(existing_nfos)} 个 NFO 文件\n（如: {existing_nfos[0]} 等）。\n\n"
                        f"为确保【逻辑媒体库】能读取到最新格式的数据，强烈建议覆盖。\n\n是否使用最新拉取的数据覆盖它们？",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    overwrite_all = (reply == QMessageBox.Yes)

            # 构建批量写入任务列表
            task_list = []

            task_list.append({
                "type": "tvshow",
                "dest": str(local_dir),
                "nfo": data,
                "overwrite": overwrite_all
            })

            for v_path, ep_data in final_mapping.items():
                if ep_data and ep_data.get("type") != "special":
                    # ==========================================
                    # ✅ 多季支持：将单集的 season 信息注入 show_data
                    # 这样 write_episode_nfo 就能从 show_data 中读到正确的季
                    # ==========================================
                    episode_show_data = dict(data) if data else {}
                    ep_season = ep_data.get("season") or ep_data.get("season_number")
                    if ep_season is not None:
                        episode_show_data["season"] = ep_season

                    task_list.append({
                        "type": "episode",
                        "video_path": v_path,
                        "nfo": ep_data,
                        "show_data": episode_show_data,
                        "overwrite": overwrite_all
                    })

            logger.info(f"UI发起批量写盘任务，共生成 {len(task_list)} 个写入指令。")

            # 清理历史 IO 线程遗迹
            if hasattr(self, 'io_worker'):
                try:
                    if self.io_worker.isRunning():
                        self.io_worker.cancel()
                        self.io_worker.quit()
                        self.io_worker.wait()
                except RuntimeError:
                    pass

            self.progress_dialog = ProgressDialog(self)
            self.io_worker = FileIOWorker(task_list=task_list)

            self.io_worker.progress_update.connect(self.progress_dialog.update_progress)
            self.io_worker.finished_signal.connect(self._on_execution_finished)
            self.io_worker.error_signal.connect(lambda err: logger.error(f"IO后台警告: {err}"))
            self.io_worker.finished_signal.connect(self._on_scrape_finished_refresh)

            self.io_worker.start()
            self.progress_dialog.exec()
        finally:
            self._is_executing = False

    @Slot(int, int)
    def _on_execution_finished(self, success_count: int, total_count: int):
        """底层写盘结束后的 UI 收尾逻辑"""
        self.progress_dialog.accept()

        # ✅ 强制重置逻辑媒体库的索引缓存，确保下次切换 Tab 时重新扫描
        self.full_library_index = None

        if success_count == total_count:
            logger.info(f"刮削与写盘全部成功: {success_count}/{total_count}")
            QMessageBox.information(self, "执行成功", "刮削大成功！\n文件已整理至指定的媒体库目录。")
            self.detail_card_panel.clear_data()
            self.statusBar().showMessage("✅ 刮削与整理完毕，系统空闲。", 5000)
        else:
            error_msg = f"成功 {success_count}/{total_count} 个任务"
            logger.error(f"执行流发生错误: {error_msg}")
            QMessageBox.warning(
                self, "写盘遭遇错误",
                f"处理过程中发生异常：\n{error_msg}\n请通过控制台或 SSH 检查 NAS 的目录权限及底层日志。"
            )
            self.statusBar().showMessage("❌ 部分文件写入失败，请检查硬盘状态或权限。", 5000)

    # ==========================================
    # 逻辑媒体库
    # ==========================================

    @Slot(int)
    def _on_main_tab_changed(self, index: int):
        """懒加载逻辑库"""
        if index == 1:
            root_dir = self.media_list_panel.current_local_root
            if not root_dir:
                self.library_panel.lbl_status.setText(
                    "⚠️ 请先在【刮削作业台】左侧点击'选择/刷新媒体库'按钮选择整个大盘根目录！"
                )
                return

            self.statusBar().showMessage("正在极速逆向解析本地 NFO...", 0)
            # ✅ 检查是否已经有 full_library_index，避免重复构建
            if not hasattr(self, 'full_library_index') or self.full_library_index is None:
                index_data = LibraryIndexer.build_library_index(root_dir)
                self.full_library_index = index_data
            else:
                index_data = self.full_library_index

            self.library_panel.load_library(index_data)
            self.statusBar().showMessage("✅ 逻辑媒体库构建完成！", 5000)

    @Slot(object)
    def _handle_library_show_request(self, show_data):
        """处理面板传来的点击事件，优先读本地缓存，没有再发网络请求"""
        b_id = show_data.get('bangumi_id')
        if not b_id:
            QMessageBox.warning(
                self, "数据缺失",
                "该剧集没有 Bangumi ID 记录，无法拉取网络单集。请回刮削台重新刮削一次该剧集总目录。"
            )
            return

        self._current_library_show = show_data

        # ✅ 优先读本地磁盘缓存
        cached = get_cached_episodes(int(b_id))
        if cached:
            logger.info(f"📦 命中本地缓存 (ID: {b_id})，共 {len(cached)} 集")
            self.statusBar().showMessage(f"📦 命中本地缓存 (ID: {b_id})，共 {len(cached)} 集", 5000)
            self._render_combined_episodes(show_data, cached)
        else:
            # ✅ 线程安全：始终确保在启动新 worker 前，旧 worker 已被妥善处理
            self._cleanup_old_worker()

            self.statusBar().showMessage(f"正在从 Bangumi 拉取全量单集 (ID: {b_id})...", 0) # 显示信息不自动消失
            self._is_library_fetching = True

            self.scrape_worker = ScrapeWorker(subject_id=b_id)
            self.scrape_worker.progress_signal.connect(self.statusBar().showMessage)
            # ✅ 这里使用 lambda 包装，将 show_data 传递给 _on_scrape_finished_for_library，以便于在 worker 返回时正确处理
            self.scrape_worker.result_signal.connect(
                lambda results, poster_bytes: self._on_scrape_finished_for_library(results, poster_bytes, show_data)
            )
            self.scrape_worker.error_signal.connect(self._on_scrape_error)
            self.scrape_worker.start()

    def _render_combined_episodes(self, show_data: dict, network_episodes: list):
        """缝合本地路径与网络单集字典，喂给面板渲染"""
        folder_path = show_data.get('local_dir') or show_data.get('folder_path') or show_data.get('path')

        if not folder_path:
            for attr_name, attr_val in self.__dict__.items():
                if isinstance(attr_val, dict):
                    if ('path' in attr_val or 'local_dir' in attr_val) and (
                        attr_val.get('id') == show_data.get('id')
                    ):
                        folder_path = attr_val.get('path') or attr_val.get('local_dir')
                        logger.debug(
                            f"🎯 [路径抢救成功] 从主窗口的 {attr_name} 中挖出了真实物理路径: {folder_path}"
                        )
                        break

        if folder_path:
            show_data['local_dir'] = folder_path
        else:
            logger.warning("🚨 [警报] 翻遍了内存也没找到该番剧的物理文件夹路径！缝合引擎可能会失效！")

        local_mapping = {}
        for ep in show_data.get("episodes", []):
            try:
                local_mapping[float(ep['ep'])] = ep.get('path', '文件丢失')
            except (ValueError, KeyError, TypeError):
                pass

        self.library_panel.render_episodes(network_episodes, local_mapping, show_data)

    @Slot(object, bytes, object)
    def _on_scrape_finished_for_library(self, results, poster_bytes, show_data):
        """逻辑媒体库专用回调：Worker 返回剧集数据后，保存缓存并渲染"""
        if isinstance(results, dict) and "episodes" in results:
            episodes = results.get("episodes", [])
            details = results.get("details", {})
            b_id = details.get('id') or show_data.get('bangumi_id')
            if b_id:
                save_cached_episodes(int(b_id), episodes)
            self._render_combined_episodes(show_data, episodes)
            self.statusBar().showMessage(f"✅ 已加载【{show_data.get('title')}】共 {len(episodes)} 集", 5000)
        else:
            logger.error(f"逻辑媒体库数据格式异常: {type(results)}")
            self.statusBar().showMessage("❌ 剧集数据格式异常，请检查网络或重新刮削", 5000)

    @Slot(object, object)
    def _handle_manual_link(self, ep_data, show_data):
        """处理手动修改物理文件的请求"""
        import os

        start_dir = show_data.get('dir_path', '')
        ep_title = ep_data.get('name_cn') or ep_data.get('name') or "未知集"

        file_path, _ = QFileDialog.getOpenFileName(
            self, f"为【{ep_title}】手动关联本地视频文件", start_dir,
            "视频文件 (*.mkv *.mp4 *.avi *.rmvb *.ts)"
        )

        if file_path:
            success = FileManager.write_episode_nfo(file_path, ep_data)
            if success:
                QMessageBox.information(
                    self, "绑定成功",
                    f"成功将物理文件映射至该集！\n已生成: {os.path.basename(file_path)}.nfo"
                )

                new_index = LibraryIndexer.build_library_index(self.media_list_panel.current_local_root)
                self.library_panel.load_library(new_index)
                self._handle_library_show_request(new_index.get(start_dir, show_data))
            else:
                QMessageBox.warning(self, "错误", "NFO 写入失败，请检查目录权限。")

    # ==========================================
    # 线程安全与生命周期
    # ==========================================

    def closeEvent(self, event):
        """拦截关闭事件，确保后台线程安全退出"""
        io_running = hasattr(self, 'io_worker') and self.io_worker.isRunning()
        scrape_running = hasattr(self, 'scrape_worker') and self.scrape_worker.isRunning()

        if io_running or scrape_running:
            reply = QMessageBox.question(
                self,
                '退出程序',
                '系统后台正在执行数据读写或网络刮削任务。\n现在强行退出可能会导致数据损坏。\n\n确定要强行退出吗？',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self._kill_all_threads()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def _kill_all_threads(self):
        """安全终止所有后台 Worker"""
        self.statusBar().showMessage("正在强制终止后台任务，请稍候...")

        if hasattr(self, 'io_worker') and self.io_worker.isRunning():
            self.io_worker.cancel()
            self.io_worker.quit()
            self.io_worker.wait()

        if hasattr(self, 'scrape_worker') and self.scrape_worker.isRunning():
            self.scrape_worker.cancel()
            self.scrape_worker.quit()
            self.scrape_worker.wait()

    def _cleanup_old_worker(self):
        """线程安全收容所：通过显式同步等待和信号阻断防止线程崩溃"""
        if hasattr(self, 'scrape_worker') and self.scrape_worker is not None:
            try:
                if self.scrape_worker.isRunning():
                    # 1. 触发内部中断标志
                    if hasattr(self.scrape_worker, 'cancel'):
                        self.scrape_worker.cancel()
                    
                    # 2. 阻断信号连接，防止过时信号回调 UI
                    try:
                        self.scrape_worker.result_signal.disconnect()
                        self.scrape_worker.error_signal.disconnect()
                        self.scrape_worker.progress_signal.disconnect()
                    except (RuntimeError, TypeError):
                        pass

                    # 3. 发出退出指令并同步等待（由于设置了 _is_cancelled，run 方法会很快退出）
                    self.statusBar().showMessage("正在切换任务，请稍候...")
                    self.scrape_worker.quit()
                    # 设定 1 秒超时，防止网络 IO 导致阻塞
                    if not self.scrape_worker.wait(1000):
                        # 如果 wait 超时，将其加入僵尸队列，主循环择机清理
                        if not hasattr(self, '_zombie_threads'):
                            self._zombie_threads = []
                        self._zombie_threads.append(self.scrape_worker)
            except RuntimeError:
                pass
            finally:
                self.scrape_worker = None

    # ==========================================
    # 刷新回调
    # ==========================================

    @Slot(int, int)
    def _on_scrape_finished_refresh(self, success_count, total_count):
        """写盘完成后的回调：刷新逻辑媒体库视图"""
        if hasattr(self, 'current_selected_tvshow') and self.current_selected_tvshow:
            folder_path = self.current_selected_tvshow.get('local_dir')
            if folder_path:
                self.statusBar().showMessage("正在同步刷新逻辑媒体库视图...")
                updated_episodes = self._parse_local_episode_nfos(folder_path)
                self.current_episodes = updated_episodes
                self.update_logical_view(updated_episodes)

    def update_logical_view(self, updated_episodes):
        """刷新逻辑媒体库的剧集列表视图"""
        if hasattr(self, '_current_library_show') and self._current_library_show:
            local_mapping = {}
            for ep in updated_episodes:
                try:
                    ep_num = ep.get('ep_number') or ep.get('sort') or ep.get('episode')
                    if ep_num is not None:
                        local_mapping[float(ep_num)] = ep.get('video_path') or ep.get('path', '文件丢失')
                except (ValueError, TypeError):
                    pass
            self.library_panel.render_episodes(updated_episodes, local_mapping, self._current_library_show)

    def _on_manual_refresh_clicked(self):
        """手动刷新逻辑：重新走一遍完美路由"""
        if hasattr(self, 'current_selected_tvshow') and self.current_selected_tvshow:
            show_title = self.current_selected_tvshow.get('title', '当前番剧')
            self.statusBar().showMessage(f"🔄 正在重新扫描物理硬盘，刷新【{show_title}】...")
            # ✅ 增加一个标志位，让 _route_list_selection 知道这是手动刷新过来的请求
            refresh_data = dict(self.current_selected_tvshow)
            refresh_data["is_manual_refresh"] = True
            self._route_list_selection(refresh_data)
        else:
            self.statusBar().showMessage("⚠️ 请先在左侧选择一个番剧才能刷新")

    # ==========================================
    # 批量下载未缓存剧集详情
    # ==========================================

    @Slot(object)
    def _on_batch_download(self, all_shows: list):
        """批量下载所有未缓存的剧集详情数据，带进度窗口"""
        from utils.network_cache import get_cached_episodes
        from core.scraper_bangumi import BangumiScraper
        from PySide6.QtWidgets import QProgressBar, QApplication
        import time

        # 筛选出未缓存的剧集
        uncached_shows = []
        for show in all_shows:
            b_id = show.get("bangumi_id")
            if b_id and not get_cached_episodes(int(b_id)):
                uncached_shows.append(show)

        if not uncached_shows:
            QMessageBox.information(self, "无需下载", "所有已识别动画的剧集详情均已缓存，无需下载。")
            return

        # 弹出确认对话框
        reply = QMessageBox.question(
            self, "批量下载确认",
            f"将下载 {len(uncached_shows)} 部尚未缓存的动画剧集详情。\n\n"
            f"每部动画约需 2-3 秒（含 Bangumi API 节流延迟），\n"
            f"预计总耗时约 {len(uncached_shows) * 2.5:.0f} 秒。\n\n"
            f"是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        # 创建进度对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("批量下载剧集详情")
        dialog.setMinimumSize(450, 150)
        dialog.resize(500, 160)
        dialog.setWindowModality(Qt.ApplicationModal)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        lbl_status = QLabel(f"准备下载 {len(uncached_shows)} 部动画的剧集详情...")
        lbl_status.setStyleSheet("font-weight: bold; color: #333;")
        layout.addWidget(lbl_status)

        progress_bar = QProgressBar(dialog)
        progress_bar.setRange(0, len(uncached_shows))
        progress_bar.setValue(0)
        progress_bar.setTextVisible(True)
        layout.addWidget(progress_bar)

        lbl_detail = QLabel("")
        lbl_detail.setStyleSheet("color: #666;")
        layout.addWidget(lbl_detail)

        dialog.show()

        # 同步执行批量下载（在 UI 线程中执行，但通过 QApplication.processEvents 保持界面响应）
        scraper = BangumiScraper()
        success_count = 0
        fail_count = 0

        for idx, show in enumerate(uncached_shows):
            title = show.get("title", "未知剧集")
            b_id = show.get("bangumi_id")

            lbl_status.setText(f"正在下载 ({idx+1}/{len(uncached_shows)}): {title}")
            lbl_detail.setText(f"Bangumi ID: {b_id}")
            progress_bar.setValue(idx)
            QApplication.processEvents()

            try:
                episodes = scraper.get_episodes(int(b_id))
                if episodes:
                    save_cached_episodes(int(b_id), episodes)
                    success_count += 1
                    logger.info(f"✅ 批量下载成功: {title} (ID: {b_id})，{len(episodes)} 集")
                else:
                    fail_count += 1
                    logger.warning(f"⚠️ 批量下载返回空: {title} (ID: {b_id})")
            except Exception as e:
                fail_count += 1
                logger.error(f"❌ 批量下载失败: {title} (ID: {b_id}): {e}")

            # 强制刷新 UI
            QApplication.processEvents()

        # 完成
        progress_bar.setValue(len(uncached_shows))
        lbl_status.setText(f"✅ 下载完成！成功: {success_count}，失败: {fail_count}")
        lbl_detail.setText("")

        # 刷新逻辑媒体库视图（如果有选中的剧集）
        if hasattr(self, '_current_library_show') and self._current_library_show:
            self._handle_library_show_request(self._current_library_show)

        # 更新状态栏文字
        self.library_panel.lbl_status.setText(
            f"📊 逻辑媒体库：批量下载完成，成功 {success_count}/{len(uncached_shows)} 部"
        )

        # 3 秒后自动关闭
        import time as time_module
        for remaining in range(3, 0, -1):
            lbl_detail.setText(f"窗口将在 {remaining} 秒后自动关闭...")
            QApplication.processEvents()
            time_module.sleep(1)

        dialog.accept()

        self.statusBar().showMessage(f"✅ 批量下载完成：成功 {success_count}，失败 {fail_count}", 5000)
