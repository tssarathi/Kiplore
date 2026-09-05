import json
import logging
import time
from contextvars import ContextVar

session: ContextVar[str] = ContextVar("session", default="")


class JsonLines(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = {
            "time": self.formatTime(record),
            "level": record.levelname.lower(),
            "session": session.get(),
            "message": record.getMessage(),
            **getattr(record, "fields", {}),
        }
        if record.exc_info:
            line["error"] = self.formatException(record.exc_info)
        return json.dumps(line)


def setup() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLines())
    logger = logging.getLogger("narrator")
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False


def event(logger: logging.Logger, message: str, **fields: object) -> None:
    logger.info(message, extra={"fields": fields})


def since(started: float) -> float:
    return round(time.monotonic() - started, 3)
