"""Structured logs, and the three timings a voice agent is judged on.

Logging is configured inside the job rather than at import, because the LiveKit CLI
sets up its own handlers first and would otherwise win.
"""

import json
import logging
import time
from contextvars import ContextVar

# Set once per job. Two children listening at once share a process and interleave their
# log lines, and this is the only thing that tells them apart afterwards.
session: ContextVar[str] = ContextVar("session", default="")


class JsonLines(logging.Formatter):
    """One JSON object per line, so a log aggregator can index the fields."""

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
    """Send the narrator's logs to stdout as JSON, and nowhere else."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLines())
    logger = logging.getLogger("narrator")
    logger.handlers[:] = [handler]
    # Set explicitly. Without it the level is inherited from root, which defaults to
    # WARNING, and every info line this module exists to emit is dropped.
    logger.setLevel(logging.INFO)
    logger.propagate = False


def event(logger: logging.Logger, message: str, **fields: object) -> None:
    """Log a line with structured fields attached to it."""
    logger.info(message, extra={"fields": fields})


def since(started: float) -> float:
    """Seconds since a `time.monotonic()` mark, to the millisecond."""
    return round(time.monotonic() - started, 3)
