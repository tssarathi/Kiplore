"""Hearing the child: energy for ducking, Flux for turns.

Two paths out of the same microphone frames. Raw energy ducks the narration in
milliseconds, before anyone knows what was said; Deepgram turns the frames into the
words that become questions.
"""

import array
import asyncio
import logging
import math
import time

from livekit import rtc
from livekit.agents.stt import SpeechEventType
from livekit.agents.types import (
    ATTRIBUTE_TRANSCRIPTION_FINAL,
    ATTRIBUTE_TRANSCRIPTION_SEGMENT_ID,
    TOPIC_TRANSCRIPTION,
)
from livekit.agents.utils import shortuuid
from livekit.plugins import deepgram, noise_cancellation

from narrator import observe
from narrator.alignment import keyterms
from narrator.config import (
    DUCK_ATTACK_SECONDS,
    DUCK_DECAY_SECONDS,
    DUCK_FRAMES,
    DUCK_RELEASE_SECONDS,
    DUCK_RMS,
    DUCK_VOLUME,
    EOT_THRESHOLD,
)
from narrator.envelope import GainRamp

logger = logging.getLogger("narrator")

MIC_FRAME_CAPACITY = 100  # frames buffered per track before old ones are dropped


class Listener:
    """The child's microphone: ducks the narration, and turns speech into questions."""

    def __init__(
        self,
        script: list[str],
        room: rtc.Room,
        identity: str,
        playing: asyncio.Event,
        spoke: asyncio.Event,
        questions: asyncio.Queue[str | None],
        ramp: GainRamp,
    ) -> None:
        self._stt = deepgram.STTv2(
            keyterm=keyterms(script), eot_threshold=EOT_THRESHOLD
        )
        self._stream = self._stt.stream()
        self._room = room
        self._identity = identity
        self._playing = playing
        self._spoke = spoke
        self._questions = questions
        self._ramp = ramp
        self._loud = 0
        self._quiet = 0.0
        self._ducked_at = 0.0
        self._ducked = False
        self._segment = shortuuid("SG_")
        self._captions: asyncio.Queue[tuple[str, str, bool]] = asyncio.Queue()
        self._tasks: list[asyncio.Task[None]] = [
            asyncio.create_task(self._read()),
            asyncio.create_task(self._publish()),
        ]

    def add_microphone(self, track: rtc.Track) -> None:
        """Start forwarding a newly subscribed microphone track."""
        self._tasks.append(asyncio.create_task(self._forward(track)))

    async def aclose(self) -> None:
        """Stop every task and close the transcriber."""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._stream.aclose()
        await self._stt.aclose()

    async def _forward(self, track: rtc.Track) -> None:
        """Pipe one track into the energy gate and the transcriber."""
        # Room noise is removed once, before either path sees the frame.
        stream = rtc.AudioStream(
            track,
            capacity=MIC_FRAME_CAPACITY,
            noise_cancellation=noise_cancellation.NC(),
        )
        try:
            async for event in stream:
                self._gate(event.frame)
                self._stream.push_frame(event.frame)
        finally:
            await stream.aclose()

    def _gate(self, frame: rtc.AudioFrame) -> None:
        """Duck while the room is loud, restore once it has been quiet a while."""
        samples = array.array("h", bytes(frame.data))
        if not samples:
            return
        # RMS as a fraction of full scale, so the threshold does not depend on volume
        # levels elsewhere. Ducking needs several loud frames, unducking needs a stretch
        # of quiet: without that hysteresis the narration would flutter.
        rms = math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768
        seconds = len(samples) / frame.sample_rate / frame.num_channels
        if rms >= DUCK_RMS:
            self._loud += 1
            self._quiet = 0.0
            if self._loud >= DUCK_FRAMES and not self._ducked:
                self._ducked = True
                self._ducked_at = time.monotonic()
                self._ramp.set(DUCK_VOLUME, DUCK_ATTACK_SECONDS)
        else:
            self._loud = 0
            self._quiet += seconds
            if self._ducked and self._quiet >= DUCK_RELEASE_SECONDS:
                self._unduck()

    def _unduck(self) -> None:
        """Bring the narration back, unless it has already stopped for a question."""
        if self._ducked:
            self._ducked = False
            if self._playing.is_set():
                self._ramp.set(1.0, DUCK_DECAY_SECONDS)

    async def _publish(self) -> None:
        """Write captions into the room one at a time.

        Separate from the read loop so a slow network write cannot stall transcription.
        """
        while True:
            segment, text, final = await self._captions.get()
            try:
                writer = await self._room.local_participant.stream_text(
                    topic=TOPIC_TRANSCRIPTION,
                    sender_identity=self._identity,
                    attributes={
                        ATTRIBUTE_TRANSCRIPTION_SEGMENT_ID: segment,
                        ATTRIBUTE_TRANSCRIPTION_FINAL: "true" if final else "false",
                    },
                )
                await writer.write(text)
                await writer.aclose()
            except Exception:
                logger.exception("caption publish failed")

    async def _read(self) -> None:
        """Turn transcription events into ducking, captions and questions."""
        try:
            async for event in self._stream:
                if event.type == SpeechEventType.END_OF_SPEECH:
                    self._unduck()
                    continue
                if not event.alternatives or not event.alternatives[0].text:
                    continue
                text = event.alternatives[0].text
                # An interim transcript is the earliest trustworthy sign the child is
                # really speaking, so narration stops here rather than on the final one.
                if event.type == SpeechEventType.INTERIM_TRANSCRIPT:
                    self._captions.put_nowait((self._segment, text, False))
                    self._spoke.set()
                    if self._playing.is_set():
                        self._playing.clear()
                        # First loud frame to the narration stopping: the number that
                        # decides whether interrupting feels natural or rude.
                        # `event` is the loop variable here, so the module is called
                        # by name rather than imported into the same scope.
                        observe.event(
                            logger,
                            "narration stopped",
                            seconds=observe.since(self._ducked_at)
                            if self._ducked_at
                            else None,
                        )
                elif event.type == SpeechEventType.FINAL_TRANSCRIPT:
                    logger.info(f"heard {text!r}")
                    self._captions.put_nowait((self._segment, text, True))
                    self._segment = shortuuid("SG_")
                    self._questions.put_nowait(text)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("transcription failed")
            self._unduck()
            # An empty question unblocks the story loop, so a dead transcriber ends in
            # the story carrying on rather than in silence.
            self._questions.put_nowait("")
