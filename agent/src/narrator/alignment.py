"""Character timestamps into words, sentences and captions.

ElevenLabs times every character it is given. That is the only ground truth about when
anything is spoken, and everything the player knows about position is derived from it
here: characters to words, words to sentences, sentences to captions and resume points.
"""

import re
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class Timings:
    """Sentence spans, and the end of each script chunk in seconds."""

    segments: list[dict] = field(default_factory=list)
    chunk_timings: list[float] = field(default_factory=list)


# Audio tags such as "[warmly]" direct the synthesiser and are never spoken.
TAG = re.compile(r"\[[^\]]*\]\s*")
SENTENCE_END = (".", "!", "?")
QUOTES = "”\"'"  # a closing quote sits outside the full stop it ends


def spoken_text(script: list[str]) -> str:
    """The words that will actually be heard, tags removed."""
    return " ".join(TAG.sub("", chunk) for chunk in script)


def keyterms(script: list[str]) -> list[str]:
    """Proper nouns to bias the transcriber towards: children repeat names back."""
    words = re.findall(r"[A-Za-z]+", spoken_text(script))
    seen = Counter(word for word in words if word[0].isupper() and len(word) > 2)
    # A word also seen lowercase is an ordinary one that started a sentence, not a name.
    lower = {word for word in words if word[0].islower()}
    return [w for w, n in seen.most_common() if n >= 3 and w.lower() not in lower][:10]


def words_from_chars(
    chars: list[str], starts: list[float], ends: list[float]
) -> list[dict]:
    """Group per-character timestamps into {text, start, end} words."""
    words: list[dict] = []
    text, start, end, depth = "", 0.0, 0.0, 0
    for char, first, last in zip(chars, starts, ends):
        # Tag characters come back timed like any other. Counted in and out rather than
        # matched, because a tag can be split across two streamed events.
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
    """Group timed words into timed sentences, the unit captions and resumes work in."""
    segments: list[dict] = []
    parts: list[str] = []
    start = end = 0.0

    def flush() -> None:
        nonlocal parts
        text = " ".join(parts)
        # "Mr." ends no sentence. A fragment starting lowercase is glued back on.
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
    """The sentence most recently begun at `position`, even if it has since ended."""
    current = None
    for segment in segments:
        if segment["start"] > position:
            break
        current = segment
    return current


def heard_text(
    script: list[str], segments: list[dict], timings: list[float], position: float
) -> str:
    """The story as told so far, and the whole of the no-spoilers rule: the model
    writing the answer is given this and nothing else."""
    if segments:
        return " ".join(s["text"] for s in segments if s["start"] <= position)
    # Alignment can still be empty early in a live render. Chunks are coarser than
    # sentences but never over-generous.
    index = next((i for i, end in enumerate(timings) if position < end), len(timings))
    return spoken_text(script[: index + 1])


def chunk_start(timings: list[float], position: float) -> float:
    """Start of the chunk holding `position`: the resume point when no sentence fits."""
    for index, end in enumerate(timings):
        if position < end:
            return 0.0 if index == 0 else timings[index - 1]
    return timings[-1] if timings else 0.0
