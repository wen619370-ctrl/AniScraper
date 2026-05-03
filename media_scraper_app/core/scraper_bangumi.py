import time
from core.api_client import ApiClient
from utils.logger import logger

class BangumiScraper(ApiClient):
    """
    针对 api.bgm.tv 的网络刮削器实现。
    """
    def __init__(self):
        headers = {
            "User-Agent": "LocalMediaScraperApp/1.0 (https://github.com/your-repo/scraper)"
        }
        super().__init__(base_url="https://api.bgm.tv/v0", default_headers=headers)
        
        self.last_request_time = 0.0
        self.request_delay = 1.2 
        
    def _rate_limit(self):
        """节流阀：防止触发 429"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            sleep_time = self.request_delay - elapsed
            logger.debug(f"触发 Bangumi 节流阀，等待 {sleep_time:.2f} 秒...")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def search_subject(self, keyword: str) -> list[dict]:
        """根据关键词搜索动画（使用 v0 的 POST 规范）"""
        self._rate_limit()
        logger.info(f"正在 Bangumi 检索番剧: {keyword}")
        
        endpoint = "/search/subjects?limit=10"
        payload = {
            "keyword": keyword,
            "filter": {
                "type": [2] 
            }
        }
        try:
            response = self.post(endpoint, json_data=payload)
            return response.get("data", [])
        except Exception as e:
            logger.warning(f"Bangumi 检索失败 [{keyword}]: {e}")
            return []

    def get_subject_details(self, subject_id: int) -> dict:
        """获取单个条目的详细元数据"""
        self._rate_limit()
        logger.info(f"拉取 Bangumi 条目详情 ID: {subject_id}")
        return self.get(f"/subjects/{subject_id}")

    def get_episodes(self, subject_id: int) -> list[dict]:
        """获取特定条目的所有单集列表"""
        self._rate_limit()
        logger.info(f"拉取 Bangumi 单集列表 ID: {subject_id}")
        
        try:
            response = self.get(f"/episodes?subject_id={subject_id}")
            return response.get("data", [])
        except Exception as e:
            logger.warning(f"拉取单集列表失败 [ID:{subject_id}]: {e}")
            return []