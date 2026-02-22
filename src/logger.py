"""
Copyright (c) 2025 Nobuo Tsukamoto
This software is released under the MIT License.
See the LICENSE file in the project root for more information.
"""

import sys
from loguru import logger
from config_manager import LoggingConfig


class Logger:
    def __init__(self, config: LoggingConfig):
        self.config = config
        self._configure_logger()

    def _configure_logger(self):
        logger.remove()
        logger.add(
            sys.stdout if self.config.output == "console" else self.config.output,
            level=self.config.level.upper(),
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        )

        # Add performance level
        try:
            logger.level("PERFORMANCE", no=38, color="<yellow>", icon="🚀")
        except ValueError:
            # Level already exists, ignore.
            pass

    def get_logger(self):
        return logger
