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
        """(Re)configure the process-global loguru logger.

        Intentionally reconfigures on every call (remove() -> add()) instead
        of skipping when "already configured": a configured flag would be
        inherited by fork-started children and silently skip their
        reconfiguration, while remove() -> add() never accumulates handlers,
        so it is correct for both fork and spawn start methods.
        """
        # Register the custom level first so level="PERFORMANCE" validates.
        try:
            logger.level("PERFORMANCE", no=38, color="<yellow>", icon="🚀")
        except ValueError:
            # Level already exists, ignore.
            pass

        level_name = self.config.level.upper()
        try:
            logger.level(level_name)
        except ValueError:
            raise ValueError(
                f"Invalid logging level: {self.config.level!r} "
                "(use TRACE/DEBUG/INFO/SUCCESS/WARNING/ERROR/CRITICAL)"
            ) from None

        logger.remove()
        logger.add(
            sys.stdout if self.config.output == "console" else self.config.output,
            level=level_name,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        )

    def get_logger(self):
        return logger
