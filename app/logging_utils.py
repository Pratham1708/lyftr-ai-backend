"""
Structured JSON logging utilities for request/response tracking.
"""
import json
import logging
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar

from app.config import Config


# Context variable to store request ID across async contexts
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs logs as JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add request ID if available
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id
        
        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logging() -> None:
    """Configure application logging based on config."""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper()))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Set formatter based on config
    if Config.LOG_FORMAT.lower() == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        )
    
    logger.addHandler(handler)


def log_request(
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """Log HTTP request with structured data."""
    logger = logging.getLogger("app.request")
    
    log_data = {
        "method": method,
        "path": path,
        "status": status_code,
        "latency_ms": round(latency_ms, 2),
    }
    
    if extra:
        log_data.update(extra)
    
    # Create a log record with extra fields
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        "(log_request)",
        0,
        f"{method} {path} {status_code} {latency_ms:.2f}ms",
        (),
        None
    )
    record.extra_fields = log_data
    logger.handle(record)


def log_webhook(
    message_id: str,
    dup: bool,
    result: str,
    method: str,
    path: str,
    status_code: int,
    latency_ms: float
) -> None:
    """Log webhook request with specific fields."""
    logger = logging.getLogger("app.webhook")
    
    log_data = {
        "method": method,
        "path": path,
        "status": status_code,
        "latency_ms": round(latency_ms, 2),
        "message_id": message_id,
        "dup": dup,
        "result": result
    }
    
    # Add request ID if available
    request_id = request_id_var.get()
    if request_id:
        log_data["request_id"] = request_id
    
    # Create a log record with extra fields
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        "(log_webhook)",
        0,
        f"Webhook {message_id} - {result}",
        (),
        None
    )
    record.extra_fields = log_data
    logger.handle(record)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


class RequestLogger:
    """Context manager for logging request lifecycle."""
    
    def __init__(self, method: str, path: str, request_id: str):
        self.method = method
        self.path = path
        self.request_id = request_id
        self.start_time = None
        self.logger = get_logger("app.request")
    
    def __enter__(self):
        """Start request logging."""
        request_id_var.set(self.request_id)
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Complete request logging."""
        duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type is None:
            status_code = 200
        else:
            status_code = 500
        
        log_request(
            self.method,
            self.path,
            status_code,
            duration_ms,
            {"request_id": self.request_id}
        )
        
        request_id_var.set(None)
