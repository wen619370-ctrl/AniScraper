# 临时测试脚本: test_network.py

from core.scraper_bangumi import BangumiScraper
from utils.logger import logger
from utils.exceptions import NetworkRequestError

def run_test():
    scraper = BangumiScraper()
    test_anime_name = "葬送的芙莉莲"

    try:
        # 1. 测试搜索功能与限流
        logger.info(f"=== 测试阶段 1: 搜索 '{test_anime_name}' ===")
        search_results = scraper.search_subject(test_anime_name)
        
        if not search_results:
            logger.error("搜索结果为空，请检查网络或 API 连通性。")
            return

        # 获取搜索结果的第一个条目
        first_result = search_results[0]
        subject_id = first_result.get("id")
        title = first_result.get("name_cn") or first_result.get("name")
        logger.info(f"命中首个结果: {title} (ID: {subject_id})")

        # 2. 测试获取详情 (注意观察控制台是否输出了“触发节流阀”的日志)
        logger.info(f"=== 测试阶段 2: 获取条目 {subject_id} 的详情 ===")
        details = scraper.get_subject_details(subject_id)
        logger.info(f"成功获取详情！总集数: {details.get('total_episodes')}, 简介片段: {details.get('summary', '')[:20]}...")

        # 3. 测试获取单集列表
        logger.info(f"=== 测试阶段 3: 获取单集列表 ===")
        episodes = scraper.get_episodes(subject_id)
        if episodes:
            logger.info(f"成功获取到 {len(episodes)} 个单集信息。第 1 集原名: {episodes[0].get('name')}")

    except NetworkRequestError as e:
        logger.error(f"网络阻断: {e}")

if __name__ == "__main__":
    run_test()