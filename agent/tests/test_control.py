import asyncio
import json

from narrator.main import control, drop_stale


def encode(message: object) -> bytes:
    return json.dumps(message).encode()


def test_a_well_formed_control_packet_is_accepted():
    assert control(encode({"action": "pause"})) == {"action": "pause"}
    assert control(encode({"action": "seek", "offset": -10})) == {
        "action": "seek",
        "offset": -10,
    }


def test_a_malformed_packet_never_reaches_the_player():
    rejected: list[object] = [
        {"action": "rewind"},
        {"action": "seek"},
        {"action": "seek", "offset": "10"},
        {"action": "seek", "offset": True},
        {"action": "seek", "offset": float("nan")},
        {"action": "seek", "offset": float("inf")},
        {},
        [1, 2, 3],
        "not an object",
        None,
    ]

    for message in rejected:
        assert control(encode(message)) is None, f"accepted {message}"


def test_bytes_that_are_not_json_are_refused_rather_than_thrown():
    assert control(b"\xff\xfe") is None


def test_a_question_left_over_from_an_earlier_turn_is_never_answered_late():
    async def scenario() -> None:
        questions: asyncio.Queue[str | None] = asyncio.Queue()
        questions.put_nowait("Hello?")
        questions.put_nowait("Hello? Hello?")

        assert drop_stale(questions) == 2
        assert questions.empty()

    asyncio.run(scenario())


def test_a_departure_outlives_the_questions_it_cancels():
    async def scenario() -> None:
        questions: asyncio.Queue[str | None] = asyncio.Queue()
        questions.put_nowait("Hello?")
        questions.put_nowait(None)
        questions.put_nowait("said after the drop")

        drop_stale(questions)

        assert questions.get_nowait() is None

    asyncio.run(scenario())
