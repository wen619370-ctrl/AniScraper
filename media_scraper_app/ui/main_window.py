# 文件路径: ui/main_window.py
# 新增引入 IO 线程、进度弹窗、日志与消息框
from PySide6.QtGui import QPixmap
from workers.file_io_worker import FileIOWorker
from ui.dialogs.progress_dialog import ProgressDialog
from utils.logger import logger
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFrame, 
    QSplitter, QMessageBox, QDialog, QTabWidget, # 👉 确保这里有 QMessageBox
    QInputDialog, QFileDialog
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction

from core.matcher import EpisodeMatcher
from ui.dialogs.match_dialog import MatchDialog
from ui.dialogs.settings_dialog import SettingsDialog
# 引入我们写好的三个 UI 乐高积木
from ui.widgets.search_panel import SearchPanel
from ui.widgets.media_list import MediaListPanel
from ui.widgets.detail_card import DetailCardPanel
from pathlib import Path  # 确保文件顶部引入了 Path
# 引入异步调度中枢
from workers.scrape_worker import ScrapeWorker
# 引入我们 V4.0 刚写的两个核心组件
from ui.widgets.library_panel import LibraryPanel
from core.library_indexer import LibraryIndexer

from PySide6.QtWidgets import QInputDialog, QFileDialog, QMessageBox
from PySide6.QtGui import QAction  # ✅ 必须从 QtGui 引入！
from utils.config_loader import ConfigLoader

from PySide6.QtGui import QIcon
from utils.path_resolver import get_resource_path

from PySide6.QtWidgets import QMainWindow, QSplitter
from PySide6.QtCore import Qt
from ui.widgets.log_console import LogConsole
# 引入基础 logger 和挂载函数
from utils.logger import logger, attach_qt_ui_handler

from PySide6.QtGui import QIcon
from utils.path_resolver import get_resource_path

