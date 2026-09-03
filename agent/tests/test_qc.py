"""A bad render that passes here is served from the cache for ever."""

import array

from narrator import qc
from narrator.config import SAMPLE_RATE

SPOKEN = "The tortoise walked on while the hare slept under the tree."
CAPTIONS = [{"start": 0.0, "end": 4.2, "text": SPOKEN}]


def audio(*parts: tuple[float, int]) -> bytes:
    samples = array.array("h")
    for seconds, level in parts:
        samples.extend([level] * int(SAMPLE_RATE * seconds))
    return samples.tobytes()


def test_a_dead_spot_keeps_a_render_out_of_the_cache():
    stalled = audio((1.0, 3000), (2.5, 0), (1.0, 3000))

    reason = qc.inspect(stalled, SPOKEN, CAPTIONS, [])

    assert reason is not None and "silence" in reason


def test_the_gaps_put_between_chunks_are_not_a_dead_spot():
    # same audio, but the quiet stretch is now a boundary we asked for
    deliberate = audio((1.0, 3000), (2.5, 0), (1.0, 3000))

    assert qc.inspect(deliberate, SPOKEN, CAPTIONS, [2.0]) is None
