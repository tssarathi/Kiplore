"""Sending sound into the room."""

import asyncio
from collections.abc import AsyncIterator

from livekit import rtc
from livekit.agents import JobContext

from narrator.config import CHUNK_SECONDS, FRAME_SAMPLES, NUM_CHANNELS, SAMPLE_RATE
from narrator.player import Player

FRAME_BYTES = FRAME_SAMPLES * 2


async def publish_voice(ctx: JobContext) -> rtc.AudioSource:
    source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
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
    source: rtc.AudioSource, player: Player, playing: asyncio.Event
) -> None:
    while playing.is_set():
        pcm = player.read(FRAME_BYTES)
        if pcm is None:
            if player.finished:
                return
            await asyncio.sleep(CHUNK_SECONDS)
            continue
        await source.capture_frame(frame(pcm))


async def speak(source: rtc.AudioSource, chunks: AsyncIterator[bytes]) -> None:
    buffer = bytearray()
    async for chunk in chunks:
        buffer += chunk
        while len(buffer) >= FRAME_BYTES:
            pcm = bytes(buffer[:FRAME_BYTES])
            del buffer[:FRAME_BYTES]
            await source.capture_frame(frame(pcm))
