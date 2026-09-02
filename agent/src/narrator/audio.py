"""Sending sound into the room."""

import asyncio
from collections.abc import AsyncIterator

from livekit import rtc
from livekit.agents import JobContext

from narrator.config import (
    CHUNK_SECONDS,
    FRAME_SAMPLES,
    NUM_CHANNELS,
    PAUSE_FADE_SECONDS,
    SAMPLE_RATE,
    SOURCE_QUEUE_MS,
)
from narrator.envelope import GainRamp, scale
from narrator.player import Player

FRAME_BYTES = FRAME_SAMPLES * 2


def discard_queued(source: rtc.AudioSource, player: Player) -> float:
    queued = source.queued_duration
    source.clear_queue()
    player.rewind(round(queued * SAMPLE_RATE) * 2)
    return queued


async def publish_voice(ctx: JobContext) -> rtc.AudioSource:
    source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS, queue_size_ms=SOURCE_QUEUE_MS)
    track = rtc.LocalAudioTrack.create_audio_track("narrator-voice", source)
    await ctx.room.local_participant.publish_track(track)
    return source


def frame(pcm: bytes) -> rtc.AudioFrame:
    return rtc.AudioFrame(pcm, SAMPLE_RATE, NUM_CHANNELS, FRAME_SAMPLES)


async def fill(player: Player, chunks: AsyncIterator[bytes]) -> None:
    async for chunk in chunks:
        player.append(chunk)
    player.finish()


async def play(
    source: rtc.AudioSource, player: Player, playing: asyncio.Event, ramp: GainRamp
) -> None:
    while True:
        if not playing.is_set():
            if ramp.gain == 0.0:
                return
            if ramp.target != 0.0:
                ramp.set(0.0, PAUSE_FADE_SECONDS)
        pcm = player.read(FRAME_BYTES)
        if pcm is None:
            if player.finished:
                return
            await asyncio.sleep(CHUNK_SECONDS)
            continue
        await source.capture_frame(frame(scale(pcm, ramp.step(CHUNK_SECONDS))))


async def speak(source: rtc.AudioSource, chunks: AsyncIterator[bytes]) -> None:
    buffer = bytearray()
    async for chunk in chunks:
        buffer += chunk
        while len(buffer) >= FRAME_BYTES:
            pcm = bytes(buffer[:FRAME_BYTES])
            del buffer[:FRAME_BYTES]
            await source.capture_frame(frame(pcm))
