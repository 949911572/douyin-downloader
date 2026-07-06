import logging
import sys
from pathlib import Path

_global_console_handler = None


def setup_logger(
    name: str = "dy-downloader",
    level: int = logging.INFO,
    log_file: str = None,
    console_level: int = logging.CRITICAL,
) -> logging.Logger:
    global _global_console_handler
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if _global_console_handler is None:
        _global_console_handler = logging.StreamHandler(sys.stderr)
        _global_console_handler.setLevel(console_level)
        _global_console_handler.setFormatter(formatter)
    
    logger.addHandler(_global_console_handler)

    if log_file:
        log_path = Path(log_file)
        if log_path.parent != Path("."):
            log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def set_console_log_level(level: int) -> None:
    global _global_console_handler
    
    if _global_console_handler is not None:
        _global_console_handler.setLevel(level)
    
    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        logger = logging.getLogger(logger_name)
        for handler in list(logger.handlers):
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                handler.setLevel(level)
    
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            handler.setLevel(level)