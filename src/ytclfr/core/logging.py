import contextvars
import json
import logging
from datetime import datetime

from ytclfr.core.config import Settings


trace_id_var = contextvars.ContextVar("trace_id", default="system")


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id_var.get(),
        }
        if record.exc_info:
            log_data["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def configure_logging(settings: Settings) -> None:
    logger = logging.getLogger()
    logger.setLevel(settings.log_level.upper())

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.addFilter(TraceIdFilter())
    formatter: logging.Formatter
    if settings.environment.lower() == "production":
        formatter = JSONFormatter()
    else:
        # Human-readable format in development
        formatter = logging.Formatter(
            "%(asctime)s - [%(trace_id)s] - %(name)s - %(levelname)s - %(message)s"
        )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
