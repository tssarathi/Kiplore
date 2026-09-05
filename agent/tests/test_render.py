import array

import pytest

from narrator.config import SAMPLE_RATE
from narrator.render import GAP, GAP_SECONDS, insert_gaps, offset_of

SILENT = b"\x00\x00"


def tone(seconds: float) -> bytes:
    return array.array("h", [3000] * int(SAMPLE_RATE * seconds)).tobytes()


def test_gaps_land_between_chunks_and_the_timings_point_at_them():
    pcm = tone(2.0)
    words = [
        {"text": "one", "start": 0.0, "end": 0.4},
        {"text": "two", "start": 0.5, "end": 0.9},
        {"text": "three", "start": 1.1, "end": 1.5},
        {"text": "four", "start": 1.6, "end": 2.0},
    ]

    gapped, shifted, timings = insert_gaps(pcm, words, [2, 2])

    assert len(gapped) == len(pcm) + 2 * len(GAP)

    cut = offset_of(1.0)
    assert gapped[:cut] == pcm[:cut]
    assert gapped[cut : cut + len(GAP)] == GAP

    assert timings[0] == pytest.approx(1.0 + GAP_SECONDS)
    edge = offset_of(timings[0])
    assert gapped[edge - 2 : edge] == SILENT
    assert gapped[edge : edge + 2] != SILENT

    assert timings[-1] == pytest.approx(len(gapped) / 2 / SAMPLE_RATE)

    assert shifted[2]["start"] == pytest.approx(1.1 + GAP_SECONDS)
