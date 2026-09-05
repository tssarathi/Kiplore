import asyncio
import math
from collections.abc import Callable
from enum import Enum

from livekit import rtc

from narrator.audio import seconds_to_bytes
from narrator.config import (
    LEAVE_GRACE_SECONDS,
    RECONNECT_GRACE_SECONDS,
    RESUME_REPORT_SECONDS,
)
from narrator.envelope import GainRamp
from narrator.observe import logger
from narrator.player import Player

CLEAN_LEAVES = frozenset(
    {
        rtc.DisconnectReason.PARTICIPANT_REMOVED,
        rtc.DisconnectReason.ROOM_DELETED,
        rtc.DisconnectReason.ROOM_CLOSED,
        rtc.DisconnectReason.SERVER_SHUTDOWN,
    }
)


class Phase(Enum):
    ACTIVE = "active"
    HELD = "held"
    LEFT = "left"


class Session:
    def __init__(
        self,
        source: rtc.AudioSource,
        player: Player,
        playing: asyncio.Event,
        paused: asyncio.Event,
        spoke: asyncio.Event,
        questions: asyncio.Queue[str | None],
        ramp: GainRamp,
    ) -> None:
        self.phase = Phase.ACTIVE
        self._source = source
        self._player = player
        self._playing = playing
        self._paused = paused
        self._spoke = spoke
        self._questions = questions
        self._ramp = ramp
        self._held = 0.0
        self._seq = 0
        self._resumed = False
        self._timer: asyncio.TimerHandle | None = None
        self._changed = asyncio.Event()

    async def ready(self) -> None:
        while self.phase is Phase.HELD:
            self._changed.clear()
            await self._changed.wait()

    def dropped(self, reason: rtc.DisconnectReason.ValueType | None) -> None:
        if self.phase is Phase.LEFT:
            return
        if reason in CLEAN_LEAVES:
            self.left()
            return
        grace = (
            LEAVE_GRACE_SECONDS
            if reason == rtc.DisconnectReason.CLIENT_INITIATED
            else RECONNECT_GRACE_SECONDS
        )
        if self.phase is Phase.HELD:
            self._arm(grace, self.left)
            return

        queued = self._source.queued_duration if self._playing.is_set() else 0.0
        self._playing.clear()
        self._spoke.set()
        self._source.clear_queue()
        self._player.seek(-seconds_to_bytes(queued))
        self._held = self._player.position
        self._resumed = False
        self._arm(grace, self.left)
        self._enter(Phase.HELD)
        self._wake()
        name = rtc.DisconnectReason.Name(reason) if reason is not None else "unknown"
        logger.info(
            f"listener dropped, holding {grace}s at {self._held:.1f} reason={name}"
        )

    def rejoined(self) -> None:
        if self.phase is not Phase.HELD:
            return
        self._arm(RESUME_REPORT_SECONDS, self._resume_unreported)
        logger.info("listener reconnected, awaiting position report")

    def report(self, seq: object, position: object, paused: object) -> int | None:
        if self.phase is Phase.LEFT:
            return None
        if not isinstance(seq, int) or isinstance(seq, bool) or seq <= 0:
            return None
        if not isinstance(position, (int, float)) or isinstance(position, bool):
            return None
        if not math.isfinite(position) or position < 0:
            return None
        if not isinstance(paused, bool):
            return None

        if seq <= self._seq:
            return seq
        if self._resumed:
            return seq
        self._seq = seq
        self._disarm()

        heard = self._player.position - self._source.queued_duration
        if position < heard or paused:
            self._source.clear_queue()
            target = min(position, heard)
            self._player.seek(seconds_to_bytes(target - self._player.position))
        if paused:
            self._paused.clear()
        if self._paused.is_set():
            self._ramp.resume()
        self._enter(Phase.ACTIVE)
        logger.info(f"resumed position={self._player.position:.1f} reason=report")
        return seq

    def left(self) -> None:
        if self.phase is Phase.LEFT:
            return
        self._disarm()
        self._playing.clear()
        self._spoke.set()
        self._enter(Phase.LEFT)
        self._wake()
        logger.info("listener gone")

    def close(self) -> None:
        self._disarm()

    def _resume_unreported(self) -> None:
        if self.phase is not Phase.HELD:
            return
        self._ramp.snap(1.0)
        self._resumed = True
        self._enter(Phase.ACTIVE)
        logger.info(f"resumed position={self._held:.1f} reason=no_report")

    def _enter(self, phase: Phase) -> None:
        self.phase = phase
        self._changed.set()

    def _wake(self) -> None:
        while not self._questions.empty():
            self._questions.get_nowait()
        self._questions.put_nowait(None)

    def _arm(self, seconds: float, expire: Callable[[], None]) -> None:
        self._disarm()
        self._timer = asyncio.get_running_loop().call_later(seconds, expire)

    def _disarm(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
