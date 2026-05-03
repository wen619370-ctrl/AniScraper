# 文件路径: utils/exceptions.py

class ScraperBaseError(Exception):
    """
    项目中所有自定义异常的基类。
    """
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class ParserError(ScraperBaseError):
    """
    解析异常：当 PTN 解析失败，或无法从文件名中提取出足以进行刮削的关键信息（如标题、季集号）时抛出。
    """
    def __init__(self, filename: str, details: str = "无法提取有效元数据"):
        message = f"文件名解析失败 [{filename}]: {details}"
        super().__init__(message)
        self.filename = filename

class NetworkRequestError(ScraperBaseError):
    """
    网络请求异常：用于处理 API 超时、代理失效、触发频率限制(429)或服务器无响应等情况。
    """
    def __init__(self, url: str, status_code: int = None, details: str = "网络连接异常"):
        code_info = f" (HTTP {status_code})" if status_code else ""
        message = f"网络请求失败{code_info} [{url}]: {details}"
        super().__init__(message)
        self.url = url
        self.status_code = status_code

class FileOperationError(ScraperBaseError):
    """
    文件操作异常：用于重命名、移动文件或读写 NFO、下载海报时，遇到的权限不足、路径不存在或磁盘空间满等系统级错误。
    """
    def __init__(self, filepath: str, operation: str, details: str = "系统拒绝访问"):
        message = f"文件操作失败 [{operation}] -> [{filepath}]: {details}"
        super().__init__(message)
        self.filepath = filepath
        self.operation = operation