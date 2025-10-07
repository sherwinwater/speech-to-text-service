
import logging
import sys
from typing import Optional

def configure_logging(level: str = "INFO"):
    """Configure structured logging for the application"""
    
    # Create formatter with consistent format
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers and add our formatted handler
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Configure uvicorn and related loggers to use our formatter
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "websockets.protocol", "websockets.server"]:
        lib_logger = logging.getLogger(logger_name)
        lib_logger.handlers.clear()
        lib_logger.addHandler(console_handler)
        lib_logger.propagate = False
    
    # Set specific log levels
    logging.getLogger("server").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # Hide HTTP requests
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)   # Hide "connection open/closed" (they use error logger)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("websockets.protocol").setLevel(logging.WARNING)  # Hide WS protocol noise
    logging.getLogger("websockets.server").setLevel(logging.WARNING)    # Hide WS server noise

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with consistent naming"""
    return logging.getLogger(f"server.{name}")
