
import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

class JsonFormatter(logging.Formatter):


    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            entry["request_id"] = rid

        for key in ("latency_ms", "step", "event"):
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = value

        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str)

def setup_logging(log_level: str = "INFO", service_name: str = "healthlink") -> logging.Logger:

    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.handlers.clear()
    logger.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level.upper()))
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    logger.info("Logging initialized", extra={"event": "startup"})
    return logger

def get_logger(name: str = "healthlink") -> logging.Logger:

    return logging.getLogger(name)

def set_request_id(request_id: str) -> None:

    request_id_var.set(request_id)

def log_step(logger: logging.Logger, step: str, latency_ms: float, event: str = "agent_step") -> None:

    logger.info(
        f"step={step} latency_ms={latency_ms:.0f}",
        extra={"step": step, "latency_ms": round(latency_ms, 1), "event": event},
    )
