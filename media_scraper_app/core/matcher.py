import re
import os
from pathlib import Path
from typing import List, Dict, Any, Union, Optional
from utils.logger import logger

class EpisodeMatcher:
    """
    强化版单集匹配引擎。
    使用多种正则模式从视频文件名中提取集数，并与网络端单集数据智能匹配。
    """

    @staticmethod
    def smart_match(
        video_data_list: List[Union[Dict[str, Any], str]],
        remote_episodes: List[Dict[str, Any]]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        V5.1 终极正则匹配引擎
        接收带层级的 relative_path，精准剥离集数，抵御多季目录干扰。
        
        Args:
            video_data_list: 本地视频文件列表，每个元素可以是包含文件信息的字典或简单的文件路径
            remote_episodes: 网络端获取的单集信息列表
            
        Returns:
            匹配结果字典，键为视频文件的绝对路径，值为匹配到的单集信息（没有匹配则为 None）
        """
        match_result: Dict[str, Optional[Dict[str, Any]]] = {}
        
        # 1. 建立网络单集速查表 { 1.0: {...}, 2.0: {...} }
        ep_map: Dict[float, Dict[str, Any]] = {}
        for ep in remote_episodes:
            try:
                # 把集数转为浮点数，兼容 1.5 这种 SP 或 .5 集
                ep_num = float(ep.get('sort') or ep.get('ep', -1))
                if ep_num > 0:  # 只添加有效的集数
                    ep_map[ep_num] = ep
            except (ValueError, TypeError):
                continue

        # 2. 开始遍历本地视频字典
        for file_info in video_data_list:
            
            # 安全拆解文件信息
            if isinstance(file_info, dict):
                # 优先吃进相对路径 (如 Season 2/01.mkv)，拿不到再吃文件名
                name_to_match = file_info.get('relative_path', file_info.get('filename', ''))
                abs_path = file_info.get('path')
            else:
                # 兜底兼容简单路径字符串
                name_to_match = os.path.basename(file_info)
                abs_path = file_info

            if not abs_path:
                continue

            # 清洗字符串，防止 Windows 反斜杠引发正则灾难
            clean_name = name_to_match.lower().replace('\\', '/')

            # 正则提取
            matched_ep: Optional[Dict[str, Any]] = None
            extracted_num: Optional[float] = None

            # 前置过滤：如果是明显的非正片 (特典、菜单、PV)，直接判定为提取失败
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
                # 使用 findall 确保我们能拿到最后一个匹配项，通常文件名末尾的数字更可能是集数
                matches = re.findall(pattern, clean_name, re.IGNORECASE)
                if matches:
                    try:
                        extracted_num = float(matches[-1])
                        break
                    except (ValueError, TypeError):
                        continue
            
            # 认亲环节：如果从路径里抠出了集数数字，且网络端刚好有这一集
            if extracted_num is not None and extracted_num in ep_map:
                matched_ep = ep_map[extracted_num]

            # 无论成功与否，必须拿物理绝对路径 abs_path 作为字典的 Key 返回
            match_result[abs_path] = matched_ep

        return match_result