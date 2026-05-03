import re
import os
from pathlib import Path
from utils.logger import logger

class EpisodeMatcher:
    """强化版单集匹配引擎"""

    # 【核心修复】：必须使用 @staticmethod！这样 Python 就不会乱塞隐形参数了。
    @staticmethod
    def smart_match(video_data_list, remote_episodes):
        """
        V5.1 终极正则匹配引擎
        接收带层级的 relative_path，精准剥离集数，抵御多季目录干扰。
        """
        match_result = {}
        
        # 1. 建立网络单集速查表 { 1.0: {...}, 2.0: {...} }
        ep_map = {}
        for ep in remote_episodes:
            try:
                # 把集数转为浮点数，兼容 1.5 这种 SP 或 .5 集
                ep_num = float(ep.get('sort') or ep.get('ep', -1))
                ep_map[ep_num] = ep
            except (ValueError, TypeError):
                continue

        # 2. 开始遍历本地视频字典
        for file_info in video_data_list:
            
            # 【V5.1 核心】：安全拆解降维打击的数据包
            if isinstance(file_info, dict):
                # 优先吃进相对路径 (如 Season 2/01.mkv)，拿不到再吃文件名
                name_to_match = file_info.get('relative_path', file_info.get('filename', ''))
                abs_path = file_info.get('path')
            else:
                # 兜底兼容极其古老的版本
                name_to_match = os.path.basename(file_info)
                abs_path = file_info

            if not abs_path:
                continue

            # 清洗字符串，防止 Windows 反斜杠引发正则灾难
            clean_name = name_to_match.lower().replace('\\', '/')

            # ==========================================
            # 🧠 正则提取大逃杀开始
            # ==========================================
            matched_ep = None
            extracted_num = None

            # [前置过滤]：如果是明显的非正片 (特典、菜单、PV)，直接判定为提取失败 (UI 亮黄灯)
            if re.search(r'(ncop|nced|menu|pv|teaser|trailer)', clean_name):
                match_result[abs_path] = None
                continue

            # 为了防止被父文件夹 "Season 2" 里的 "2" 干扰，
            # 我们优先匹配带明确集数标识的格式 (匹配绝大多数 PT 组和字幕组命名规范)
            patterns = [
                r's\d+e0*(\d+(?:\.\d+)?)',          # 匹配 S01E02 -> 提取 2
                r'\[0*(\d+(?:\.\d+)?)\]',           # 匹配 [02] 或 [02.5] -> 提取 2
                r'-\s0*(\d+(?:\.\d+)?)\s',          # 匹配 - 02 (VCB 等常见) -> 提取 2
                r'第0*(\d+(?:\.\d+)?)[话集]',         # 匹配 第02话 -> 提取 2
                r'ep?0*(\d+(?:\.\d+)?)',            # 匹配 EP02 或 E02 -> 提取 2
                r'(?:^|/)\D*0*(\d+(?:\.\d+)?)\D*$'  # 兜底：提取路径最后一部分里的唯一数字
            ]

            for pattern in patterns:
                match = re.search(pattern, clean_name, re.IGNORECASE)
                if match:
                    extracted_num = float(match.group(1))
                    break
            
            # ==========================================
            # 🤝 认亲环节
            # ==========================================
            # 如果从路径里抠出了集数数字，且网络端刚好有这一集
            if extracted_num is not None and extracted_num in ep_map:
                matched_ep = ep_map[extracted_num]

            # 无论成功与否，必须拿物理绝对路径 abs_path 作为字典的 Key 返回
            match_result[abs_path] = matched_ep

        return match_result