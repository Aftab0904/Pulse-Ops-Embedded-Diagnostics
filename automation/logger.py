import os
import sys
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

class JsonFormatter(logging.Formatter):
    """Formatter to export log records in structured JSON format."""
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

class ColoredFormatter(logging.Formatter):
    """Formatter to output colored logs in the terminal."""
    GREY = "\x1b[38;20m"
    GREEN = "\x1b[32;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"
    FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    COLORS = {
        logging.DEBUG: GREY,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED
    }

    def format(self, record):
        log_fmt = self.COLORS.get(record.levelno, self.RESET) + self.FORMAT + self.RESET
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

def setup_logger(name="AutomationCore", config_path="configs/config.json"):
    """Creates a custom logger configured via json settings."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Logger is already configured
        
    logger.setLevel(logging.DEBUG)
    
    # Load configuration
    log_dir = "logs"
    log_level_str = "DEBUG"
    max_bytes = 10 * 1024 * 1024
    backup_count = 5

    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
                log_dir = cfg.get("log", {}).get("log_dir", log_dir)
                log_level_str = cfg.get("log", {}).get("level", log_level_str)
                max_bytes = cfg.get("log", {}).get("max_bytes", max_bytes)
                backup_count = cfg.get("log", {}).get("backup_count", backup_count)
        except Exception:
            pass

    log_level = getattr(logging, log_level_str.upper(), logging.DEBUG)
    logger.setLevel(log_level)

    # Ensure log directory exists
    os.makedirs(log_dir, exist_ok=True)

    # 1. Console Handler (Colored)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)

    # 2. File Handler (Colored Text Log)
    text_log_path = os.path.join(log_dir, "automation_run.log")
    text_file_handler = RotatingFileHandler(text_log_path, maxBytes=max_bytes, backupCount=backup_count)
    text_file_handler.setLevel(log_level)
    text_file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(text_file_handler)

    # 3. File Handler (Structured JSON)
    json_log_path = os.path.join(log_dir, "automation_run.json")
    json_file_handler = RotatingFileHandler(json_log_path, maxBytes=max_bytes, backupCount=backup_count)
    json_file_handler.setLevel(log_level)
    json_file_handler.setFormatter(JsonFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(json_file_handler)

    return logger
