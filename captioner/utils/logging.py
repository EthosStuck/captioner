"""Structured logging configuration."""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    verbose: bool = False,
    log_file: Optional[Path] = None,
    log_level: Optional[str] = None
) -> None:
    """
    Configure structured logging for captioner.
    
    Args:
        verbose: Enable DEBUG level logging
        log_file: Optional path to log file
        log_level: Override log level (DEBUG, INFO, WARNING, ERROR)
    """
    # Determine log level
    if log_level:
        level = getattr(logging, log_level.upper(), logging.INFO)
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Configure handlers
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True  # Override any existing configuration
    )
    
    # Set specific library log levels to reduce noise
    logging.getLogger("ffmpeg").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
