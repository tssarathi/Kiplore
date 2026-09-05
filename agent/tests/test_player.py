from narrator.audio import seconds_to_bytes
from narrator.config import SAMPLE_RATE
from narrator.envelope import GainRamp
from narrator.player import Player


def test_seeking_past_either_end_of_the_tape_is_clamped():
    player = Player()
    player.append(bytes(seconds_to_bytes(10.0)))

    player.seek(seconds_to_bytes(-5.0))
    assert player.position == 0.0

    player.seek(seconds_to_bytes(99.0))
    assert player.position == 10.0


def test_a_fade_stops_on_its_target_from_either_direction():
    down = GainRamp()
    down.set(0.0, 0.1)
    for _ in range(20):
        down.step(0.02)
    assert down.gain == 0.0

    up = GainRamp()
    up.snap(0.25)
    up.set(1.0, 0.1)
    for _ in range(20):
        up.step(0.02)
    assert up.gain == 1.0


def test_a_time_becomes_a_whole_number_of_samples():
    assert seconds_to_bytes(1.0) == SAMPLE_RATE * 2
    assert seconds_to_bytes(0.0) == 0
    assert all(seconds_to_bytes(s) % 2 == 0 for s in (0.001, 0.019, 1.7, 12.345))
