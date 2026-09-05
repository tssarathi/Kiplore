import json

from narrator.main import control


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
