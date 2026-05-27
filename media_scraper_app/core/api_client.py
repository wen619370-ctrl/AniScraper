import requests
from typing import Dict, Any, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utils.logger import logger
from utils.exceptions import NetworkRequestError

class ApiClient:
    """
    网络请求基类，封装 requests 会话，内置重试机制与超时控制。
    提供统一的 HTTP 请求接口和错误处理。
    """
    def __init__(
        self,
        base_url: str,
        default_headers: Optional[Dict[str, str]] = None,
        timeout: int = 10
    ):
        """
        初始化 API 客户端
        
        Args:
            base_url: API 基础 URL
            default_headers: 默认请求头
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        
        if default_headers:
            self.session.headers.update(default_headers)
            
        # 配置自动重试策略
        retry_strategy = Retry(
            total=3,  # 总重试次数
            backoff_factor=1.0,  # 退避因子
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的 HTTP 状态码
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]  # 允许重试的 HTTP 方法
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        发送 HTTP 请求的内部方法
        
        Args:
            method: HTTP 方法（GET, POST 等）
            endpoint: API 端点（相对于 base_url）
            **kwargs: 其他传递给 requests.request 的参数
            
        Returns:
            解析后的 JSON 响应数据
            
        Raises:
            NetworkRequestError: 当请求失败或响应解析失败时
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        kwargs.setdefault('timeout', self.timeout)
        
        try:
            logger.debug(f"发送请求: {method} {url}")
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()  # 对 4xx/5xx 状态码抛出异常
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

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        发送 GET 请求
        
        Args:
            endpoint: API 端点
            params: URL 查询参数
            **kwargs: 其他参数
            
        Returns:
            解析后的 JSON 响应
        """
        return self._request("GET", endpoint, params=params, **kwargs)

    def post(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        发送 POST 请求
        
        Args:
            endpoint: API 端点
            json_data: 请求体 JSON 数据
            **kwargs: 其他参数
            
        Returns:
            解析后的 JSON 响应
        """
        return self._request("POST", endpoint, json=json_data, **kwargs)