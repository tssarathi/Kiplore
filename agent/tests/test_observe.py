import io
import json
import logging

from narrator.observe import JsonLines, event, session, setup


def test_a_log_line_is_json_carrying_the_session_and_its_fields():
    record = logging.LogRecord(
        "narrator", logging.INFO, __file__, 1, "answering", None, None
    )
    record.fields = {"seconds": 1.25}

    token = session.set("story-tortoise-9f2c")
    try:
        line = json.loads(JsonLines().format(record))
    finally:
        session.reset(token)

    assert line["session"] == "story-tortoise-9f2c"
    assert line["message"] == "answering"
    assert line["seconds"] == 1.25


def test_setup_leaves_info_lines_actually_reaching_the_handler():
    logger = logging.getLogger("narrator")
    before = (logger.handlers[:], logger.level, logger.propagate)
    stream = io.StringIO()
    try:
        setup()
        handler = logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        handler.setStream(stream)
        event(logger, "first audio", seconds=2.317)
        written = stream.getvalue()
    finally:
        logger.handlers[:], logger.level, logger.propagate = before

    assert json.loads(written)["seconds"] == 2.317
