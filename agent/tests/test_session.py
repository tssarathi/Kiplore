"""The reconnect path, driven without a network: a client the agent cannot trust."""

import asyncio
from typing import cast

import pytest
from livekit import rtc

from narrator.audio import seconds_to_bytes
from narrator.envelope import GainRamp
from narrator.player import Player
from narrator.session import Phase, Session

DROP = rtc.DisconnectReason.SIGNAL_CLOSE
LEAVE = rtc.DisconnectReason.CLIENT_INITIATED


class FakeSource:
    """queued_duration and clear_queue, all Session asks of a real source."""

    def __init__(self, queued: float) -> None:
        self.queued_duration = queued

    def clear_queue(self) -> None:
        self.queued_duration = 0.0


def narrating(position: float, queued: float = 0.0) -> tuple[Session, Player]:
    player = Player()
    player.append(bytes(seconds_to_bytes(60.0)))
    player.seek(seconds_to_bytes(position))
    playing, paused = asyncio.Event(), asyncio.Event()
    playing.set()
    paused.set()
    session = Session(
        cast(rtc.AudioSource, FakeSource(queued)),
        player,
        playing,
        paused,
        asyncio.Event(),
        asyncio.Queue(),
        GainRamp(),
    )
    return session, player


def test_a_closed_tab_ends_the_story_but_a_dropped_connection_holds_it():
    async def scenario() -> None:
        session, _ = narrating(7.0)
        session.dropped(LEAVE)
        assert session.phase is Phase.LEFT

        session, _ = narrating(7.0)
        session.dropped(DROP)
        assert session.phase is Phase.HELD
        session.close()

    asyncio.run(scenario())


def test_a_repeated_position_report_is_acknowledged_but_applied_once():
    async def scenario() -> None:
        session, player = narrating(7.0, queued=1.0)
        session.dropped(DROP)
        session.rejoined()

        assert session.report(1, 5.0, False) == 1
        assert session.phase is Phase.ACTIVE
        assert player.position == pytest.approx(5.0)

        # the client retries until acknowledged, so this arrives twice
        assert session.report(1, 0.0, False) == 1
        assert player.position == pytest.approx(5.0)
        session.close()

    asyncio.run(scenario())


def test_a_report_ahead_of_what_was_sent_cannot_move_the_story_forward():
    async def scenario() -> None:
        # still playing, so a claim beyond what was sent is ignored outright
        session, player = narrating(7.0)
        session.dropped(DROP)
        session.rejoined()
        assert session.report(1, 99.0, False) == 1
        assert player.position == pytest.approx(7.0)
        session.close()

        # paused, so the claim is acted on, but clamped to what was sent
        session, player = narrating(7.0)
        session.dropped(DROP)
        session.rejoined()
        assert session.report(1, 99.0, True) == 1
        assert player.position == pytest.approx(7.0)
        session.close()

    asyncio.run(scenario())
