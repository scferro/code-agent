"""Logging setup for CodeAgent"""
import logging
import sys
from pathlib import Path
import os
from rich.logging import RichHandler

def setup_logger():
    """Set up logging"""
    # Create logger
    logger = logging.getLogger("codeagent")
    logger.setLevel(logging.INFO)
    
    # Create console handler
    console_handler = RichHandler(rich_tracebacks=True)
    console_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter("%(message)s")
    
    # Add formatter to handler
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    # Create file handler if .codeagent directory exists
    codeagent_dir = Path.cwd() / ".codeagent"
    if codeagent_dir.exists() and codeagent_dir.is_dir():
        log_dir = codeagent_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / "codeagent.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # More detailed formatter for file
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        
        # Add file handler to logger
        logger.addHandler(file_handler)
    
    return logger