class MainWindow(QMainWindow):
    """
    全局主窗体控制器。
    负责 UI 组件的排版拼装，以及前端与底层异步 Worker 的神经连线。
    """
    def __init__(self):
        super().__init__()

        # ✅ 核心防阻塞：此时 QApplication 已经创建，挂载 Qt 信号器绝对丝滑！
        attach_qt_ui_handler()
        
        self.setWindowTitle("AniScraper v1.0")

        # ✅ 给当前主窗口挂载左上角图标
        try:
            icon_path = get_resource_path("resources/icons/app.png")
            self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass
        
        self.setMinimumSize(1024, 768)

        self._setup_menu_bar()
        self._setup_status_bar()
        self._setup_ui()
        
        # 【核心新增】：执行全局神经连线
        self._connect_global_signals()
        # 【新增】：用于缓存当前正在操作的本地文件夹路径
        self.current_local_path = None
        self.network_episodes_cache = {}

        self._setup_main_layout()
        self._connect_logger()


    def _setup_main_layout(self):
        """
        完美无缝嵌入日志面板，并加装状态栏抽屉开关
        """
        from PySide6.QtWidgets import QPushButton # 确保按钮被引入
        
        # 1. 拿到你原来的整个上半部分主界面
        original_main_widget = self.centralWidget()

        # 2. 创建一个全局垂直分割器
        self.v_splitter = QSplitter(Qt.Vertical)

        # ✅ V6.0 优化：把隐形的拖拽条变宽，并加上灰色提示背景，方便用户抓取
        self.v_splitter.setHandleWidth(6)
        self.v_splitter.setStyleSheet("""
            QSplitter::handle:vertical {
                background-color: #f0f0f0;
                border-top: 1px solid #ddd;
                border-bottom: 1px solid #ddd;
            }
            QSplitter::handle:vertical:hover {
                background-color: #d0d0d0; /* 鼠标悬浮时变深，提示可拖拽 */
            }
        """)

        # 3. 把原来的主界面安全地塞进分割器的上半部分
        if original_main_widget:
            self.v_splitter.addWidget(original_main_widget)

        # 4. 创建日志面板，并塞进分割器的下半部分
        from ui.widgets.log_console import LogConsole
        self.log_console = LogConsole()
        self.v_splitter.addWidget(self.log_console)

        # 5. 设置上下比例并挂载为中心容器
        self.v_splitter.setSizes([800, 200])
        self.setCentralWidget(self.v_splitter)

        # ==========================================
        # ✅ V6.0 最终优化：日志抽屉开关 (状态栏常驻)
        # ==========================================
        self.log_console.setVisible(False)  # 默认隐藏，保持界面清爽
        
        self.btn_toggle_log = QPushButton("📝 运行日志")
        self.btn_toggle_log.setCheckable(True) # 让按钮拥有按下/弹起的状态
        self.btn_toggle_log.setChecked(False)
        self.btn_toggle_log.setFlat(True)      # 设置为扁平化，融入状态栏
        self.btn_toggle_log.setStyleSheet("QPushButton:checked { color: #4a90e2; font-weight: bold; }")
        
        # 绑定点击事件
        self.btn_toggle_log.clicked.connect(self._toggle_log_console)
        
        # addPermanentWidget 会把组件永久钉在状态栏的【最右侧】
        self.statusBar().addPermanentWidget(self.btn_toggle_log)

    def _toggle_log_console(self, checked: bool):
        """控制日志面板的呼出与收起"""
        self.log_console.setVisible(checked)
        
        # 当被呼出时，给主界面极大的比重 (比如 1000)，给日志极小的比重 (120)
        # 这样它只会占用底部很小的一条，剩下的由用户自己决定是否往上拉
        if checked:
            self.v_splitter.setSizes([1000, 120])

    def _connect_logger(self):
        """
        最重要的神经连线：将 logger 的信号跨线程连接到 UI
        """
        # 访问我们在 setup_logger 中挂载的 signaler
        if hasattr(logger, 'signaler'):
            logger.signaler.log_signal.connect(self.log_console.append_log)
        
        # 顺便测试一下
        logger.info("AniScraper V6.0 系统启动成功，日志监控已就绪。")

    def _open_settings(self):
        """打开设置面板并监听配置变更信号"""
        from ui.dialogs.settings_dialog import SettingsDialog # 确保顶部或此处引入了弹窗
        
        dialog = SettingsDialog(self)
        # ✅ 将弹窗的“设置已更新”信号，连接到主窗体的刷新方法上
        dialog.settings_updated.connect(self._on_settings_updated)
        dialog.exec()

    def _on_settings_updated(self):
        """
        【联动刷新引擎】
        当捕获到设置保存成功的信号时，触发各个 UI 组件的热重载
        """
        # 1. 强制重刷左侧媒体库列表（应用新的排序规则）
        if hasattr(self, 'media_list_panel'):
            self.media_list_panel.refresh_current_view()
            
        # 2. 底部状态栏给予轻量级反馈
        self.statusBar().showMessage("⚙️ 设置已更新，媒体库视图已自动重载。", 4000)


    def _setup_status_bar(self):
        self.statusBar().showMessage("系统就绪。")

    def _setup_ui(self):
        """主窗体 UI 组装"""
        
        # 1. 实例化所有基础组件 (这部分保留你原来的代码)
        self.search_panel = SearchPanel(self)
        self.media_list_panel = MediaListPanel(self)
        self.detail_card_panel = DetailCardPanel(self)
        
        # 2. 组装“旧版”的刮削工作台 (原先的右侧上下分栏，以及左右大分栏)
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.search_panel)
        right_layout.addWidget(self.detail_card_panel)
        
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        
        # 这个 scraping_splitter 就是你 V1.0~V3.0 一直在用的主视图
        scraping_splitter = QSplitter(Qt.Horizontal)
        scraping_splitter.addWidget(self.media_list_panel)
        scraping_splitter.addWidget(right_widget)
        scraping_splitter.setSizes([300, 700]) # 左 3 右 7

        # ==========================================
        # 【V4.0 核心改动开始】：引入 QTabWidget 作为最顶层容器
        # ==========================================
        self.main_tab = QTabWidget()
        self.main_tab.setStyleSheet("""
            QTabWidget::pane { border-top: 2px solid #4a90e2; }
            QTabBar::tab { padding: 10px 20px; font-size: 14px; font-weight: bold; }
            QTabBar::tab:selected { color: #4a90e2; background: #f0f8ff; }
        """)

        # 3. 将旧的刮削大局塞进 Tab 1
        self.main_tab.addTab(scraping_splitter, "🛠️ 刮削作业台")

        # 4. 实例化新的逻辑媒体库，并塞进 Tab 2
        self.library_panel = LibraryPanel()
        # ===================================
        # ✅ 跨组件连接：把面板里的刷新按钮，连接到主窗口的刷新方法上！
        # ==========================================
        if hasattr(self.library_panel, 'btn_refresh'):
            self.library_panel.btn_refresh.clicked.connect(self._on_manual_refresh_clicked)

        self.main_tab.addTab(self.library_panel, "📊 逻辑媒体库")

        # 5. 将大 Tab 设为窗口的心脏
        self.setCentralWidget(self.main_tab)


        try:
            icon_path = get_resource_path("resources/icons/app.ico")
            self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            pass # 如果你还没准备好 .ico 图标文件，直接跳过防报错

    def _connect_global_signals(self):
        """【神经连线核心】：将所有组件和后台 Worker 缝合在一起"""
        
        # 1. 前端内部闭环：左侧列表点击 -> 右侧卡片展示详情
        self.media_list_panel.item_selected.connect(self._route_list_selection)
        
        # 2. 搜索流：顶部面板发出搜索请求 -> 触发槽函数启动 Worker
        self.search_panel.search_requested.connect(self._start_scraping)
        # 3. 执行流：右侧卡片点击确认 -> 触发底层物理写盘
        self.detail_card_panel.execute_requested.connect(self._handle_execution)
        # 监听顶层 Tab 的切换动作
        self.main_tab.currentChanged.connect(self._on_main_tab_changed)


    @Slot(str, str)
    def _start_scraping(self, keyword: str, source: str):
        # 【终极防御】：加装 try-except 防弹衣，无视幽灵外壳
        if hasattr(self, 'scrape_worker'):
            try:
                if self.scrape_worker.isRunning():
                    self.scrape_worker.cancel()
                    self.scrape_worker.quit()
                    self.scrape_worker.wait()
            except RuntimeError:
                pass # C++ 底层已经自然死亡并回收，直接放行

        """处理搜素请求，配置并启动异步线程"""
        # 防坑：每次必须新建 Worker 实例，因为上次跑完的对象已经 deleteLater 了
        self.scrape_worker = ScrapeWorker(keyword=keyword)
        
        # 连线 A：将后台进度文本直接怼给状态栏
        self.scrape_worker.progress_signal.connect(self.statusBar().showMessage)
        
        # 连线 B：将成功抓取的数据结果扔给回调函数处理
        self.scrape_worker.result_signal.connect(self._on_scrape_finished)
        
        # 连线 C：捕获异常，给出优雅的提示
        self.scrape_worker.error_signal.connect(self._on_scrape_error)
        
        # 界面重置：开始搜索时，清空右侧卡片残留数据
        self.detail_card_panel.clear_data()
        
        # 点火发射！(不会阻塞主 GUI)
        self.scrape_worker.start()

    @Slot(object, bytes)
    def _on_scrape_finished(self, results, poster_bytes):
        """处理网络数据和图片的最终回传"""
        
        if isinstance(results, list):
            # 模式A：这是搜索请求返回的列表
            self.media_list_panel.update_list(results, title="网络检索结果")
            self.statusBar().showMessage("✅ 检索完成！请在左侧选择正确条目。", 5000)
            
        elif isinstance(results, dict) and "details" in results:
            self.current_episodes = results.get("episodes", [])
            
            # 【V4.0 路由拦截】：如果是从逻辑媒体库发起的请求，缓存后直接渲染表格，不走原先的图片逻辑
            if getattr(self, '_is_library_fetching', False):
                self._is_library_fetching = False
                b_id = results['details']['id']
                self.network_episodes_cache[b_id] = self.current_episodes # 保存到字典直至程序退出
                self._render_combined_episodes(self._current_library_show, self.current_episodes)
                return
            
            # ... 下面保留你原先的 details_data 更新和海报加载代码 ...
            details_data = results["details"]
            self.detail_card_panel.update_data(details_data)
            
            # (下方保留你原有的 QPixmap 加载代码...)
            
            # 【核心】：在 UI 主线程安全地将 bytes 转换为 QPixmap
            if poster_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(poster_bytes)
                self.detail_card_panel.set_poster(pixmap)
                
            self.statusBar().showMessage("✅ 详情与海报加载完毕！", 5000)
            # 【一键追番核心串联】：如果带有静默追番标志，数据加载完直接弹出单集核对框！
            if getattr(self, '_auto_pop_match', False):
                self._auto_pop_match = False
                # 直接拿着刚热乎的网络数据，自动帮你点击“确认刮削”按钮一样的效果
                self._handle_execution(details_data)
    @Slot(str)
    def _on_scrape_error(self, err_msg):
        """网络或解析错误处理"""
        # 发生错误时，确保搜索面板的按钮恢复可用
        self.search_panel.reset_state() 
        self.statusBar().showMessage(f"❌ 刮削失败: {err_msg}", 5000)


    @Slot(dict)
    def _on_auto_pop_match_dialog(self, remote_data: dict):
        """后台拿到剧集数据后，全自动模拟点击，呼出核对弹窗！"""
        self.statusBar().showMessage("剧集数据恢复成功，正在打开核对窗口...")
        
        # 1. 提取单集列表喂给弹窗下拉菜单
        self.current_episodes = remote_data.get('episodes', [])
        
        # 2. 提取整部剧的总元数据 (标题、简介、ID 等)
        details_data = remote_data.get('details', remote_data)
        
        # 3. 满足你的终极诉求：无需人为干预，直接强行呼出匹配核对弹窗！
        # ✅ 核心修复：把热乎的数据原封不动地传给写盘引擎！绝对不能再传 None 了！
        if hasattr(self, '_handle_execution'):
            self._handle_execution(details_data)
    
    @Slot(object)
    def _handle_execution(self, data):
        """处理最终的确认执行操作，弹出匹配核对框，确认后真实物理写盘！"""
        
        if not self.current_local_path:
            QMessageBox.warning(self, "操作异常", "请先在左侧【本地库】中选择一个需要刮削的文件夹！")
            return

        # 1. 扫描当前文件夹下的所有视频文件 (使用 V3.0 过滤引擎)
        from core.file_manager import FileManager
        video_dicts = FileManager.get_valid_video_files(self.current_local_path)
        
        # 2. 提取缓存的网络单集数据
        remote_episodes = getattr(self, 'current_episodes', [])

        # ==========================================
        # ✅ 终极防弹装甲：拦截“静默失败”，给予用户明确指引！
        # ==========================================
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

        # 3. 核心计算：后台静默正则匹配 (上面已经做过非空拦截，这里直接执行)
        final_mapping = {}
        match_result = EpisodeMatcher.smart_match(video_dicts, remote_episodes)

        # 4. 弹出核对窗 (阻塞线程)
        dialog = MatchDialog(video_dicts, remote_episodes, match_result, self)
        
        if dialog.exec() == QDialog.Accepted:
            # ✅ 关键修改：必须从 dialog 获取结果，覆盖掉原来的 final_mapping！
            final_mapping = dialog.get_final_mapping()
        else:
            return # 用户点击了取消，终止写盘流程
        
        if not final_mapping:
            self.statusBar().showMessage("没有有效的匹配项需要写入。")
            return
        
        # ... (下方保留你原有的写盘逻辑：from pathlib import Path ...)
        # ... (上方代码保留：弹出核对窗 dialog.exec()，获取了 final_mapping) ...
        from pathlib import Path
        local_dir = Path(self.current_local_path)
        # 【V4.1 新增逻辑：NFO 冲突检测与覆盖弹窗】
        existing_nfos = []
        dest_nfo_path = local_dir / "tvshow.nfo"
        if dest_nfo_path.exists():
            existing_nfos.append("tvshow.nfo")
            
        for v_path in final_mapping.keys():
            nfo_p = Path(v_path).with_suffix('.nfo')
            if nfo_p.exists():
                existing_nfos.append(nfo_p.name)

        # 默认是否覆盖的标志位
        overwrite_all = False 
        
        if existing_nfos:
            reply = QMessageBox.question(
                self, 
                "发现旧版 NFO 数据",
                f"检测到当前目录下已存在 {len(existing_nfos)} 个 NFO 文件\n（如: {existing_nfos[0]} 等）。\n\n为确保【逻辑媒体库】能读取到最新格式的数据，强烈建议覆盖。\n\n是否使用最新拉取的数据覆盖它们？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            overwrite_all = (reply == QMessageBox.Yes)
        
        # 5. 构建批量写入任务列表
        task_list = []

        # 任务 A: 生成整部的 tvshow.nfo
        task_list.append({
            "type": "tvshow",
            # 【核心修复】：这里必须传目录 local_dir，绝对不能传包含文件名的 dest_nfo_path！
            "dest": str(local_dir), 
            "nfo": data,
            "overwrite": overwrite_all
        })

        # 任务 B: 遍历最终映射表，生成每一集的 NFO
        for v_path, ep_data in final_mapping.items():
            if ep_data and ep_data.get("type") != "special":
                task_list.append({
                    "type": "episode",
                    "video_path": v_path,
                    "nfo": ep_data,
                    "show_data": data,   # 【V5.0 核心新增】：把番剧总数据塞进任务包裹
                    "overwrite": overwrite_all
                })

        # ... (下方保留：启动 IO 线程) ...
        '''

        # 5. 构建批量写入任务列表
        task_list = []

        # 【修复关键】：把因为重构而不小心删掉的 local_dir 找回来！
        from pathlib import Path  # 如果文件顶部已经引入了 Path，这句可以不写
        

        # 任务 A: 生成整部的 tvshow.nfo
        dest_nfo = str(local_dir / "tvshow.nfo")
        task_list.append({
            "type": "tvshow",
            "dest": dest_nfo,
            "nfo": data
        })
        
        # ... (下方的 for 循环生成单集 NFO 保持不变) ...

        # 任务 B: 遍历最终映射表，生成每一集的 NFO
        for v_path, ep_data in final_mapping.items():
            if ep_data and ep_data.get("type") != "special":
                task_list.append({
                    "type": "episode",
                    "video_path": v_path,
                    "nfo": ep_data
                })
        '''

        logger.info(f"UI发起批量写盘任务，共生成 {len(task_list)} 个写入指令。")

        # 【终极防御】：清理历史 IO 线程遗迹
        if hasattr(self, 'io_worker'):
            try:
                if self.io_worker.isRunning():
                    self.io_worker.cancel()
                    self.io_worker.quit()
                    self.io_worker.wait()
            except RuntimeError:
                pass # C++ 底层已安息，放行

        # 6. 启动底层 IO 线程
        self.progress_dialog = ProgressDialog(self)
        self.io_worker = FileIOWorker(task_list=task_list)
        
        self.io_worker.progress_update.connect(self.progress_dialog.update_progress)
        self.io_worker.finished_signal.connect(self._on_execution_finished)
        self.io_worker.error_signal.connect(lambda err: logger.error(f"IO后台警告: {err}"))

        # ✅ 新增这行核心指令：监听写盘完成信号，触发 UI 热更新！
        # ==========================================
        self.io_worker.finished_signal.connect(self._on_scrape_finished_refresh)

        self.io_worker.start()
        self.progress_dialog.exec()

    @Slot(bool, str)
    def _on_execution_finished(self, success: bool, msg: str):
        """底层写盘结束后的 UI 收尾逻辑"""
        
        # 1. 关闭阻塞的进度条弹窗
        self.progress_dialog.accept()

        # 2. 弹窗与日志汇报
        if success:
            logger.info(f"刮削与写盘全部成功: {msg}")
            QMessageBox.information(self, "执行成功", f"刮削大成功！\n文件已整理至指定的媒体库目录。")
            
            # UI 复位：清空右侧卡片，等待下一次点击
            self.detail_card_panel.clear_data()
            self.statusBar().showMessage("✅ 刮削与整理完毕，系统空闲。", 5000)
        else:
            logger.error(f"执行流发生致命错误: {msg}")
            QMessageBox.warning(self, "写盘遭遇错误", f"处理过程中发生异常：\n{msg}\n请通过控制台或 SSH 检查 NAS 的目录权限及底层日志。")
            self.statusBar().showMessage("❌ 文件写入失败，请检查硬盘状态或权限。", 5000)

    @Slot(object)
    def _fetch_details(self, raw_data):
        """点击列表项时，启动 Worker 获取详情和海报"""
        subject_id = raw_data.get('id')
        if not subject_id:
            return

        self.detail_card_panel.clear_data() # 请求前先清空旧卡片
        
        self.scrape_worker = ScrapeWorker(subject_id=subject_id)
        self.scrape_worker.progress_signal.connect(self.statusBar().showMessage)
        self.scrape_worker.result_signal.connect(self._on_scrape_finished)
        self.scrape_worker.error_signal.connect(self._on_scrape_error)
        self.scrape_worker.start()

    @Slot(object)
    def _route_list_selection(self, data: dict):
        """左侧列表点击事件的路由分发 (终极修复版)"""
        
        # ==========================================
        # 🛡️ 核心修复：先判断是不是网络搜索结果！
        # ==========================================
        # 如果带有 id 且没有 path，说明这是你手动/自动搜索出来的网络条目
        if 'id' in data and 'path' not in data:
            subject_id = data['id']
            self.statusBar().showMessage(f"正在拉取条目详情 (ID: {subject_id})...")

            # ✅ 核心调用：创建新线程前，先安置旧线程！
            # ==========================================
            # ✅ 唯一真理：只召唤收容所，绝对不要再加什么防弹装甲和 wait() 了！
            # ==========================================
            if hasattr(self, '_cleanup_old_worker'):
                self._cleanup_old_worker()
                
            # 重新实例化底层爬虫，直接拉取该条目详情并弹出核对窗口/详情页
            from workers.scrape_worker import ScrapeWorker
            self.scrape_worker = ScrapeWorker(subject_id=subject_id)
            self.scrape_worker.result_signal.connect(self._on_scrape_finished)
            from PySide6.QtWidgets import QMessageBox
            self.scrape_worker.error_signal.connect(lambda e: QMessageBox.warning(self, "网络错误", e))
            self.scrape_worker.start()
            return
        # ==========================================
        # 🛡️ 下面才是处理本地物理目录点击的逻辑
        # ==========================================
        is_scraped = data.get('is_scraped', False)
        folder_name = data.get('name', '未知文件夹')
        folder_path = data.get('path', '')

        self.current_local_path = folder_path

        if is_scraped:
            # 1. 读取 tvshow.nfo 的主数据
            if hasattr(self, '_show_local_scraped_info'):
                local_meta = self._show_local_scraped_info(folder_path)
                
                if local_meta:

                    # ✅ 终极源头注入：把物理路径死死焊在字典上！
                    # 绝对不能让这个承载着全村希望的字典空着手出门！
                    # ==========================================
                    local_meta['local_dir'] = folder_path
                    local_meta['path'] = folder_path
                    self.current_selected_tvshow = local_meta
                    
                    # ==========================================
                    # ✅ 终极架构转变：彻底断网，纯本地数据驱动弹窗！
                    # ==========================================
                    self.statusBar().showMessage(f"正在从本地读取单集 NFO 数据...")
                    
                    # 2. 直接从本地硬盘解析单集列表
                    local_episodes = self._parse_local_episode_nfos(folder_path)
                    self.current_episodes = local_episodes
                    
                    if local_episodes:
                        # 3. 本地有单集数据，拿着两份本地数据，直接强行呼出匹配核对弹窗！
                        if hasattr(self, '_handle_execution'):
                            self._handle_execution(local_meta)
                    else:
                        from PySide6.QtWidgets import QMessageBox
                        QMessageBox.information(self, "本地数据不全", "未能在这个目录下找到任何合法的【单集 .nfo】文件！\n核对弹窗因缺乏单集参照物而无法呼出。")

    def _show_local_scraped_info(self, folder_path: str) -> dict:
        """读取本地 NFO，并在后台偷偷提取媒体 ID 以备弹窗使用"""
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
            'subject_id': None  # ✅ 新增：用来存放挖出来的 ID
        }
        
        if os.path.exists(nfo_path):
            try:
                # ✅ 核心修复：把 'r' 改成 'rb' (读取二进制字节流)，去掉 encoding 参数！
                # 这样 Python 的 XML 引擎就不会再因为那句 <?xml...?> 头部声明而崩溃了！
                with open(nfo_path, 'rb') as f:
                    xml_content = f.read()
                
                if xml_content.strip():
                    root = ET.fromstring(xml_content)
                    title = root.findtext('title') or root.findtext('localtitle')
                    if title: local_meta['name'] = title
                    local_meta['summary'] = root.findtext('plot', '暂无简介')
                    local_meta['date'] = root.findtext('year', '')
                    
                    subject_id = None
                    for uid in root.findall('uniqueid'):
                        if uid.text:
                            subject_id = uid.text
                            break
                    if not subject_id:
                        subject_id = root.findtext('tmdbid') or root.findtext('bangumiid')
                        
                    local_meta['subject_id'] = subject_id
                    
            except Exception as e:
                from utils.logger import logger
                logger.error(f"读取本地 NFO 失败: {e}")
                
        poster_path = os.path.join(folder_path, "poster.jpg")
        if not os.path.exists(poster_path):
            poster_path = os.path.join(folder_path, "folder.jpg")
        if os.path.exists(poster_path):
            local_meta['cover_image'] = poster_path
            
        if hasattr(self, 'detail_panel'):
            self.detail_panel.update_ui(local_meta)
            
        return local_meta

    def _parse_local_episode_nfos(self, folder_path: str) -> list:
        """纯本地提取：递归穿透遍历目录下所有单集 NFO (完美支持多层嵌套子文件夹)"""
        import os
        from pathlib import Path
        import xml.etree.ElementTree as ET
        
        episodes = []
        # ==========================================
        # ✅ 核心升维：抛弃 os.listdir 的近视眼，换用 rglob 进行“X光级”深度递归搜索！
        # ==========================================
        for nfo_path_obj in Path(folder_path).rglob('*.nfo'):
            file_name = nfo_path_obj.name
            nfo_path = str(nfo_path_obj)
            
            # 排掉整部的 nfo，只抓单集
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
                
                # 只有带有集数标号的，才被认为是合法的剧集 NFO
                # ... 前面提取标题、集数的代码保持不变 ...
                if ep_num and ep_num.isdigit():
                        base_name = nfo_path_obj.stem 
                        parent_dir_name = nfo_path_obj.parent.name.lower()
                        
                        video_path = ""
                        # ==========================================
                        # 🔍 探照灯 1 号：看看探针到底在找什么文件名？
                        # ==========================================
                        from utils.logger import logger  # 确保导入了 logger
                        logger.debug(f"[探针准备] 正在为 NFO: {nfo_path_obj.name} 寻找旁边同名的视频文件...")

                        for ext in ['.mkv', '.mp4', '.avi', '.ts', '.rmvb']:
                            vid_file = nfo_path_obj.with_suffix(ext)
                            if vid_file.exists():
                                video_path = str(vid_file)
                                # ✅ 新增日志：如果找到了，大声喊出来！
                                logger.info(f"🎯 [探针命中] 成功找到视频实体: {video_path}")
                                break
                        
                        # ✅ 新增日志：如果遍历完都没找到，报个警！
                        if not video_path:
                            logger.warning(f"⚠️ [探针落空] 彻底摸空！在 {nfo_path_obj.parent} 目录下，没有找到名为 {base_name} 的任何视频文件！")

                        real_id_str = root.findtext('bangumiid') or root.findtext('tmdbid') or root.findtext('id')
                        real_id = int(real_id_str) if real_id_str and real_id_str.isdigit() else int(ep_num)
                        item_type = 'movie' if 'movie' in parent_dir_name or '剧场版' in base_name else 'episode'
                        
                        # ==========================================
                        # 🔍 探照灯 2 号：打印最终送给逻辑媒体库的字典结构！
                        # ==========================================
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
                        
                        logger.debug(f"[数据组装] 第 {ep_num} 集字典打包完毕，video_path 状态: {'有值' if video_path else '空'}")
                        episodes.append(ep_dict)
            except Exception as e:
                pass
                
        # 按照集数从小到大排个序
        episodes.sort(key=lambda x: x.get('ep_number', 0))
        return episodes


    @Slot(bool, str)
    def _on_execution_finished(self, success: bool, msg: str):
        """底层写盘结束后的 UI 收尾逻辑"""
        self.progress_dialog.accept()

        if success:
            logger.info(f"刮削与写盘全部成功: {msg}")
            QMessageBox.information(self, "执行成功", f"刮削大成功！\ntvshow.nfo 已成功写入目标文件夹！\n\n您可以点击左侧的【刷新媒体库】查看状态变化。")
            self.detail_card_panel.clear_data()
            self.statusBar().showMessage("✅ 刮削完毕，系统空闲。", 5000)
            self.current_local_path = None # 清空缓存，防止误操作
        else:
            logger.error(f"执行流发生致命错误: {msg}")
            QMessageBox.warning(self, "写盘遭遇错误", f"处理过程中发生异常：\n{msg}")
            self.statusBar().showMessage("❌ 文件写入失败。", 5000)
    def _connect_global_signals(self):
        """主控台中枢神经网：整合 V1~V4 的所有连线"""
        
        # ==========================================
        # 🔌 [V1.0 - V3.0] 刮削作业台的核心神经 (你弄丢的部分)
        # ==========================================
        # 1. 列表点击 -> 触发智能路由（负责自动搜索和静默追番弹窗）
        self.media_list_panel.item_selected.connect(self._route_list_selection)
        
        # 2. 搜索框回车/点击 -> 触发主动网络搜索
        self.search_panel.search_requested.connect(self._start_scraping)
        
        # 3. 右侧详情卡片点击“确认刮削” -> 触发匹配核对弹窗与写盘
        self.detail_card_panel.execute_requested.connect(self._handle_execution)


        # ==========================================
        # 🔌 [V4.0] 逻辑媒体库的核心神经
        # ==========================================
        # 4. 监听顶级 Tab 的来回切换，实现零卡顿懒加载
        self.main_tab.currentChanged.connect(self._on_main_tab_changed)
        
        # 5. 监听媒体库面板传来的请求（拉取网络数据 & 手动绑定物理文件）
        self.library_panel.request_network_episodes.connect(self._handle_library_show_request)
        self.library_panel.request_manual_link.connect(self._handle_manual_link)

    @Slot(int)
    def _on_main_tab_changed(self, index: int):
        """懒加载逻辑库，真正做到全局挂载"""
        if index == 1:
            # 【核心修复】：使用整个媒体库的根目录，而不是点选的子文件夹！
            root_dir = self.media_list_panel.current_local_root 
            if not root_dir:
                self.library_panel.lbl_status.setText("⚠️ 请先在【刮削作业台】左侧点击'选择/刷新媒体库'按钮选择整个大盘根目录！")
                return

            self.statusBar().showMessage("正在极速逆向解析本地 NFO...", 0)
            index_data = LibraryIndexer.build_library_index(root_dir)
            self.library_panel.load_library(index_data)
            self.statusBar().showMessage("✅ 逻辑媒体库构建完成！", 5000)

    @Slot(object)
    def _handle_library_show_request(self, show_data):
        """处理面板传来的点击事件，决定是读缓存还是发网络请求"""
        b_id = show_data.get('bangumi_id')
        if not b_id:
            QMessageBox.warning(self, "数据缺失", "该剧集没有 Bangumi ID 记录，无法拉取网络单集。请回刮削台重新刮削一次该剧集总目录。")
            return

        self._current_library_show = show_data # 暂存当前查看的剧集信息

        if b_id in self.network_episodes_cache:
            # 【核心诉求】：直接读取内存缓存，不发网络请求！
            self._render_combined_episodes(show_data, self.network_episodes_cache[b_id])
        else:
            # 缓存未命中，启动 Worker 拉取
            self.statusBar().showMessage(f"正在从 Bangumi 拉取全量单集 (ID: {b_id})...")
            self._is_library_fetching = True # 设置路由标志位
            self._fetch_details({'id': b_id})

    def _render_combined_episodes(self, show_data: dict, network_episodes: list):
        """缝合本地路径与网络单集字典，喂给面板渲染 (终极路径抢救版)"""
        from utils.logger import logger
        
        # ==========================================
        # 🚨 终极抢救：翻箱倒柜找回丢失的文件夹路径！
        # ==========================================
        folder_path = show_data.get('local_dir') or show_data.get('folder_path') or show_data.get('path')
        
        # 如果 show_data 里没带路径，我们就去主窗口的变量里强行“搜身”！
        if not folder_path:
            for attr_name, attr_val in self.__dict__.items():
                if isinstance(attr_val, dict):
                    # 只要这个字典里有 path，并且 id 匹配，那就是它！
                    if ('path' in attr_val or 'local_dir' in attr_val) and (attr_val.get('id') == show_data.get('id')):
                        folder_path = attr_val.get('path') or attr_val.get('local_dir')
                        logger.debug(f"🎯 [路径抢救成功] 从主窗口的 {attr_name} 中挖出了真实物理路径: {folder_path}")
                        break

        # 强行把找回的路径塞给下游的缝合引擎！
        if folder_path:
            show_data['local_dir'] = folder_path
        else:
            logger.warning("🚨 [警报] 翻遍了内存也没找到该番剧的物理文件夹路径！缝合引擎可能会失效！")
        # ==========================================


        # 将本地的字典列表转为 O(1) 查找的 {集数: 路径} (保留你的原有逻辑防呆)
        local_mapping = {}
        for ep in show_data.get("episodes", []):
            try:
                local_mapping[float(ep['ep'])] = ep.get('path', '文件丢失')
            except (ValueError, KeyError, TypeError):
                pass
                
        # 呼叫我们上一轮写好的、带“X光探针”的终极缝合引擎！
        self.library_panel.render_episodes(network_episodes, local_mapping, show_data)


    @Slot(object, object)
    def _handle_manual_link(self, ep_data, show_data):
        """处理手动修改物理文件的请求"""
        from PySide6.QtWidgets import QFileDialog
        from core.file_manager import FileManager
        import os

        # 锁定选择范围在当前番剧的目录下
        start_dir = show_data.get('dir_path', '')
        ep_title = ep_data.get('name_cn') or ep_data.get('name') or "未知集"
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"为【{ep_title}】手动关联本地视频文件", start_dir, "视频文件 (*.mkv *.mp4 *.avi *.rmvb *.ts)"
        )

        if file_path:
            # 直接在选中的视频文件旁生成标准 NFO，强制完成绑定！
            success = FileManager.write_episode_nfo(file_path, ep_data)
            if success:
                QMessageBox.information(self, "绑定成功", f"成功将物理文件映射至该集！\n已生成: {os.path.basename(file_path)}.nfo")
                
                # 重新扫描一遍当前目录，并刷新视图
                new_index = LibraryIndexer.build_library_index(self.media_list_panel.current_local_root)
                self.library_panel.load_library(new_index)
                
                # 再次触发点击，读取缓存刷新右侧表格
                self._handle_library_show_request(new_index.get(start_dir, show_data))
            else:
                QMessageBox.warning(self, "错误", "NFO 写入失败，请检查目录权限。")
    

    def closeEvent(self, event):
        """
        【全局生命周期防火墙】
        拦截主窗口的关闭事件，确保所有底层 C++ 线程安全退出，防止僵尸线程引发崩溃。
        """
        # 检查写盘线程是否在跑
        io_running = hasattr(self, 'io_worker') and self.io_worker.isRunning()
        # 检查网络爬虫线程是否在跑
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
                # 用户头铁非要退，那我们执行“优雅超度”
                self._kill_all_threads()
                event.accept() # 同意关闭窗口
            else:
                event.ignore() # 驳回关闭请求，当作无事发生
        else:
            event.accept()

    def _kill_all_threads(self):
        """【拔管程序】：安全终止所有后台 Worker"""
        self.statusBar().showMessage("正在强制终止后台任务，请稍候...")
        from PySide6.QtWidgets import QApplication
        
        # 杀死 IO 线程
        if hasattr(self, 'io_worker') and self.io_worker.isRunning():
            # 1. 挂上取消标志位 (让你线程里的 for 循环 break 出来)
            self.io_worker.cancel() 
            # 2. 告诉底层 Qt 事件循环准备退出
            self.io_worker.quit() 
            # 3. 【最核心的一步】：死死阻塞住主线程，直到 C++ 底层真正停机！绝不留僵尸！
            self.io_worker.wait() 

        # 同理，杀死爬虫线程
        if hasattr(self, 'scrape_worker') and self.scrape_worker.isRunning():
            self.scrape_worker.cancel() # 假设你的 ScrapeWorker 也有 cancel 方法
            self.scrape_worker.quit()
            self.scrape_worker.wait()

    def _setup_menu_bar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件(&F)")
        
        # ==========================================
        # V6.0 新增：添加新媒体库 Action
        # ==========================================
        add_lib_action = QAction("添加新媒体库...", self)
        add_lib_action.triggered.connect(self._on_add_new_library)
        file_menu.addAction(add_lib_action)
        
        file_menu.addSeparator()

        # ==========================================
        # ✅ V6.0 核心修复：连接到自定义方法，监听更新信号
        # ==========================================
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self._open_settings) # 👉 就是改了这一行！
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menubar.addMenu("帮助(&H)")
        about_action = QAction("关于", self)
        help_menu.addAction(about_action)

    def _on_add_new_library(self):
        """交互流：添加媒体库的全过程闭环"""
        # 第一步：让用户输入库名 (防坑：检查 ok 标志防取消崩溃)
        lib_name, ok = QInputDialog.getText(self, "添加新媒体库", "请输入媒体库昵称 (如: 主PT库, 老番库):")
        if not ok or not lib_name.strip():
            return

        # 第二步：选择物理文件夹
        lib_path = QFileDialog.getExistingDirectory(self, "选择媒体库根目录", "")
        if not lib_path:
            return # 用户点击了取消

        # 第三步：写入全局配置并保存
        ConfigLoader().add_library(lib_name.strip(), lib_path)
        self.statusBar().showMessage(f"✅ 成功添加媒体库：{lib_name}", 5000)

        # 第四步：神经传导 -> 通知左侧视图重刷下拉菜单！
        if hasattr(self, 'media_list_panel'):
            self.media_list_panel.update_library_combo()


    def _cleanup_old_worker(self):
        """
        🛡️ 防崩御甲：僵尸线程收容所 (终极 C++ 容错版)
        安全剥离旧线程，完美化解 Python 变量与 C++ 底层对象生命周期错位的崩溃！
        """
        # 1. 初始化收容所
        if not hasattr(self, '_zombie_threads'):
            self._zombie_threads = []
            
        # 2. 扫地僧：安全清理已经自然死亡的僵尸线程
        alive_zombies = []
        for t in self._zombie_threads:
            try:
                if t.isRunning():
                    alive_zombies.append(t)
            except RuntimeError:
                # 核心防弹：C++ 对象已被 Qt 底层彻底扬了灰，直接丢弃，不予理会！
                pass
        self._zombie_threads = alive_zombies
        
        # 3. 处理当前正在运行的 scrape_worker
        if hasattr(self, 'scrape_worker') and self.scrape_worker is not None:
            try:
                # 这一步是高危操作，如果底层已死，会直接跳到 except
                if self.scrape_worker.isRunning():
                    # (1) 挂起免战牌
                    if hasattr(self.scrape_worker, 'cancel'):
                        self.scrape_worker.cancel()
                        
                    # (2) 物理拔线
                    try:
                        self.scrape_worker.result_signal.disconnect()
                    except Exception:
                        pass 
                        
                    # (3) 扔进收容所
                    self._zombie_threads.append(self.scrape_worker)
            except RuntimeError:
                # 核心防弹：当前变量已经是空壳，说明线程早就跑完被回收了，安全跳过！
                pass
            finally:
                # 无论死活，彻底解绑当前变量，迎接新线程！
                self.scrape_worker = None


    @Slot(int, int)
    def _on_scrape_finished_refresh(self, success_count, total_count):
        """写盘完成后的回调：强行刷新界面，让逻辑媒体库同步最新数据"""
        # 1. 如果你在逻辑媒体库有一个专门的刷新按钮或刷新方法，直接调用它：
        # self.logical_library_tab.refresh_data()  <-- 假设你有这个方法
        
        # 2. 最简单粗暴的万能刷新法：模拟重新点击一次左侧选中的番剧！
        # 既然我们已经写好了强大的 _route_list_selection，只要再调一次它，
        # 它就会自动去硬盘里读出刚才写好的 NFO，瞬间把“未匹配”变成绿色的“已匹配”！
        if hasattr(self, 'current_selected_tvshow') and self.current_selected_tvshow:
            folder_path = self.current_selected_tvshow.get('local_dir')
            if folder_path:
                self.statusBar().showMessage("正在同步刷新逻辑媒体库视图...")
                
                # 重新解析一次硬盘里的最新单集数据
                updated_episodes = self._parse_local_episode_nfos(folder_path)
                self.current_episodes = updated_episodes
                
                # 重新渲染右侧表格 (假设你有一个更新表格的方法，比如 update_logical_view)
                if hasattr(self, 'update_logical_view'):
                    self.update_logical_view(updated_episodes)


    def _on_manual_refresh_clicked(self):
        """手动刷新逻辑：重新走一遍完美路由，无缝热更新！"""
        if hasattr(self, 'current_selected_tvshow') and self.current_selected_tvshow:
            show_title = self.current_selected_tvshow.get('title', '当前番剧')
            self.statusBar().showMessage(f"🔄 正在重新扫描物理硬盘，刷新【{show_title}】...")
            
            # ==========================================
            # ✅ 架构级的优雅：直接复用我们刚修好的完美路由！
            # 只要把当前存着的字典再喂给它一次，它就会自动去读硬盘、找路径、强行缝合！
            # ==========================================
            self._route_list_selection(self.current_selected_tvshow)
        else:
            self.statusBar().showMessage("⚠️ 请先在左侧选择一个番剧才能刷新")