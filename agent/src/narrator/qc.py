"""What a render must pass before it is allowed into the cache."""

import array
import math

from narrator.config import (
    MAX_CHARS_PER_SECOND,
    MAX_SILENCE_SECONDS,
    MIN_ALIGNMENT_COVERAGE,
    MIN_CHARS_PER_SECOND,
    SAMPLE_RATE,
    SILENCE_RMS,
    SILENCE_WINDOW_SECONDS,
)


def longest_silence(samples: array.array) -> float:
    window = int(SAMPLE_RATE * SILENCE_WINDOW_SECONDS)
    quiet = SILENCE_RMS * 32768
    longest = run = 0
    for start in range(0, len(samples) - window, window):
        block = samples[start : start + window]
        if math.sqrt(sum(s * s for s in block) / window) < quiet:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return longest * SILENCE_WINDOW_SECONDS


def inspect(pcm: bytes, spoken: str, segments: list[dict]) -> str | None:
    samples = array.array("h", pcm)
    seconds = len(samples) / SAMPLE_RATE
    if seconds <= 0:
        return "the render is empty"

    density = len(spoken) / seconds
    if not MIN_CHARS_PER_SECOND <= density <= MAX_CHARS_PER_SECOND:
        return f"speech density is {density:.1f} characters per second"

    silence = longest_silence(samples)
    if silence > MAX_SILENCE_SECONDS:
        return f"a silence of {silence:.1f}s"

    if not segments:
        return "there are no caption segments"
    coverage = (segments[-1]["end"] - segments[0]["start"]) / seconds
    if coverage < MIN_ALIGNMENT_COVERAGE:
        return f"the alignment covers only {coverage:.0%} of the audio"

    return None
