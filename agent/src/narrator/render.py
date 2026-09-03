"""Turning story text into the narrator's voice."""

import base64
import hashlib
import itertools
import json
import math
import os
from collections.abc import AsyncIterator

import aiohttp

from narrator.alignment import spoken_text, to_segments, words_from_chars
from narrator.config import (
    CHUNK_GAP_SECONDS,
    ELEVEN_MODEL,
    MAX_STORY_TEXT_CHARS,
    OUTPUT_FORMAT,
    SAMPLE_RATE,
    SEED,
    VOICE_SETTINGS,
)

SYNTHESIS_TIMEOUT = 600
GAP_SAMPLES = int(SAMPLE_RATE * CHUNK_GAP_SECONDS)
GAP = bytes(GAP_SAMPLES * 2)
GAP_SECONDS = GAP_SAMPLES / SAMPLE_RATE


def offset_of(seconds: float) -> int:
    return int(seconds * SAMPLE_RATE) * 2


def _finite(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value >= 0
    )


def _parse(line: bytes) -> tuple[bytes, list[str], list[float], list[float]]:
    event = json.loads(line)
    audio = event.get("audio_base64")
    if not isinstance(audio, str):
        raise RuntimeError("synthesis event is malformed")
    pcm = base64.b64decode(audio, validate=True)
    if len(pcm) % 2:
        raise RuntimeError("synthesis audio is not whole samples")
    alignment = event.get("alignment")
    if alignment is None:
        return pcm, [], [], []
    if not isinstance(alignment, dict):
        raise RuntimeError("synthesis event is malformed")
    chars = alignment.get("characters")
    starts = alignment.get("character_start_times_seconds")
    ends = alignment.get("character_end_times_seconds")
    if not (
        isinstance(chars, list) and isinstance(starts, list) and isinstance(ends, list)
    ):
        raise RuntimeError("synthesis alignment is malformed")
    if not len(chars) == len(starts) == len(ends):
        raise RuntimeError("synthesis alignment lengths differ")
    if not all(isinstance(char, str) and len(char) == 1 for char in chars):
        raise RuntimeError("synthesis characters are malformed")
    if not all(_finite(s) and _finite(e) and e >= s for s, e in zip(starts, ends)):
        raise RuntimeError("synthesis times are malformed")
    return pcm, chars, starts, ends


async def _events(
    text: str, voice_id: str
) -> AsyncIterator[tuple[bytes, list[str], list[float], list[float]]]:
    url = (
        "https://api.elevenlabs.io/v1/text-to-speech/"
        f"{voice_id}/stream/with-timestamps"
    )
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=SYNTHESIS_TIMEOUT)
    ) as session:
        async with session.post(
            url,
            params={"output_format": OUTPUT_FORMAT},
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
            json={
                "text": text,
                "model_id": ELEVEN_MODEL,
                "voice_settings": VOICE_SETTINGS,
                "seed": SEED,
            },
        ) as response:
            if response.status != 200:
                detail = (await response.content.read(200)).decode(errors="replace")
                raise RuntimeError(f"synthesis failed, HTTP {response.status}: {detail}")
            buffer = b""
            async for data in response.content.iter_any():
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.strip():
                        yield _parse(line)
            if buffer.strip():
                yield _parse(buffer)


def shift_words(words: list[dict], counts: list[int]) -> list[dict]:
    shifted: list[dict] = []
    index = 0
    for chunk, count in enumerate(counts):
        shift = chunk * GAP_SECONDS
        for word in words[index : index + count]:
            shifted.append(
                {
                    "text": word["text"],
                    "start": word["start"] + shift,
                    "end": word["end"] + shift,
                }
            )
        index += count
    return shifted


def insert_gaps(
    pcm: bytes, words: list[dict], counts: list[int]
) -> tuple[bytes, list[dict], list[float]]:
    if sum(counts) != len(words):
        raise RuntimeError(
            f"word mapping failed: script has {sum(counts)} spoken words, "
            f"alignment produced {len(words)}"
        )
    cuts = []
    index = 0
    for count in counts[:-1]:
        index += count
        cuts.append((words[index - 1]["end"] + words[index]["start"]) / 2)

    gapped = bytearray()
    previous = 0
    for cut in cuts:
        gapped += pcm[previous : offset_of(cut)] + GAP
        previous = offset_of(cut)
    gapped += pcm[previous:] + GAP

    shifted = shift_words(words, counts)
    timings = [round(cut + (k + 1) * GAP_SECONDS, 2) for k, cut in enumerate(cuts)]
    raw_seconds = len(pcm) / 2 / SAMPLE_RATE
    timings.append(round(raw_seconds + len(counts) * GAP_SECONDS, 2))
    return bytes(gapped), shifted, timings


class Narration:
    def __init__(self, story: dict, voice_id: str) -> None:
        self.segments: list[dict] = []
        self.chunk_timings: list[float] = []
        self._text = "\n\n".join(story["script"])
        if len(self._text) > MAX_STORY_TEXT_CHARS:
            raise RuntimeError("story exceeds the synthesis text limit")
        self._counts = [len(spoken_text([chunk]).split()) for chunk in story["script"]]
        self._voice_id = voice_id

    async def stream(self) -> AsyncIterator[bytes]:
        pcm = bytearray()
        chars: list[str] = []
        starts: list[float] = []
        ends: list[float] = []
        boundaries = list(itertools.accumulate(self._counts[:-1]))
        cuts: list[float] = []
        emitted = gaps_emitted = sent = 0
        digest = hashlib.sha256()

        async for event, event_chars, event_starts, event_ends in _events(
            self._text, self._voice_id
        ):
            pcm += event
            chars += event_chars
            starts += event_starts
            ends += event_ends
            words = words_from_chars(chars, starts, ends)

            while len(cuts) < len(boundaries) and len(words) > boundaries[len(cuts)]:
                index = boundaries[len(cuts)]
                cuts.append((words[index - 1]["end"] + words[index]["start"]) / 2)
                self.chunk_timings.append(round(cuts[-1] + len(cuts) * GAP_SECONDS, 2))
            self.segments = to_segments(shift_words(words, self._counts))

            if len(cuts) == len(boundaries):
                safe_end = len(pcm)
            elif words:
                safe_end = min(len(pcm), offset_of(words[-1]["end"]))
            else:
                safe_end = emitted

            while gaps_emitted < len(cuts):
                cut = offset_of(cuts[gaps_emitted])
                if cut > safe_end:
                    break
                block = bytes(pcm[emitted:cut]) + GAP
                digest.update(block)
                sent += len(block)
                emitted = cut
                gaps_emitted += 1
                yield block

            if safe_end > emitted:
                block = bytes(pcm[emitted:safe_end])
                digest.update(block)
                sent += len(block)
                emitted = safe_end
                yield block

        words = words_from_chars(chars, starts, ends)
        gapped, shifted, timings = insert_gaps(bytes(pcm), words, self._counts)
        if digest.digest() != hashlib.sha256(gapped[:sent]).digest():
            raise RuntimeError("streamed audio does not match the final render")
        self.segments = to_segments(shifted)
        self.chunk_timings[:] = timings
        if len(gapped) > sent:
            yield gapped[sent:]


async def stream_answer(text: str, voice_id: str) -> AsyncIterator[bytes]:
    async for pcm, _, _, _ in _events(text, voice_id):
        yield pcm
