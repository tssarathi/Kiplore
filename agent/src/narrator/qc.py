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


def longest_silence(samples: array.array, boundaries: list[float]) -> float:
    window = int(SAMPLE_RATE * SILENCE_WINDOW_SECONDS)
    quiet = SILENCE_RMS * 32768
    longest, began = 0.0, None

    def measure(end: float) -> float:
        if began is None or any(began <= edge <= end for edge in boundaries):
            return 0.0
        return end - began

    for start in range(0, len(samples) - window, window):
        at = start / SAMPLE_RATE
        block = samples[start : start + window]
        if math.sqrt(sum(s * s for s in block) / window) < quiet:
            if began is None:
                began = at
            continue
        longest, began = max(longest, measure(at)), None
    return max(longest, measure(len(samples) / SAMPLE_RATE))


def inspect(
    pcm: bytes, spoken: str, segments: list[dict], boundaries: list[float]
) -> str | None:
    samples = array.array("h", pcm)
    seconds = len(samples) / SAMPLE_RATE
    if seconds <= 0:
        return "the render is empty"

    density = len(spoken) / seconds
    if not MIN_CHARS_PER_SECOND <= density <= MAX_CHARS_PER_SECOND:
        return f"speech density is {density:.1f} characters per second"

    silence = longest_silence(samples, boundaries)
    if silence > MAX_SILENCE_SECONDS:
        return f"a silence of {silence:.1f}s"

    if not segments:
        return "there are no caption segments"
    coverage = (segments[-1]["end"] - segments[0]["start"]) / seconds
    if coverage < MIN_ALIGNMENT_COVERAGE:
        return f"the alignment covers only {coverage:.0%} of the audio"

    return None
