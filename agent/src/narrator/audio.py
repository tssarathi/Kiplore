"""The one path from stored audio into the room."""

import asyncio
from collections.abc import AsyncIterator

from livekit import rtc
from livekit.agents import JobContext

from narrator.config import (
    CHUNK_SECONDS,
    FRAME_SAMPLES,
    NUM_CHANNELS,
    PAUSE_FADE_SECONDS,
    RESUME_FADE_FROM,
    RESUME_FADE_SECONDS,
    SAMPLE_RATE,
    SOURCE_QUEUE_MS,
)
from narrator.envelope import GainRamp, scale
from narrator.player import Player

FRAME_BYTES = FRAME_SAMPLES * 2


def seconds_to_bytes(seconds: float) -> int:
    """Round to a whole sample, then double it: 16-bit is two bytes."""
    return round(seconds * SAMPLE_RATE) * 2


def discard_queued(source: rtc.AudioSource, player: Player) -> float:
    """Throw away unheard audio and rewind, so position is what was heard."""
    queued = source.queued_duration
    source.clear_queue()
    player.seek(-seconds_to_bytes(queued))
    return queued


async def publish_voice(ctx: JobContext) -> rtc.AudioSource:
    """Make the source and publish it as a microphone track."""
    source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS, queue_size_ms=SOURCE_QUEUE_MS)
    track = rtc.LocalAudioTrack.create_audio_track("narrator-voice", source)
    # a microphone, because that is the source the client's assistant hooks look for
    await ctx.room.local_participant.publish_track(
        track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    )
    return source


def frame(pcm: bytes) -> rtc.AudioFrame:
    """Assert 22,050 Hz mono over 882 anonymous bytes."""
    return rtc.AudioFrame(pcm, SAMPLE_RATE, NUM_CHANNELS, FRAME_SAMPLES)


async def once(pcm: bytes) -> AsyncIterator[bytes]:
    """Make a cached blob look like a stream, so there is one code path."""
    yield pcm


async def fill(player: Player, chunks: AsyncIterator[bytes]) -> None:
    """Drain the render into the player; mark it finished."""
    async for chunk in chunks:
        player.append(chunk)
    player.finish()


async def play(
    source: rtc.AudioSource,
    player: Player,
    playing: asyncio.Event,
    paused: asyncio.Event,
    ramp: GainRamp,
    producer: asyncio.Task[None],
) -> None:
    """The narration loop: fade, pause, read, send at real time."""
    while True:
        # paused holds the loop, playing cleared returns so the caller can answer
        if not (playing.is_set() and paused.is_set()) and ramp.target != 0.0:
            ramp.set(0.0, PAUSE_FADE_SECONDS)
        if ramp.gain == 0.0:
            if not playing.is_set():
                return

            # drop audio queued behind the fade, or resume starts after a gap
            discard_queued(source, player)
            while not paused.is_set() and playing.is_set():
                await asyncio.sleep(CHUNK_SECONDS)
            if not playing.is_set():
                return
            ramp.snap(RESUME_FADE_FROM)
            ramp.set(1.0, RESUME_FADE_SECONDS)
        pcm = player.read(FRAME_BYTES)
        if pcm is None:
            if player.finished:
                return

            # caught up with a render still in flight; re-raise if it has since failed
            if producer.done():
                producer.result()
            ramp.step(CHUNK_SECONDS)
            await asyncio.sleep(CHUNK_SECONDS)
            continue

        # capture_frame returns when LiveKit has room, which paces this at real time
        await source.capture_frame(frame(scale(pcm, ramp.step(CHUNK_SECONDS))))


async def speak_reply(
    source: rtc.AudioSource, chunks: AsyncIterator[bytes], spoke: asyncio.Event
) -> bool:
    """Speak an answer; give way if the child talks again."""
    spoke.clear()
    speaking = asyncio.create_task(speak(source, chunks))
    interrupt = asyncio.create_task(spoke.wait())
    done, _ = await asyncio.wait(
        {speaking, interrupt}, return_when=asyncio.FIRST_COMPLETED
    )
    if speaking in done:
        interrupt.cancel()
        await speaking  # awaited so a synthesis failure is raised, not swallowed
        return True
    speaking.cancel()
    # the queue is cleared twice: cancellation lands at the next scheduling
    source.clear_queue()
    await asyncio.gather(speaking, return_exceptions=True)
    source.clear_queue()
    return False


async def speak(source: rtc.AudioSource, chunks: AsyncIterator[bytes]) -> None:
    """Send arbitrary PCM as whole frames; carry the remainder."""
    # carried, never padded, since padding would click between chunks
    buffer = bytearray()
    async for chunk in chunks:
        buffer += chunk
        while len(buffer) >= FRAME_BYTES:
            pcm = bytes(buffer[:FRAME_BYTES])
            del buffer[:FRAME_BYTES]
            await source.capture_frame(frame(pcm))
