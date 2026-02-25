"""
日志模块

提供统一的日志配置，默认 INFO 级别，输出到 stdout。

使用方式:
    from src.utils import get_logger

    logger = get_logger("my-module")
    logger.debug("调试信息")  # 默认不显示
    logger.info("普通信息")
    logger.warning("警告")
    logger.error("错误")

开启调试日志:
    import logging
    logging.getLogger("react").setLevel(logging.DEBUG)
"""

import logging
import sys
from typing import Optional


def get_logger(name: str = "auto-agent", level: Optional[int] = None) -> logging.Logger:
    """
    获取配置好的 logger 实例

    Args:
        name: logger 名称，用于区分不同模块
        level: 可选的日志级别，默认 INFO

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)

    if not logger.handlers:  # 避免重复添加 handler
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level or logging.INFO)

    return logger


# 预定义的模块 logger
supervisor_logger = get_logger("supervisor")
react_logger = get_logger("react")
