import array
import asyncio

from narrator import cache
from narrator.alignment import Timings
from narrator.config import SAMPLE_RATE


def render(seconds: float) -> bytes:
    return array.array("h", [3000] * int(SAMPLE_RATE * seconds)).tobytes()


def test_an_unconfigured_bucket_is_a_reason_not_a_crash(monkeypatch):
    for name in (
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET",
    ):
        monkeypatch.delenv(name, raising=False)
    timings = Timings(
        [{"start": 0.0, "end": 1.9, "text": "The tortoise walked on."}], [2.0]
    )

    reason = asyncio.run(
        cache.save(
            "library/x/y/z/0", render(2.0), timings, "The tortoise walked on and on."
        )
    )

    assert reason is not None and "upload failed" in reason


def test_a_render_that_fails_quality_is_never_uploaded(monkeypatch):
    def refuse(*_: object) -> None:
        raise AssertionError("a rejected render must not reach the bucket")

    monkeypatch.setattr(cache, "_client", refuse)
    timings = Timings(
        [{"start": 0.0, "end": 1.9, "text": "The tortoise walked on."}], [2.0]
    )

    reason = cache._save("library/x/y/z/0", render(2.0), timings, "short")

    assert reason is not None and "density" in reason
