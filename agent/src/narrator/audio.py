"""Sending sound into the room.

The one path from the player to the LiveKit track, so volume, pausing and interruption
all take effect in a single place.
"""

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
    """Seconds of audio as a byte count, at two bytes per sample."""
    return round(seconds * SAMPLE_RATE) * 2


def discard_queued(source: rtc.AudioSource, player: Player) -> float:
    """Drop audio queued but not yet heard, rewind to match, and return the seconds.

    Without the rewind, position would count audio the child never heard.
    """
    queued = source.queued_duration
    source.clear_queue()
    player.seek(-seconds_to_bytes(queued))
    return queued


async def publish_voice(ctx: JobContext) -> rtc.AudioSource:
    """Publish the narrator's track and return the source feeding it."""
    source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS, queue_size_ms=SOURCE_QUEUE_MS)
    track = rtc.LocalAudioTrack.create_audio_track("narrator-voice", source)
    # Published as a microphone because that is the source the client's voice assistant
    # hooks look for when picking out the agent's track.
    await ctx.room.local_participant.publish_track(
        track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    )
    return source


def frame(pcm: bytes) -> rtc.AudioFrame:
    """Wrap exactly one frame of PCM for LiveKit."""
    return rtc.AudioFrame(pcm, SAMPLE_RATE, NUM_CHANNELS, FRAME_SAMPLES)


async def once(pcm: bytes) -> AsyncIterator[bytes]:
    """Give a cached render the same shape as a live one, so playback is one path."""
    yield pcm


async def fill(player: Player, chunks: AsyncIterator[bytes]) -> None:
    """Drain a render into the player, so playback can start on the first chunk."""
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
    """Narrate until the story ends or the child interrupts.

    `paused` down means hold here; `playing` down means return and let the caller take
    the question. Both fade out first. `producer` is watched only so a failed render
    surfaces here instead of leaving playback waiting for audio that never comes.
    """
    while True:
        if not (playing.is_set() and paused.is_set()) and ramp.target != 0.0:
            ramp.set(0.0, PAUSE_FADE_SECONDS)
        if ramp.gain == 0.0:
            if not playing.is_set():
                return
            # Silent and staying, so this is a pause. Hand back the audio queued behind
            # the fade, or resuming would start after a gap the child never heard.
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
            # Caught up with a render still in flight: re-raise if it has since failed,
            # then idle one frame and look again.
            if producer.done():
                producer.result()
            ramp.step(CHUNK_SECONDS)
            await asyncio.sleep(CHUNK_SECONDS)
            continue
        # capture_frame returns only once LiveKit has room, which is what paces this
        # loop at real time rather than racing through the buffer.
        await source.capture_frame(frame(scale(pcm, ramp.step(CHUNK_SECONDS))))


async def speak_reply(
    source: rtc.AudioSource, chunks: AsyncIterator[bytes], spoke: asyncio.Event
) -> bool:
    """Speak an answer, giving way if the child talks again.

    Returns True only if it finished; False means they are still talking.
    """
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
    # Cleared twice: cancellation only lands at the next scheduling, so the task can
    # queue one more frame after the first clear.
    source.clear_queue()
    await asyncio.gather(speaking, return_exceptions=True)
    source.clear_queue()
    return False


async def speak(source: rtc.AudioSource, chunks: AsyncIterator[bytes]) -> None:
    """Send PCM into the room a whole frame at a time."""
    # Chunks arrive at arbitrary sizes; the remainder is carried over, never padded,
    # since padding would insert a click between chunks.
    buffer = bytearray()
    async for chunk in chunks:
        buffer += chunk
        while len(buffer) >= FRAME_BYTES:
            pcm = bytes(buffer[:FRAME_BYTES])
            del buffer[:FRAME_BYTES]
            await source.capture_frame(frame(pcm))
