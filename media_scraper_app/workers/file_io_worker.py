# 文件路径: workers/file_io_worker.py
from PySide6.QtCore import QThread, Signal
from core.file_manager import FileManager
from utils.exceptions import FileOperationError
from utils.logger import logger
from core.file_manager import FileManager
# (你的其他 imports 保持不变)
from PySide6.QtCore import QThread, Signal

class FileIOWorker(QThread):
    progress_update = Signal(int, str)
    finished_signal = Signal(int, int)
    error_signal = Signal(str)

    def __init__(self, task_list: list, parent=None):
        super().__init__(parent)
        self.task_list = task_list
        # 【核心修复】：在这里补上取消标志位的初始化！
        self.is_cancelled = False 

    def cancel(self):
        """暴露给外部 (如进度条弹窗的取消按钮) 的停止接口"""
        self.is_cancelled = True

    def run(self):
        total_tasks = len(self.task_list)
        success_count = 0

        for index, task in enumerate(self.task_list):
            # 响应取消指令
            if getattr(self, 'is_cancelled', False):
                break
            
            try:
                task_type = task.get("type", "legacy")
                overwrite_flag = task.get("overwrite", False)
                
                # 安全的统一定义变量
                target_name = "未知文件"

                if task_type == "tvshow":
                    # 【注意这里】：第二个参数一定要是 task.get("dest")，绝对不能写 dest_path！
                    FileManager.generate_nfo(task.get("nfo"), task.get("dest"), overwrite=overwrite_flag)
                    
                    import os
                    # target_name = os.path.basename(task.get("dest"))
                    target_name = "tvshow.nfo"
                    
                elif task_type == "episode":
                    # 【核心修改】：提取 show_data 并传给底层写入方法
                    FileManager.write_episode_nfo(
                        video_path=task.get("video_path"), 
                        ep_data=task.get("nfo"), 
                        show_data=task.get("show_data"), 
                        overwrite=overwrite_flag
                    )
                    import os
                    target_name = os.path.basename(task.get("video_path")).rsplit('.', 1)[0] + '.nfo'
                    
                else:
                    # 兼容 1.0 的老模式
                    src_path = task.get("src")
                    dest_path = task.get("dest")
                    if dest_path:
                        import os
                        target_name = os.path.basename(dest_path)
                        
                    if src_path and dest_path:
                        FileManager.create_hardlink_or_copy(src_path, dest_path)
                    if task.get("nfo"):
                        FileManager.generate_nfo(task.get("nfo"), dest_path)

                success_count += 1
                current_progress = int(((index + 1) / total_tasks) * 100)
                
                # 【关键修复1】：完全消灭 dest_path，统一使用 target_name
                self.progress_update.emit(current_progress, f"已处理: {target_name}")

            except Exception as e:
                # 【关键修复2】：强制转为标准字符串，彻底解决 Shiboken C++ 类型转换报错！
                error_msg = str(e)
                self.error_signal.emit(f"执行异常: {error_msg}")

        # 任务结束，发送完成信号
        self.finished_signal.emit(success_count, total_tasks)