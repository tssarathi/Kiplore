"""JSON logs, and the three timings: first audio, barge-in, answer."""

import json
import logging
import time
from contextvars import ContextVar

# one process serves two children at once, and their log lines interleave
session: ContextVar[str] = ContextVar("session", default="")


class JsonLines(logging.Formatter):
    """One JSON object per line, session id on every one."""

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
    """JSON to stdout, INFO explicitly, no propagation, inside the job."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLines())
    logger = logging.getLogger("narrator")
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)  # root defaults to WARNING and would drop every line
    logger.propagate = False


def event(logger: logging.Logger, message: str, **fields: object) -> None:
    """A log line with structured fields hung off the record."""
    logger.info(message, extra={"fields": fields})


def since(started: float) -> float:
    """Monotonic stopwatch, milliseconds, never the wall clock."""
    return round(time.monotonic() - started, 3)
