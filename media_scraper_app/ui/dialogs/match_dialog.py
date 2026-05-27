# 文件路径: ui/dialogs/match_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTableWidget, QTableWidgetItem, QComboBox, QHeaderView, QLabel
)
from PySide6.QtCore import Qt, QEvent
from pathlib import Path

from PySide6.QtWidgets import QAbstractItemView # 【新增】用于配置表格多选模式

from utils.config_loader import ConfigLoader
from PySide6.QtWidgets import QCheckBox

class MatchDialog(QDialog):
    def __init__(self, local_files: list[dict], remote_episodes: list[dict], match_result: dict, parent=None):
        super().__init__(parent)
        
        # ✅ 【核心修复 1】：在整个类刚出生的时候，第一件事就是把“锁”闭合！
        self._is_syncing = True 
        self._is_combo_syncing = True # 【新增】下拉框专属同步锁

        # 【修改点】：local_files 现在接收包含体积字典的列表
        self.local_files = local_files 
        self.remote_episodes = remote_episodes
        self.match_result = match_result
        
        self.setWindowTitle("请核对单集匹配结果")
        self.setMinimumSize(850, 500)
        self.setWindowModality(Qt.ApplicationModal)

        self._setup_ui()
        self._populate_data()
        # ✅ 核心启动：激活全自动打勾联动引擎！
        # ==========================================
        self._auto_check_valid_rows()

        # ✅ 【核心修复 2】：表格全部画完，数据塞好之后，安全解锁！
        self._is_syncing = False 
        self._is_combo_syncing = False # 【新增】解锁下拉框


    def _on_item_changed(self, item):
        """当复选框状态改变时，批量同步给所有选中的行"""
        # ✅ 【核心修复 3】：使用 getattr 穿上终极防弹衣。
        # 如果 self._is_syncing 还没出生，它会默认返回 True(锁定拦截状态)，绝不报错！
        if getattr(self, '_is_syncing', True) or item.column() != 0:
            return

        # 2. 获取当前高亮选中的行号（不包括当前正在操作的这一行）
        selected_ranges = self.table.selectedRanges()
        selected_rows = []
        for r in selected_ranges:
            for row_idx in range(r.topRow(), r.bottomRow() + 1):
                selected_rows.append(row_idx)

        # 3. 如果当前行在多选范围内，则开始“施法”
        current_row = item.row()
        if current_row in selected_rows and len(selected_rows) > 1:
            self._is_syncing = True # 开启同步锁
            new_state = item.checkState()
            
            for r in selected_rows:
                if r != current_row: # 避开自己，防止死循环
                    check_item = self.table.item(r, 0)
                    if check_item:
                        check_item.setCheckState(new_state)
            
            self._is_syncing = False # 解锁

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        lbl_info = QLabel("系统已完成智能匹配。低于设定阈值的小体积文件已被自动过滤。\n请核对以下文件与网络单集的对应关系：")
        lbl_info.setStyleSheet("color: #555; font-weight: bold; padding: 5px;")
        layout.addWidget(lbl_info)

        self.table = QTableWidget()

        # ✅ 获取配置的最小体积阈值 (转换为 Bytes)
        config = ConfigLoader().config
        self.min_size_mb = config.get("min_video_size_mb", 150)
        self.min_size_bytes = self.min_size_mb * 1024 * 1024

        # ✅ 增加显隐开关 (默认不勾选)
        self.chk_show_small = QCheckBox(f"👁️ 显示小于 {self.min_size_mb}MB 的零碎文件 (默认忽略 NFO 生成)")
        self.chk_show_small.setChecked(False)
        self.chk_show_small.toggled.connect(self._toggle_small_files)
        
        # 将复选框加到你的布局中，比如 top_layout.addWidget(self.chk_show_small)
        layout.addWidget(self.chk_show_small)

        # ==========================================
        # ✅ [V5.2 稳健版 UX]：干干净净的表格设置，没有任何鼠标劫持！
        # ==========================================
        # 1. 设置为整行选中模式
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # 2. 开启扩展选择模式 (支持 Shift 连续多选、Ctrl 间隔多选)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # 3. 监听项改变事件（处理复选框状态同步）
        self.table.itemChanged.connect(self._on_item_changed)

        # 【修改点】：设置列名（注意 populate_data 里是 5 列，这里只是初始化表头，会被覆盖，但保持整洁）
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["选择", "本地视频文件", "文件体积", "识别状态", "对应网络单集"])
        
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 50)   # 选择
        self.table.setColumnWidth(1, 250)  # 本地视频文件
        self.table.setColumnWidth(2, 80)   # 文件体积
        self.table.setColumnWidth(3, 100)  # 识别状态
        # 第4列(对应网络单集) 由 StretchLastSection 自动拉伸
        self.table.horizontalHeader().setMinimumSectionSize(60)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget { border: 1px solid #ccc; background-color: #fff; }
            QHeaderView::section { background-color: #f0f0f0; padding: 6px; border: 1px solid #ddd; font-weight: bold; }
        """)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()

        # ✅ 【新增】：明确的批量忽略按钮（放置在布局最左侧）
        self.btn_batch_ignore = QPushButton("🚫 批量忽略选中行")
        self.btn_batch_ignore.setMinimumHeight(35)
        self.btn_batch_ignore.setStyleSheet("color: #d9534f; font-weight: bold; padding: 0 15px;")
        self.btn_batch_ignore.clicked.connect(self._on_batch_ignore_clicked)
        btn_layout.addWidget(self.btn_batch_ignore)

        # ✅ 【新增】：仅保留选中行按钮
        self.btn_keep_only = QPushButton("🎯 仅保留选中 (忽略其余)")
        self.btn_keep_only.setMinimumHeight(35)
        self.btn_keep_only.setStyleSheet("color: #e67e22; font-weight: bold; padding: 0 15px;")
        self.btn_keep_only.clicked.connect(self._on_keep_selected_only_clicked)
        btn_layout.addWidget(self.btn_keep_only)

        # 使用伸缩条将左侧的批量按钮与右侧的确认/取消按钮强行隔开
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("取消刮削")
        self.btn_cancel.setMinimumHeight(35)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_confirm = QPushButton("✅ 确认无误，开始批量写盘")
        self.btn_confirm.setMinimumHeight(35)
        self.btn_confirm.setStyleSheet("background-color: #2fb565; color: white; font-weight: bold; padding: 0 20px;")
        self.btn_confirm.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_confirm)
        layout.addLayout(btn_layout)

    def _format_size(self, size_bytes: int) -> str:
        """内置的极简体积格式化探针"""
        if size_bytes >= 1024 ** 3:
            return f"{size_bytes / (1024 ** 3):.2f} GB"
        else:
            return f"{size_bytes / (1024 ** 2):.2f} MB"

    def _populate_data(self):
        """将底层匹配数据渲染到表格中 (终极智能联动版)"""
        self.table.setRowCount(len(self.local_files))
        # 【核心修改】：现在是 5 列了！
        self.table.setColumnCount(5) 
        self.table.setHorizontalHeaderLabels(["选择", "本地视频文件", "文件体积", "识别状态", "对应网络单集"])
        
        # 预处理下拉框数据
        combo_items = ["❌ 忽略此文件 (不生成NFO)"]
        # 增加容错：本地提取的可能是 ep_number 而不是 sort
        sorted_episodes = sorted(self.remote_episodes, key=lambda x: float(x.get('sort', x.get('ep_number', 9999))))
        for ep in sorted_episodes:
            ep_num = ep.get('sort') or ep.get('ep_number') or '?'
            ep_title = ep.get('name_cn') or ep.get('name') or ep.get('title') or '未命名'
            combo_items.append(f"第 {ep_num} 集 - {ep_title}")

        # (✅ 这里干干净净，直接进入循环)

        for row, file_info in enumerate(self.local_files):
            file_path = file_info['path']
            size_bytes = file_info['size_bytes']
            from pathlib import Path  # 确保 Path 被导入
            filename = Path(file_path).name
            
            # 原来的底层正则引擎匹配结果
            matched_ep = self.match_result.get(file_path)

            # ==========================================
            # ✅ 终极补救：如果引擎瞎了，我们就用“同名绝对绑定”！
            # ==========================================
            if not matched_ep:
                video_base_name = Path(file_path).stem  # 提取视频的无后缀文件名
                for ep in sorted_episodes:
                    # 只要视频文件名和 NFO 文件名完全一样，直接原地成婚！
                    if ep.get('local_filename') == video_base_name:
                        matched_ep = ep
                        break
            
            # ... 下面是你原有的创建复选框等代码，保持不变 ...

            # ==========================================
            # 列 0：选择复选框 (先创建壳子，状态由后面的下拉框决定！)
            # ==========================================
            item_check = QTableWidgetItem()
            item_check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item_check.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, item_check)

            # ==========================================
            # 列 1：本地视频文件
            # ==========================================
            rel_path = file_info.get('relative_path', Path(file_path).name)
            item_file = QTableWidgetItem(rel_path)
            item_file.setFlags(Qt.ItemIsEnabled)
            item_file.setData(Qt.UserRole, file_path) 
            item_file.setToolTip(rel_path) 
            self.table.setItem(row, 1, item_file)

            # ==========================================
            # 列 2：文件体积
            # ==========================================
            item_size = QTableWidgetItem(self._format_size(size_bytes))
            item_size.setFlags(Qt.ItemIsEnabled)
            item_size.setTextAlignment(Qt.AlignCenter)
            if size_bytes < 300 * 1024 * 1024: 
                item_size.setForeground(Qt.darkYellow)
            self.table.setItem(row, 2, item_size)

            # ==========================================
            # 列 3：识别状态
            # ==========================================
            status_text = "🟢 匹配成功" if matched_ep and matched_ep.get("type") != "special" else "🟡 需手动确认"
            item_status = QTableWidgetItem(status_text)
            item_status.setFlags(Qt.ItemIsEnabled)
            item_status.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, item_status)

            # ==========================================
            # 列 4：下拉选框
            # ==========================================
            combo = QComboBox()
            combo.addItems(combo_items)
            combo.setItemData(0, None)
            for i, ep in enumerate(sorted_episodes):
                combo.setItemData(i + 1, ep)

            # 智能预选中逻辑
            if matched_ep:
                if matched_ep.get("type") == "special":
                    combo.setCurrentIndex(0)
                else:
                    for i, ep in enumerate(sorted_episodes):
                        # ==========================================
                        # ✅ 终极防瞎眼逻辑：严禁 None == None 这种智障匹配发生！
                        # 兼容 ID、ep_number 和 sort 三种维度，只要命中一个真实的且相等的值即可
                        # ==========================================
                        match_id = (ep.get('id') is not None) and (ep.get('id') == matched_ep.get('id'))
                        match_ep = (ep.get('ep_number') is not None) and (str(ep.get('ep_number')) == str(matched_ep.get('ep_number')))
                        match_sort = (ep.get('sort') is not None) and (str(ep.get('sort')) == str(matched_ep.get('sort')))
                        
                        if match_id or match_ep or match_sort:
                            combo.setCurrentIndex(i + 1)
                            break
            else:
                combo.setCurrentIndex(0)

            self.table.setCellWidget(row, 4, combo)
            self.table.setRowHeight(row, 45) 
            
            # ==========================================
            # ✅ 终极核弹修复：复选框与下拉框的“血肉绑定”
            # ==========================================
            # 1. 界面弹出的瞬间：看下拉框脸色！选了集数就打勾，没选就取消！
            if combo.currentIndex() > 0:
                item_check.setCheckState(Qt.Checked)
            else:
                item_check.setCheckState(Qt.Unchecked)

            # 2. 运行时防呆联动：用户手动拨动下拉框，复选框全自动伴随变化！
            combo.currentIndexChanged.connect(
                lambda idx, chk=item_check: chk.setCheckState(Qt.Checked if idx > 0 else Qt.Unchecked)
            )

            # 保留你原来的闭包监听逻辑
            combo.currentIndexChanged.connect(lambda idx, r=row: self._on_combo_changed(r, idx))

        self._toggle_small_files(False)

    def keyPressEvent(self, event):
        """
        【极客快捷键】
        支持按下空格键 (Space) 批量翻转所有高亮行的勾选状态。
        """
        if event.key() == Qt.Key_Space:
            selected_items = self.table.selectedItems()
            if selected_items:
                selected_rows = set(item.row() for item in selected_items)
                
                # 以选中范围内第一行的状态为基准进行反转
                first_row = list(selected_rows)[0]
                first_item = self.table.item(first_row, 0)
                
                if first_item:
                    current_state = first_item.checkState()
                    # 确定要切换到的新状态
                    target_state = Qt.Unchecked if current_state == Qt.Checked else Qt.Checked
                    
                    # 批量施法
                    for r in selected_rows:
                        item = self.table.item(r, 0)
                        if item:
                            item.setCheckState(target_state)
                            
                event.accept() # 拦截事件，防止空格键触发别的按钮
                return
                
        # 其他按键放行给父类处理
        super().keyPressEvent(event)
    

    def get_final_mapping(self) -> dict:
        """
        全自动雷达扫描版 + 万能数据翻译插头 + 幽灵文件拦截器
        保证送给底层的每一份数据都是所见即所得的！
        """
        from utils.logger import logger
        final_results = {}
        logger.info("=== 🔍 开始扫描弹窗 UI 提取手动选择结果 ===")

        for row in range(self.table.rowCount()):
            # ==========================================
            # ✅ 终极防鬼装甲：只要是 UI 隐藏的行，一律当它不存在！
            # 绝对不把用户看不见的小体积字幕/垃圾文件悄悄写进硬盘！
            # ==========================================
            if self.table.isRowHidden(row):
                continue

            try:
                file_path = self.local_files[row].get('path')
            except IndexError:
                continue

            if not file_path:
                continue

            # 1. 获取最准确的打勾状态
            is_checked = True
            widget = self.table.cellWidget(row, 0)
            if widget and hasattr(widget, 'isChecked'):
                is_checked = widget.isChecked()
            else:
                chk_item = self.table.item(row, 0)
                if chk_item is not None:
                    state_value = chk_item.checkState().value if hasattr(chk_item.checkState(), 'value') else int(chk_item.checkState())
                    is_checked = (state_value != 0)
            
            if not is_checked:
                continue

            # 2. 全自动雷达：找下拉框
            combo = None
            for col in range(self.table.columnCount()):
                w = self.table.cellWidget(row, col)
                if w and w.__class__.__name__ == 'QComboBox':
                    combo = w
                    break

            # 3. 提取最高指令，并进行【数据洗澡】
            if combo:
                if combo.currentIndex() == 0:
                    continue # 忽略项安全跳过
                    
                current_data = combo.currentData()
                if current_data:
                    standard_data = dict(current_data) 
                    
                    ep_num = current_data.get('ep_number') or current_data.get('sort') or current_data.get('episode') or ''
                    standard_data['ep_number'] = ep_num
                    
                    ep_name = current_data.get('ep_name') or current_data.get('name_cn') or current_data.get('name') or current_data.get('title') or '未命名'
                    standard_data['ep_name'] = ep_name
                    
                    standard_data['overview'] = current_data.get('overview') or current_data.get('plot') or current_data.get('desc') or ''
                    standard_data['season'] = current_data.get('season') or current_data.get('season_number') or 1

                    final_results[file_path] = standard_data
                    logger.info(f"[+] 行 {row}: 提取成功 -> 准备写入第 {ep_num} 集: {ep_name}")
                else:
                    logger.error(f"[!] 🚨 行 {row}: 异常！下拉框有内容但字典丢失！")

        logger.info(f"=== 🔍 扫描结束，共提取到 {len(final_results)} 个真实写盘任务 ===")
        return final_results

    def _auto_check_valid_rows(self):
        """UI 智能化修复：自动根据下拉框是否有数据，联动复选框的打勾状态"""
        for row in range(self.table.rowCount()):
            # ⚠️ 注意：你的下拉框在第 5 列，所以索引是 4
            combo = self.table.cellWidget(row, 4)
            chk = self.table.item(row, 0)
            
            if combo and chk:
                # 1. 窗口刚打开时，进行一次初始化判断并自动打勾
                if combo.currentData():
                    chk.setCheckState(Qt.Checked)
                else:
                    chk.setCheckState(Qt.Unchecked)
                    
                # 2. 绑定神级联动：以后只要你手动修改了下拉框，复选框就会全自动跟随变化！
                combo.currentIndexChanged.connect(
                    lambda idx, c=combo, ch=chk: ch.setCheckState(Qt.Checked if c.currentData() else Qt.Unchecked)
                )
    

    def _on_combo_changed(self, current_row, new_index):
        """当下拉框选项改变时，批量同步给所有高亮选中的行"""
        # 1. 安全拦截：如果是初始化阶段，或者正处于代码循环同步中，直接放行
        if getattr(self, '_is_combo_syncing', True):
            return

        # 2. 获取当前高亮选中的行号
        selected_ranges = self.table.selectedRanges()
        selected_rows = []
        for r in selected_ranges:
            for row_idx in range(r.topRow(), r.bottomRow() + 1):
                selected_rows.append(row_idx)

        # 3. 触发同调：如果当前行属于多选范围，则强行覆盖其他选中行的下拉框
        if current_row in selected_rows and len(selected_rows) > 1:
            self._is_combo_syncing = True # 开启下拉框同步锁
            
            for r in selected_rows:
                if r != current_row: # 避开自己
                    combo = self.table.cellWidget(r, 4)
                    if combo:
                        combo.setCurrentIndex(new_index)
            
            self._is_combo_syncing = False # 解锁


    def _on_batch_ignore_clicked(self):
        """明确的批量忽略执行逻辑"""
        from PySide6.QtWidgets import QMessageBox

        # 🛑 【核心修复】：不要用 selectedItems()，改用 selectedRanges() 获取视觉上的高亮区域！
        selected_ranges = self.table.selectedRanges()
        
        if not selected_ranges:
            QMessageBox.information(self, "提示", "请先在表格中按住 Shift 框选需要忽略的多行。")
            return

        # 提取所有高亮区域中包含的，不重复的行号
        selected_rows = set()
        for r in selected_ranges:
            for row_idx in range(r.topRow(), r.bottomRow() + 1):
                selected_rows.add(row_idx)

        # 闭合信号锁，防止修改复选框时触发不必要的连环更新
        self._is_syncing = True
        self._is_combo_syncing = True

        for r in selected_rows:
            # 1. 强行取消复选框的勾选 (第 0 列)
            chk = self.table.item(r, 0)
            if chk:
                chk.setCheckState(Qt.Unchecked)
            
            # 2. 强行将下拉框切为“忽略此文件” (第 4 列，索引为 0)
            combo = self.table.cellWidget(r, 4)
            if combo:
                combo.setCurrentIndex(0)

        # 解除信号锁
        self._is_syncing = False
        self._is_combo_syncing = False

        # 操作完成后，顺手把表格的选择焦点清空，给人一种“操作已完成”的视觉反馈
        self.table.clearSelection()
        
        # 状态栏或者轻量级提示（可选）
        QMessageBox.information(self, "操作成功", f"已将 {len(selected_rows)} 个文件批量设置为忽略！")


    def _on_keep_selected_only_clicked(self):
        """反向操作逻辑：忽略除了选中行之外的所有行"""
        from PySide6.QtWidgets import QMessageBox

        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            QMessageBox.information(self, "提示", "请先在表格中框选您【想要保留】的行。")
            return

        # 提取所有高亮区域中包含的行号
        selected_rows = set()
        for r in selected_ranges:
            for row_idx in range(r.topRow(), r.bottomRow() + 1):
                selected_rows.add(row_idx)

        # 闭合信号锁
        self._is_syncing = True
        self._is_combo_syncing = True

        ignored_count = 0
        # 遍历表格中的【每一行】
        for row in range(self.table.rowCount()):
            # 如果这行不在用户的选择范围内，就干掉它
            if row not in selected_rows:
                # 1. 强行取消复选框
                chk = self.table.item(row, 0)
                if chk:
                    chk.setCheckState(Qt.Unchecked)
                
                # 2. 强行将下拉框切为“忽略”
                combo = self.table.cellWidget(row, 4)
                if combo:
                    combo.setCurrentIndex(0)
                
                ignored_count += 1

        # 解除信号锁
        self._is_syncing = False
        self._is_combo_syncing = False

        self.table.clearSelection()
        QMessageBox.information(self, "操作成功", f"已为您保留选中的 {len(selected_rows)} 行，并将其余 {ignored_count} 个文件全部忽略！")


    def _toggle_small_files(self, checked: bool):
        """控制小体积视频文件的显示与隐藏"""
        # ✅ 修复 1：你的表格变量名叫 self.table
        # ✅ 修复 2：直接从 self.local_files 列表获取体积，绝对安全准确
        for row in range(self.table.rowCount()):
            # 行号 row 刚好完美对应 self.local_files 列表的索引
            if row < len(self.local_files):
                size = self.local_files[row].get('size_bytes', 0)
                
                # 如果文件小于阈值，且当前开关未勾选，则隐藏该行
                if size < self.min_size_bytes:
                    self.table.setRowHidden(row, not checked)