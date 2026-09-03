"""Character timestamps into words, sentences and captions."""

import re

TAG = re.compile(r"\[[^\]]*\]\s*")
SENTENCE_END = (".", "!", "?")
QUOTES = "”\"'"


def spoken_text(script: list[str]) -> str:
    return " ".join(TAG.sub("", chunk) for chunk in script)


def words_from_chars(
    chars: list[str], starts: list[float], ends: list[float]
) -> list[dict]:
    words: list[dict] = []
    text, start, end, depth = "", 0.0, 0.0, 0
    for char, first, last in zip(chars, starts, ends):
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
    segments: list[dict] = []
    parts: list[str] = []
    start = end = 0.0

    def flush() -> None:
        nonlocal parts
        text = " ".join(parts)
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


def segment_at(segments: list[dict], position: float) -> dict | None:
    current = None
    for segment in segments:
        if segment["start"] > position:
            break
        current = segment
    return current


def heard_text(
    script: list[str], segments: list[dict], timings: list[float], position: float
) -> str:
    if segments:
        return " ".join(s["text"] for s in segments if s["start"] <= position)
    index = next((i for i, end in enumerate(timings) if position < end), len(timings))
    return spoken_text(script[: index + 1])


def chunk_start(timings: list[float], position: float) -> float:
    for index, end in enumerate(timings):
        if position < end:
            return 0.0 if index == 0 else timings[index - 1]
    return timings[-1] if timings else 0.0
