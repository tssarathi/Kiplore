import asyncio
from typing import cast

import pytest
from livekit import rtc

import narrator.session
from narrator.audio import seconds_to_bytes
from narrator.envelope import GainRamp
from narrator.player import Player
from narrator.session import Phase, Session

DROP = rtc.DisconnectReason.SIGNAL_CLOSE
LEAVE = rtc.DisconnectReason.CLIENT_INITIATED


class FakeSource:
    def __init__(self, queued: float) -> None:
        self.queued_duration = queued

    def clear_queue(self) -> None:
        self.queued_duration = 0.0


def narrating(
    position: float, queued: float = 0.0
) -> tuple[Session, Player, asyncio.Event]:
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
    return session, player, paused


def test_a_removed_listener_ends_the_story_but_a_dropped_connection_holds_it():
    async def scenario() -> None:
        session, _, _ = narrating(7.0)
        session.dropped(rtc.DisconnectReason.PARTICIPANT_REMOVED)
        assert session.phase is Phase.LEFT

        session, _, _ = narrating(7.0)
        session.dropped(DROP)
        assert session.phase is Phase.HELD
        session.close()

    asyncio.run(scenario())


def test_a_leave_is_held_briefly_because_a_failed_resume_sends_one_too(monkeypatch):
    async def scenario() -> None:
        monkeypatch.setattr(narrator.session, "LEAVE_GRACE_SECONDS", 0.05)
        session, player, _ = narrating(7.0)
        session.dropped(LEAVE)
        assert session.phase is Phase.HELD, (
            "a leave that precedes a reconnect ended the story"
        )
        session.rejoined()
        assert session.report(1, 6.0, False) == 1
        assert session.phase is Phase.ACTIVE
        assert player.position == pytest.approx(6.0)
        session.close()

        session, _, _ = narrating(7.0)
        session.dropped(LEAVE)
        await asyncio.sleep(0.1)
        assert session.phase is Phase.LEFT, "a closed tab never ended the story"

    asyncio.run(scenario())


def test_a_repeated_position_report_is_acknowledged_but_applied_once():
    async def scenario() -> None:
        session, player, _ = narrating(7.0, queued=1.0)
        session.dropped(DROP)
        session.rejoined()

        assert session.report(1, 5.0, False) == 1
        assert session.phase is Phase.ACTIVE
        assert player.position == pytest.approx(5.0)

        assert session.report(1, 0.0, False) == 1
        assert player.position == pytest.approx(5.0)
        session.close()

    asyncio.run(scenario())


def test_a_report_ahead_of_what_was_sent_cannot_move_the_story_forward():
    async def scenario() -> None:
        session, player, _ = narrating(7.0)
        session.dropped(DROP)
        session.rejoined()
        assert session.report(1, 99.0, False) == 1
        assert player.position == pytest.approx(7.0)
        session.close()

        session, player, _ = narrating(7.0)
        session.dropped(DROP)
        session.rejoined()
        assert session.report(1, 99.0, True) == 1
        assert player.position == pytest.approx(7.0)
        session.close()

    asyncio.run(scenario())


def test_a_report_may_pause_the_story_but_never_start_it_again():
    async def scenario() -> None:
        session, _, paused = narrating(7.0)
        paused.clear()
        session.dropped(DROP)
        session.rejoined()

        assert session.report(1, 7.0, False) == 1
        assert not paused.is_set(), "a stale report restarted a paused story"
        session.close()

    asyncio.run(scenario())


def test_the_same_listener_rejoining_over_a_dead_socket_is_not_a_departure():
    async def scenario() -> None:
        session, _, _ = narrating(7.0)
        session.dropped(rtc.DisconnectReason.DUPLICATE_IDENTITY)

        assert session.phase is Phase.HELD
        session.close()

    asyncio.run(scenario())


def test_dropping_again_while_held_puts_the_hold_timer_back(monkeypatch):
    async def scenario() -> None:
        monkeypatch.setattr(narrator.session, "RECONNECT_GRACE_SECONDS", 0.01)
        session, _, _ = narrating(7.0)
        session.dropped(DROP)
        session.rejoined()
        session.dropped(DROP)
        await asyncio.sleep(0.05)

        assert session.phase is Phase.LEFT

    asyncio.run(scenario())


def test_a_report_arriving_after_the_story_carried_on_is_acknowledged_only(monkeypatch):
    async def scenario() -> None:
        monkeypatch.setattr(narrator.session, "RESUME_REPORT_SECONDS", 0.01)
        session, player, _ = narrating(7.0)
        session.dropped(DROP)
        session.rejoined()
        await asyncio.sleep(0.05)
        assert session.phase is Phase.ACTIVE

        assert session.report(1, 2.0, False) == 1
        assert player.position == pytest.approx(7.0)
        session.close()

    asyncio.run(scenario())


def test_a_departure_stops_an_answer_being_spoken():
    async def scenario() -> None:
        session, _, _ = narrating(7.0)
        spoke = session._spoke
        spoke.clear()
        session.dropped(rtc.DisconnectReason.PARTICIPANT_REMOVED)

        assert session.phase is Phase.LEFT
        assert spoke.is_set(), "the answer kept playing to an empty room"

    asyncio.run(scenario())
