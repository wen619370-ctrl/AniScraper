import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utils.logger import logger
from utils.exceptions import NetworkRequestError

class ApiClient:
    """
    网络请求基类，封装 requests 会话，内置重试机制与超时控制。
    """
    def __init__(self, base_url: str, default_headers: dict = None, timeout: int = 10):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        
        if default_headers:
            self.session.headers.update(default_headers)
            
        # 核心防线：配置自动重试策略，增加对 POST 请求的放行
        retry_strategy = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        kwargs.setdefault('timeout', self.timeout)
        
        try:
            logger.debug(f"发送请求: {method} {url}")
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status() 
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP 状态异常: {e.response.status_code} - {url}")
            raise NetworkRequestError(url, status_code=e.response.status_code, details=str(e))
        except requests.exceptions.RequestException as e:
            logger.error(f"网络底层连接异常: {url} - {str(e)}")
            raise NetworkRequestError(url, details="网络连接失败或超时")
        except ValueError as e:
            logger.error(f"JSON 解析失败: {url}")
            raise NetworkRequestError(url, details="接口返回了非 JSON 的脏数据")

    def get(self, endpoint: str, params: dict = None, **kwargs) -> dict:
        """对外暴露的 GET 方法"""
        return self._request("GET", endpoint, params=params, **kwargs)

    def post(self, endpoint: str, json_data: dict = None, **kwargs) -> dict:
        """对外暴露的 POST 方法"""
        return self._request("POST", endpoint, json=json_data, **kwargs)