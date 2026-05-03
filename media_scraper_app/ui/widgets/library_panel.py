from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter, QListWidget, QListWidgetItem, 
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QPushButton,
    QLineEdit # ✅ 新增引入搜索框组件
)
from PySide6.QtCore import Qt, Signal, Slot

class LibraryPanel(QWidget):
    # 信号定义：请求网络获取全量单集
    request_network_episodes = Signal(object) 
    # 信号定义：请求手动绑定物理文件 (参数：网络单集字典，当前剧集数据)
    request_manual_link = Signal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10) # 加上一点组件间距
        
        # 【状态栏美化与高度锁定】
        self.lbl_status = QLabel("📊 逻辑媒体库：等待扫描 (左侧列表基于本地，点击触发网络校验)")
        self.lbl_status.setFixedHeight(35) 
        self.lbl_status.setStyleSheet("""
            QLabel {
                font-weight: bold; 
                color: #333; 
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding-left: 10px;
            }
        """)
        main_layout.addWidget(self.lbl_status)

        self.splitter = QSplitter(Qt.Horizontal)
        
        # ==========================================
        # ✅ 重构左侧区域：套一层外壳，用来装【搜索框 + 列表】
        # ==========================================
        # ==========================================
        # ✅ 重构左侧区域：套一层外壳，用来装【搜索栏 + 列表】
        # ==========================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0) # 内部不再留白
        left_layout.setSpacing(5)

        # ==========================================
        # 🌟 核心修复：创建一个水平布局的“托盘”，把输入框和按钮肩并肩放进去！
        # ==========================================
        from PySide6.QtWidgets import QHBoxLayout
        search_toolbar_layout = QHBoxLayout()
        search_toolbar_layout.setSpacing(5)

        # 1. 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 检索左侧剧集...")
        self.search_input.setFixedHeight(30)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        
        # 把搜索框放进水平托盘的左边
        search_toolbar_layout.addWidget(self.search_input)

        # 2. 强制刷新按钮
        self.btn_refresh = QPushButton("🔄 刷新") # 名字稍微精简，免得占太多搜索框空间
        self.btn_refresh.setFixedHeight(30) # 让它和搜索框一样高，对齐才好看！
        self.btn_refresh.setToolTip("重新扫描本地 NFO 和视频文件，刷新当前视图")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                padding: 0px 12px;
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-weight: bold;
                color: #333;
            }
            QPushButton:hover { background-color: #e0e0e0; border-color: #999; }
            QPushButton:pressed { background-color: #d0d0d0; }
        """)

        # 把按钮放进水平托盘的右边
        search_toolbar_layout.addWidget(self.btn_refresh)

        # 3. 将这个装好东西的水平托盘，整体塞进左侧垂直大布局的顶部！
        left_layout.addLayout(search_toolbar_layout)
        # ==========================================

        # 2. 原来的左侧大纲列表
        self.list_shows = QListWidget()
        self.list_shows.setStyleSheet("""
            QListWidget { border: 1px solid #ddd; border-radius: 4px; background: #fff; }
            QListWidget::item { padding: 12px 8px; border-bottom: 1px solid #f5f5f5; }
            QListWidget::item:selected { background-color: #4a90e2; color: white; font-weight: bold;}
        """)
        self.list_shows.itemClicked.connect(self._on_show_clicked)
        left_layout.addWidget(self.list_shows)

        # 3. 将整个左侧外壳塞入 Splitter
        self.splitter.addWidget(left_widget)
        # ==========================================

        # 右侧：带有操作列的物理映射表
        self.table_episodes = QTableWidget()
        self.table_episodes.setColumnCount(4)
        self.table_episodes.setHorizontalHeaderLabels(["集数", "网络标准标题", "当前映射物理文件", "操作"])
        
        header = self.table_episodes.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) 
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) 
        header.setStretchLastSection(False)
        header.setSectionResizeMode(2, QHeaderView.Stretch) # 路径列拉伸
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table_episodes.setColumnWidth(3, 100) # 操作按钮列宽
        
        self.table_episodes.setAlternatingRowColors(True)
        self.table_episodes.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_episodes.setStyleSheet("QTableWidget { border: 1px solid #ccc; background-color: #fff; }")
        self.splitter.addWidget(self.table_episodes)

        self.splitter.setSizes([300, 700])
        
        # 弹性注入：把剩余垂直空间全给 splitter
        main_layout.addWidget(self.splitter, 1)

    # ==========================================
    # ✅ 新增：内存级极速检索的核心逻辑
    # ==========================================
    def _on_search_text_changed(self, text: str):
        """当搜索框文字改变时触发，直接操作内存节点显示/隐藏"""
        search_text = text.lower() # 统一转小写，实现不区分大小写匹配
        
        # 遍历左侧大纲的所有剧集
        for i in range(self.list_shows.count()):
            item = self.list_shows.item(i)
            # 判断搜索词是否在剧集名称中
            is_match = search_text in item.text().lower()
            # 匹配的显示 (setHidden(False))，不匹配的隐藏 (setHidden(True))
            item.setHidden(not is_match)

    def load_library(self, index_data: dict):
        """只负责渲染基于本地 NFO 极速构建的左侧大纲 (终极不失忆版)"""
        self.list_shows.clear()
        self.table_episodes.setRowCount(0)
        self.lbl_status.setText(f"📊 逻辑媒体库：本地极速挂载 {len(index_data)} 部剧集")

        for dir_path, show_data in index_data.items():
            title = show_data.get("title", "未知剧集")
            
            # ==========================================
            # ✅ 终极防失忆补丁：把目录路径死死焊在数据字典里！
            # 绝对不能让这个 dir_path 烂在循环的外面！
            # ==========================================
            if isinstance(show_data, dict):
                show_data['local_dir'] = dir_path
                show_data['path'] = dir_path
                show_data['folder_path'] = dir_path  # 多焊几个键名，万无一失！
                
            item = QListWidgetItem(f"📺 {title}")
            item.setData(Qt.UserRole, show_data)
            self.list_shows.addItem(item)
            
        # 加载完数据后，顺手把搜索框清空
        self.search_input.clear()

    @Slot(QListWidgetItem)
    def _on_show_clicked(self, item: QListWidgetItem):
        """点击大纲，向主控台发射请求拉取网络的信号"""
        show_data = item.data(Qt.UserRole)
        self.lbl_status.setText(f"正在加载【{show_data.get('title')}】的单集映射...")
        self.table_episodes.setRowCount(0) # 先清空表格
        self.request_network_episodes.emit(show_data)

    def render_episodes(self, network_episodes: list, local_mapping: dict, show_data: dict):
        """渲染网络与本地的缝合视图 (带探照灯的满血物理降维版)"""
        from utils.logger import logger
        logger.debug("=== 🧨 终极缝合引擎启动 ===")
        
        # 1. 尝试从各个角落挖出真实的物理路径！
        folder_path = show_data.get('local_dir') or show_data.get('path') or show_data.get('folder_path')
        
        # 如果 show_data 里没有，去主窗口的实例变量里找（极其常见）
        if not folder_path:
            if hasattr(self, 'current_selected_tvshow') and self.current_selected_tvshow:
                folder_path = self.current_selected_tvshow.get('local_dir') or self.current_selected_tvshow.get('path')

        # ==========================================
        # 🛡️ 终极路径纠偏装甲：纯文本降维打击！绝对不相信硬盘！
        # ==========================================
        if folder_path:
            # 只要传过来的路径（字符串）长得像个 nfo 文件，就强行把它砍回父目录！
            if folder_path.lower().endswith('.nfo'):
                import os
                folder_path = os.path.dirname(folder_path)
                logger.debug(f"🛡️ [路径纠偏] 抓到一个伪装成目录的 NFO 文件！已强行剥离为纯目录: {folder_path}")
        # ==========================================
        
        logger.debug(f"[路径嗅探] 最终确定的目标文件夹路径: {folder_path}")
        
        # 2. 如果挖到了路径，立刻执行强行缝合！
        if folder_path:
            import os
            from pathlib import Path
            import xml.etree.ElementTree as ET
            
            nfo_files = list(Path(folder_path).rglob('*.nfo'))
            logger.debug(f"[X光扫描] 在该目录下找到了 {len(nfo_files)} 个 NFO 文件")
            
            for nfo_obj in nfo_files:
                if nfo_obj.name.lower() == 'tvshow.nfo':
                    continue
                try:
                    with open(nfo_obj, 'rb') as f:
                        xml_content = f.read()
                    if not xml_content.strip():
                        continue
                        
                    root = ET.fromstring(xml_content)
                    ep_num_str = root.findtext('episode')
                    
                    if ep_num_str and ep_num_str.isdigit():
                        ep_float = float(ep_num_str)
                        # 只要 local_mapping 没这个集数，强行拿物理视频填进去！
                        if ep_float not in local_mapping:
                            for ext in ['.mkv', '.mp4', '.avi', '.ts', '.rmvb']:
                                vid_file = nfo_obj.with_suffix(ext)
                                if vid_file.exists():
                                    local_mapping[ep_float] = str(vid_file)
                                    logger.debug(f"✅ [缝合成功] 第 {ep_float} 集 -> {vid_file.name}")
                                    break
                except Exception as e:
                    logger.error(f"解析 {nfo_obj.name} 失败: {e}")
        else:
            logger.warning("🚨 [致命异常] 根本没拿到物理文件夹的路径，缝合引擎罢工！")
            
        logger.debug(f"[引擎收工] 缝合后的 local_mapping 最终长度: {len(local_mapping)}")
        logger.debug("=== 🧨 缝合引擎结束 ===")

        # ==========================================
        # 以下是 UI 渲染部分，保持不变
        # ==========================================
        self.table_episodes.setRowCount(len(network_episodes))
        self.lbl_status.setText(f"✅ 【{show_data.get('title')}】映射加载完毕")
        
        for row, ep_data in enumerate(network_episodes):
            ep_num = ep_data.get('sort') or ep_data.get('ep')
            try:
                ep_float = float(ep_num)
            except (ValueError, TypeError):
                ep_float = -1
                
            local_path = local_mapping.get(ep_float, "⚠️ 未匹配 (缺失)")

            item_ep = QTableWidgetItem(f"第 {ep_num} 集")
            item_ep.setTextAlignment(Qt.AlignCenter)
            self.table_episodes.setItem(row, 0, item_ep)

            title = ep_data.get('name_cn') or ep_data.get('name') or '未命名'
            self.table_episodes.setItem(row, 1, QTableWidgetItem(title))

            item_path = QTableWidgetItem(local_path)
            if "缺失" in local_path:
                item_path.setForeground(Qt.red)
            else:
                item_path.setForeground(Qt.darkGreen)
            self.table_episodes.setItem(row, 2, item_path)

            btn_link = QPushButton("🔍 选择文件")
            btn_link.setStyleSheet("QPushButton { padding: 4px; background: #f0f0f0; border: 1px solid #ccc; border-radius: 4px; } QPushButton:hover { background: #e0e0e0; }")
            btn_link.clicked.connect(lambda checked=False, e=ep_data, s=show_data: self.request_manual_link.emit(e, s))
            self.table_episodes.setCellWidget(row, 3, btn_link)
            self.table_episodes.setRowHeight(row, 35)