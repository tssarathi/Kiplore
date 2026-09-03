"""Character times into words, sentences and captions."""

import re
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class Timings:
    """Sentence start and end times, and each chunk's end, all in seconds."""

    segments: list[dict] = field(default_factory=list)
    chunk_timings: list[float] = field(default_factory=list)


# stripping the tags: "[warmly]" directs the synthesiser and is never spoken
TAG = re.compile(r"\[[^\]]*\]\s*")
SENTENCE_END = (".", "!", "?")
QUOTES = "”\"'"  # stripped first: a closing quote sits outside its full stop


def spoken_text(script: list[str]) -> str:
    """The story with [tags] removed."""
    return " ".join(TAG.sub("", chunk) for chunk in script)


def keyterms(script: list[str]) -> list[str]:
    """Proper nouns to bias the recogniser, filtered by the lowercase test."""
    words = re.findall(r"[A-Za-z]+", spoken_text(script))
    seen = Counter(word for word in words if word[0].isupper() and len(word) > 2)
    # also seen lowercase: an ordinary word that started a sentence, not a name
    lower = {word for word in words if word[0].islower()}
    return [w for w, n in seen.most_common() if n >= 3 and w.lower() not in lower][:10]


def words_from_chars(
    chars: list[str], starts: list[float], ends: list[float]
) -> list[dict]:
    """Characters into words, counting bracket depth to skip tags."""
    words: list[dict] = []
    text, start, end, depth = "", 0.0, 0.0, 0
    for char, first, last in zip(chars, starts, ends, strict=True):
        # counted, not matched: a tag can split across two streamed events
        if char == "[":
            depth += 1
        elif char == "]":
            depth = max(0, depth - 1)
        elif depth:
            continue
        elif char.isspace():
            if text:
                words.append({"text": text, "start": start, "end": end})
                text = ""
        else:
            if not text:
                start = first
            text += char
            end = last
    if text:
        words.append({"text": text, "start": start, "end": end})
    return words


def to_segments(words: list[dict]) -> list[dict]:
    """Words into sentences; re-join lowercase fragments."""
    segments: list[dict] = []
    parts: list[str] = []
    start = end = 0.0

    def flush() -> None:
        nonlocal parts
        text = " ".join(parts)
        # "Mr." ends no sentence, so a lowercase fragment is glued back on
        if segments and text[:1].islower():
            segments[-1]["text"] += " " + text
            segments[-1]["end"] = round(end, 2)
        else:
            segments.append(
                {"start": round(start, 2), "end": round(end, 2), "text": text}
            )
        parts = []

    for word in words:
        if not parts:
            start = word["start"]
        end = word["end"]
        parts.append(word["text"])
        if word["text"].rstrip(QUOTES).endswith(SENTENCE_END):
            flush()
    if parts:
        flush()
    return segments


# the three lookups: which sentence, how much was heard, where a chunk began
def segment_at(segments: list[dict], position: float) -> dict | None:
    """The sentence most recently begun, even if it has ended."""
    current = None
    for segment in segments:
        if segment["start"] > position:
            break
        current = segment
    return current


def heard_text(
    script: list[str], segments: list[dict], timings: list[float], position: float
) -> str:
    """The story so far: the whole no-spoilers rule."""
    if segments:
        return " ".join(s["text"] for s in segments if s["start"] <= position)
    # alignment can still be empty early in a live render, so fall back to chunks
    index = next((i for i, end in enumerate(timings) if position < end), len(timings))
    return spoken_text(script[: index + 1])


def chunk_start(timings: list[float], position: float) -> float:
    """The coarse resume point when no sentence fits."""
    for index, end in enumerate(timings):
        if position < end:
            return 0.0 if index == 0 else timings[index - 1]
    return timings[-1] if timings else 0.0
