import json
import logging
from datetime import datetime, timezone


APP_LOG_CATEGORIES = {
    "audit",
    "auth",
    "trips",
    "jobs",
    "inventory",
    "warehouse",
    "verification",
    "security",
    "monitoring",
    "system",
}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        event = getattr(record, "event", None)
        if isinstance(event, dict):
            payload["event"] = event

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def get_app_logger(category):
    if category not in APP_LOG_CATEGORIES:
        category = "system"
    return logging.getLogger(f"harborops.{category}")


def log_app_event(category, action, level="info", **fields):
    logger = get_app_logger(category)
    fn = getattr(logger, level, logger.info)
    fn(action, extra={"event": {"category": category, "action": action, **fields}})
