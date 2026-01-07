"""
Production logging configuration with rotation

Sets up structured logging with:
- Console output for development
- Rotating file logs for production
- JSON formatting for log aggregation
- Request/response logging middleware
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
import json
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        return json.dumps(log_data)


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[str] = None,
    app_name: str = "dmarc-processor",
    enable_json: bool = False
):
    """
    Configure application logging

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files. If None, only console logging is enabled.
        app_name: Application name for log files
        enable_json: Enable JSON formatting for structured logging
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    if enable_json:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(console_format)

    root_logger.addHandler(console_handler)

    # File handler with rotation (if log_dir is specified)
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Main application log with size-based rotation
        app_log_file = log_path / f"{app_name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            app_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,  # Keep 5 backup files
            encoding="utf-8"
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))

        if enable_json:
            file_handler.setFormatter(JSONFormatter())
        else:
            file_format = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_format)

        root_logger.addHandler(file_handler)

        # Error log - only errors and above
        error_log_file = log_path / f"{app_name}-error.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)

        if enable_json:
            error_handler.setFormatter(JSONFormatter())
        else:
            error_handler.setFormatter(file_format)

        root_logger.addHandler(error_handler)

        logging.info(f"File logging enabled: {app_log_file}")

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)

    logging.info(f"Logging configured: level={log_level}, json={enable_json}")


async def log_requests_middleware(request, call_next):
    """
    Middleware to log HTTP requests and responses

    Logs:
    - Request method, path, headers
    - Response status code, duration
    """
    import time
    import uuid

    # Generate request ID
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id

    # Log request
    logger = logging.getLogger("app.requests")
    logger.info(
        f"Request started: {request.method} {request.url.path}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else None
        }
    )

    # Process request
    start_time = time.time()
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000

        # Log response
        logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2)
            }
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000

        logger.error(
            f"Request failed: {request.method} {request.url.path} - {str(e)}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round(duration_ms, 2)
            },
            exc_info=True
        )
        raise
