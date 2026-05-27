# 文件路径: workers/file_io_worker.py
import os

from PySide6.QtCore import QThread, Signal

from core.file_manager import FileManager
from utils.exceptions import FileOperationError
from utils.logger import logger


class FileIOWorker(QThread):
    progress_update = Signal(int, str)
    finished_signal = Signal(int, int)
    error_signal = Signal(str)

    def __init__(self, task_list: list, parent=None):
        super().__init__(parent)
        self.task_list = task_list
        self.is_cancelled = False

    def cancel(self):
        """暴露给外部 (如进度条弹窗的取消按钮) 的停止接口"""
        self.is_cancelled = True

    def run(self):
        total_tasks = len(self.task_list)
        success_count = 0

        for index, task in enumerate(self.task_list):
            if getattr(self, 'is_cancelled', False):
                break

            try:
                task_type = task.get("type", "legacy")
                overwrite_flag = task.get("overwrite", False)

                target_name = "未知文件"

                if task_type == "tvshow":
                    FileManager.generate_nfo(task.get("nfo"), task.get("dest"), overwrite=overwrite_flag)
                    target_name = "tvshow.nfo"

                elif task_type == "episode":
                    FileManager.write_episode_nfo(
                        video_path=task.get("video_path"),
                        ep_data=task.get("nfo"),
                        show_data=task.get("show_data"),
                        overwrite=overwrite_flag
                    )
                    target_name = os.path.basename(task.get("video_path")).rsplit('.', 1)[0] + '.nfo'

                else:
                    # 兼容 1.0 的老模式
                    src_path = task.get("src")
                    dest_path = task.get("dest")
                    if dest_path:
                        target_name = os.path.basename(dest_path)

                    if src_path and dest_path:
                        FileManager.create_hardlink_or_copy(src_path, dest_path)
                    if task.get("nfo"):
                        FileManager.generate_nfo(task.get("nfo"), dest_path)

                success_count += 1
                current_progress = int(((index + 1) / total_tasks) * 100)
                self.progress_update.emit(current_progress, f"已处理: {target_name}")

            except Exception as e:
                error_msg = str(e)
                self.error_signal.emit(f"执行异常: {error_msg}")

        self.finished_signal.emit(success_count, total_tasks)
