import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging() -> logging.Logger:
    log_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ClaudeUsageMonitor"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "monitor.log"

    logger = logging.getLogger("monitor")
    logger.setLevel(logging.DEBUG)

    handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(handler)

    return logger
