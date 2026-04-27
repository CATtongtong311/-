"""结构化日志封装，基于 loguru。"""

import sys
from pathlib import Path

from loguru import logger

from config.settings import get_settings


def setup_logger() -> None:
    """配置全局日志：控制台输出 + 文件轮转 + 压缩归档。"""
    settings = get_settings()

    # 移除默认的 stderr handler
    logger.remove()

    # 控制台输出：简洁格式，带颜色
    logger.add(
        sys.stderr,
        level=settings.log.level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level:<8}</level> | "
        "<cyan>{name}:{function}:{line}</cyan> - {message}",
        colorize=True,
    )

    # 文件输出：结构化 JSON，按天轮转，保留 7 天，自动压缩
    log_path = Path(settings.log.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_path),
        level=settings.log.level,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}",
        rotation="00:00",  # 每天零点轮转
        retention="7 days",  # 保留 7 天
        compression="zip",  # 压缩旧日志
        encoding="utf-8",
        enqueue=True,  # 异步写入，避免阻塞
    )

    logger.info("日志系统初始化完成，级别: {}", settings.log.level)
