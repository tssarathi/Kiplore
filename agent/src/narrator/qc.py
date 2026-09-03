"""Is this render good enough to keep?"""

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
    """Longest quiet stretch that is not a deliberate chunk gap."""
    window = int(SAMPLE_RATE * SILENCE_WINDOW_SECONDS)
    quiet = SILENCE_RMS * 32768
    longest, began = 0.0, None

    # a quiet stretch containing a deliberate chunk gap does not count
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
    """Empty, density, silence, coverage: the reason it failed, not a bool."""
    samples = array.array("h", pcm)
    seconds = len(samples) / SAMPLE_RATE
    if seconds <= 0:
        return "the render is empty"

    # speech density catches audio too fast, too slow, or mostly missing
    density = len(spoken) / seconds
    if not MIN_CHARS_PER_SECOND <= density <= MAX_CHARS_PER_SECOND:
        return f"speech density is {density:.1f} characters per second"

    silence = longest_silence(samples, boundaries)
    if silence > MAX_SILENCE_SECONDS:
        return f"a silence of {silence:.1f}s"

    if not segments:
        return "there are no caption segments"

    # coverage: alignment that stopped partway leaves the end with no captions
    coverage = (segments[-1]["end"] - segments[0]["start"]) / seconds
    if coverage < MIN_ALIGNMENT_COVERAGE:
        return f"the alignment covers only {coverage:.0%} of the audio"

    return None
