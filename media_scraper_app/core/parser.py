# 文件路径: core/parser.py

import re
from pathlib import Path
import PTN

from models.media_entity import MediaType, MediaEntity, Movie, Episode
from utils.logger import logger
from utils.exceptions import ParserError

class FilenameParser:
    """
    核心文件名解析引擎。
    负责将杂乱的文件名转换为结构化的 MediaEntity (Movie 或 Episode)。
    """
    
    # 针对二次元动漫特化的保底正则 (匹配类似: [压制组] 番剧名称 - 01 (分辨率) [Hash].mkv)
    # 提取组 1: 标题, 提取组 2: 集数
    ANIME_FALLBACK_REGEX = re.compile(r'\[.*?\]\s*(.+?)\s*-\s*(\d+(?:\.\d+)?).+?')

    @classmethod
    def parse(cls, file_path: str) -> MediaEntity:
        """
        解析文件路径并返回对应的实体对象。
        """
        path_obj = Path(file_path)
        filename = path_obj.name
        
        logger.info(f"开始解析文件: {filename}")
        
        # 1. 使用 PTN 进行基础解析
        parsed_data = PTN.parse(filename)
        
        title = parsed_data.get('title')
        episode_num = parsed_data.get('episode')
        season_num = parsed_data.get('season')
        
        # 2. 如果 PTN 没抓到标题或集数，启动动漫特化正则进行抢救
        if not title or episode_num is None:
            logger.debug(f"PTN 解析信息不全，尝试使用动漫特化正则抢救: {filename}")
            match = cls.ANIME_FALLBACK_REGEX.search(filename)
            if match:
                title = match.group(1).strip()
                episode_num = int(float(match.group(2)))
                logger.debug(f"正则抢救成功 -> 标题: {title}, 集数: {episode_num}")
            else:
                # 抢救失败，抛出我们在 utils/exceptions.py 中定义的异常
                raise ParserError(filename, "PTN 与动漫正则均无法提取有效的标题和集数")

        # 3. 组装数据模型 (models/media_entity.py)
        # 如果包含 episode 信息，我们就认为它是单集 (Episode)，否则暂时归类为电影/剧场版 (Movie)
        if episode_num is not None:
            entity = Episode(
                file_path=file_path,
                original_filename=filename,
                title=title,
                year=parsed_data.get('year'),
                resolution=parsed_data.get('resolution'),
                video_codec=parsed_data.get('codec'),
                audio_codec=parsed_data.get('audio'),
                release_group=parsed_data.get('group'),
                season=season_num if season_num else 1, # 默认第一季
                episode=episode_num
            )
        else:
            entity = Movie(
                file_path=file_path,
                original_filename=filename,
                title=title,
                year=parsed_data.get('year'),
                resolution=parsed_data.get('resolution'),
                video_codec=parsed_data.get('codec'),
                audio_codec=parsed_data.get('audio'),
                release_group=parsed_data.get('group')
            )
            
        logger.info(f"解析完成: {entity.title} " + (f"(S{entity.season:02d}E{entity.episode:02d})" if entity.media_type == MediaType.EPISODE else ""))
        return entity