import requests
from PySide6.QtCore import QThread, Signal
from core.scraper_bangumi import BangumiScraper
from utils.exceptions import NetworkRequestError, ScraperBaseError
from utils.logger import logger
from PIL import Image
import io

class ScrapeWorker(QThread):
    progress_signal = Signal(str)
    # 【修改 1】：增加 bytes 类型，用于安全传递图片二进制数据
    result_signal = Signal(object, bytes) 
    error_signal = Signal(str)

    def __init__(self, keyword: str = None, subject_id: int = None, parent=None):
        super().__init__(parent)
        self.keyword = keyword
        self.subject_id = subject_id
        
        # ✅ 新增：安全状态标志位
        self._is_cancelled = False 
        
        self.finished.connect(self.deleteLater)

    def cancel(self):
        """
        ✅ 新增：安全中断接口
        主窗体在重新发起搜索或关闭软件时，会调用此方法。
        触发后，底层的网络流和逻辑处理会就近安全退出。
        """
        self._is_cancelled = True

    def run(self):
        scraper = BangumiScraper()
        
        try:
            if self.keyword:
                if self._is_cancelled: return  # 🛑 安全检查点
                
                self.progress_signal.emit(f"正在搜索番剧: {self.keyword} ...")
                results = scraper.search_subject(self.keyword)
                
                if self._is_cancelled: return  # 🛑 安全检查点
                
                if not results:
                    self.error_signal.emit(f"未找到与 '{self.keyword}' 相关的结果。")
                    return
                    
                self.progress_signal.emit("搜索完成！")
                # 搜索模式下，不下载海报，bytes 传空
                self.result_signal.emit(results, b"")
                
            elif self.subject_id:
                if self._is_cancelled: return  # 🛑 安全检查点
                
                self.progress_signal.emit(f"正在拉取条目详情 (ID: {self.subject_id}) ...")
                details = scraper.get_subject_details(self.subject_id)
                
                if self._is_cancelled: return  # 🛑 安全检查点
                
                episodes = scraper.get_episodes(self.subject_id)
                
                if self._is_cancelled: return  # 🛑 安全检查点
                
                # 【修改 2】：提取海报 URL 并同步下载
                poster_bytes = b""
                images = details.get("images") or details.get("image") or {}
                # Bangumi 通常把大图放在 large 字段
                poster_url = images.get("large") or images.get("common", "")
                
                if poster_url:
                    self.progress_signal.emit("正在下载高清海报...")
                    try:
                        headers = {"User-Agent": "Mozilla/5.0"}
                        resp = requests.get(poster_url, headers=headers, timeout=10)
                        resp.raise_for_status()
                        
                        if self._is_cancelled: return  # 🛑 核心防弹：图片下载完发现被强杀了，立刻抛弃
                        
                        # 【新增：清洗图片 iCCP 配置】
                        img = Image.open(io.BytesIO(resp.content))
                        # 剥离可能引起报错的 ICC profile
                        img.info.pop('icc_profile', None) 
                        
                        # 重新转存为干净的 bytes
                        clean_bytes_io = io.BytesIO()
                        img.save(clean_bytes_io, format="PNG")
                        poster_bytes = clean_bytes_io.getvalue()
                        
                    except Exception as e:
                        logger.warning(f"海报下载或清洗失败: {e}")

                if self._is_cancelled: return  # 🛑 最终发射前的检查点
                
                combined_data = {
                    "details": details,
                    "episodes": episodes
                }
                self.progress_signal.emit("数据拉取完毕！")
                # 将元数据和图片 bytes 一同发射出去
                self.result_signal.emit(combined_data, poster_bytes)
                
            else:
                self.error_signal.emit("未提供有效的搜索词或条目 ID。")

        except Exception as e:
            # 只有在没有被主动 Cancel 的情况下才报错，避免主线程强退时污染日志
            if not getattr(self, '_is_cancelled', False):
                logger.exception("刮削线程发生未知崩溃")
                self.error_signal.emit(f"发生未知错误: {str(e)}")