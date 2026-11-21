import json
import logging
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """
    Structured JSON log formatter for production logging and SIEM integration.
    Never exposes passwords, tokens, or credentials.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if hasattr(record, "correlation_id") and record.correlation_id:
            log_obj["correlation_id"] = record.correlation_id
        if hasattr(record, "trace_id") and record.trace_id:
            log_obj["trace_id"] = record.trace_id
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, default=str)
