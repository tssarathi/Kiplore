import asyncio
import contextlib
import itertools
import json
import math
import time
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentServer, JobContext
from livekit.agents.types import (
    ATTRIBUTE_AGENT_STATE,
    ATTRIBUTE_TRANSCRIPTION_FINAL,
    ATTRIBUTE_TRANSCRIPTION_SEGMENT_ID,
    TOPIC_TRANSCRIPTION,
)
from livekit.agents.utils import shortuuid

from narrator import cache, observe
from narrator.alignment import (
    Timings,
    chunk_start,
    heard_text,
    segment_at,
    spoken_text,
)
from narrator.answer import shape, write_answer
from narrator.audio import (
    discard_queued,
    once,
    play,
    publish_voice,
    seconds_to_bytes,
    speak_reply,
)
from narrator.config import (
    ANSWER_FALLBACK,
    CLARIFY_WAIT_SECONDS,
    RESUME_BREATH_SECONDS,
)
from narrator.content import load_story, load_voice
from narrator.envelope import GainRamp
from narrator.listen import Listener
from narrator.observe import logger
from narrator.player import Player
from narrator.render import Narration, stream_answer
from narrator.session import Phase, Session

load_dotenv()

server = AgentServer(num_idle_processes=1)


ACTIONS = frozenset({"pause", "resume", "seek", "resume-at"})


def control(payload: bytes) -> dict | None:
    try:
        message = json.loads(payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(message, dict) or message.get("action") not in ACTIONS:
        return None
    if message["action"] == "seek":
        offset = message.get("offset")
        if not isinstance(offset, (int, float)) or isinstance(offset, bool):
            return None
        if not math.isfinite(offset):
            return None
    return message


def sentence_at(timings: Timings, position: float) -> dict | None:
    segment = segment_at(timings.segments, position)
    if segment is not None and position >= segment["end"]:
        return None
    return segment


async def broadcast(
    ctx: JobContext, player: Player, timings: Timings, paused: asyncio.Event
) -> None:
    for seq in itertools.count(1):
        segment = sentence_at(timings, player.position)
        payload = json.dumps(
            {
                "seq": seq,
                "position": round(player.position, 1),
                "duration": round(timings.chunk_timings[-1], 1)
                if timings.chunk_timings
                else 0.0,
                "paused": not paused.is_set(),
                "caption": segment["text"] if segment is not None else None,
            }
        )
        try:
            await ctx.room.local_participant.publish_data(payload, reliable=False)
        except Exception:
            logger.warning("state broadcast failed")
        await asyncio.sleep(1)


async def announce(ctx: JobContext, state: str) -> None:
    try:
        await ctx.room.local_participant.set_attributes({ATTRIBUTE_AGENT_STATE: state})
    except Exception:
        logger.warning(f"could not announce {state}")


def drop_stale(questions: asyncio.Queue[str | None]) -> int:
    dropped, ended = 0, False
    while not questions.empty():
        if questions.get_nowait() is None:
            ended = True
        else:
            dropped += 1
    if ended:
        questions.put_nowait(None)
    return dropped


async def next_question(
    questions: asyncio.Queue[str | None], within: float
) -> str | None:
    try:
        return await asyncio.wait_for(questions.get(), within)
    except TimeoutError:
        return ""


async def caption(ctx: JobContext, text: str) -> None:
    try:
        writer = await ctx.room.local_participant.stream_text(
            topic=TOPIC_TRANSCRIPTION,
            attributes={
                ATTRIBUTE_TRANSCRIPTION_SEGMENT_ID: shortuuid("SG_"),
                ATTRIBUTE_TRANSCRIPTION_FINAL: "true",
            },
        )
        await writer.write(text)
        await writer.aclose()
    except Exception:
        logger.warning("could not caption the answer")


async def fill(player: Player, chunks: AsyncIterator[bytes], started: float) -> None:
    first = True
    async for chunk in chunks:
        if first:
            observe.event("first audio", seconds=observe.since(started))
            first = False
        player.append(chunk)
    player.finished = True


def resume_point(timings: Timings, position: float) -> float:
    segment = segment_at(timings.segments, position)
    if segment is not None:
        return segment["start"] if position < segment["end"] else segment["end"]
    return chunk_start(timings.chunk_timings, position)


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    started = time.monotonic()
    answers = 0

    playing = asyncio.Event()
    paused = asyncio.Event()
    paused.set()
    spoke = asyncio.Event()
    questions: asyncio.Queue[str | None] = asyncio.Queue()
    player = Player()
    ramp = GainRamp()
    acks: set[asyncio.Task[None]] = set()
    spoken: list[str] = []

    observe.setup()
    observe.session.set(ctx.job.room.name)

    await ctx.connect()
    source = await publish_voice(ctx)
    session = Session(source, player, playing, paused, spoke, questions, ramp)

    def publish_ack(seq: int) -> None:
        payload = json.dumps({"type": "resume-ack", "seq": seq})
        task = asyncio.create_task(
            ctx.room.local_participant.publish_data(payload, reliable=True)
        )
        acks.add(task)
        task.add_done_callback(acks.discard)

    @ctx.room.on("data_received")
    def on_control(packet: rtc.DataPacket) -> None:
        message = control(packet.data)
        if message is None:
            logger.warning("control packet refused")
            return
        logger.info(f"control {message}")
        action = message["action"]
        if action == "resume-at":
            seq = session.report(
                message.get("seq"), message.get("position"), message.get("paused")
            )
            if seq is not None:
                publish_ack(seq)
            return
        if session.phase is not Phase.ACTIVE:
            return
        if action == "pause":
            paused.clear()
        elif action == "resume":
            paused.set()
        elif action == "seek":
            discard_queued(source, player)
            player.seek(seconds_to_bytes(message["offset"]))

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
        session.dropped(participant.disconnect_reason)

    @ctx.room.on("participant_connected")
    def on_participant_connected(_: rtc.RemoteParticipant) -> None:
        session.rejoined()

    listener = await ctx.wait_for_participant()
    request = json.loads(listener.metadata)
    story = load_story(request["collection"], request["storyId"])
    voice = load_voice(request["voiceId"])

    logger.info(
        f"listener={listener.identity} story={story['title']!r} voice={voice['name']}"
    )

    render = cache.render_id(story, voice["elevenLabsId"])
    at = cache.prefix(
        request["collection"], request["storyId"], request["voiceId"], render
    )
    cached = await cache.load(at)
    if cached is None:
        narration = Narration(story, voice["elevenLabsId"])
        timings, chunks = narration.timings, narration.stream()
        logger.info(f"narrating live at={at}")
    else:
        pcm, timings = cached
        chunks = once(pcm)
        logger.info(f"narrating from cache at={at}")

    ears = Listener(
        story["script"],
        ctx.room,
        listener.identity,
        playing,
        paused,
        spoke,
        questions,
        ramp,
    )
    ctx.room.on("track_subscribed", lambda track, *_: ears.add_microphone(track))
    for publication in listener.track_publications.values():
        if publication.track is not None:
            ears.add_microphone(publication.track)

    producer = asyncio.create_task(fill(player, chunks, started))
    broadcaster = asyncio.create_task(broadcast(ctx, player, timings, paused))

    try:
        while True:
            await session.ready()
            if session.phase is Phase.LEFT:
                break
            stale = drop_stale(questions)
            if stale:
                logger.info(f"dropped {stale} question(s) said before this turn")
            playing.set()
            await announce(ctx, "speaking")
            await play(source, player, playing, paused, ramp, producer)
            if playing.is_set():
                break
            logger.info(
                f"rewound {discard_queued(source, player):.2f}s of queued audio"
            )
            await announce(ctx, "listening")

            carried: dict | None = None
            while question := await next_question(questions, CLARIFY_WAIT_SECONDS):
                asked = time.monotonic()
                heard = heard_text(
                    story["script"],
                    timings.segments,
                    timings.chunk_timings,
                    player.position,
                )
                await announce(ctx, "thinking")
                try:
                    answer = shape(
                        await write_answer(story["title"], heard, question, spoken)
                    )
                except Exception:
                    logger.exception("answer failed")
                    answer = ANSWER_FALLBACK
                answers += 1
                spoken.append(answer)
                logger.info(f"answering {answer!r}")
                asked_again = answer.rstrip().endswith("?")
                carried = None if asked_again else sentence_at(timings, player.position)
                said = f"{answer} {carried['text']}" if carried else answer
                await caption(ctx, said)
                await announce(ctx, "speaking")
                observe.event("answered", seconds=observe.since(asked))
                try:
                    replied = await speak_reply(
                        source, stream_answer(said, voice["elevenLabsId"]), spoke
                    )
                except Exception:
                    logger.exception("answer synthesis failed")
                    carried = None
                    break
                if not replied:
                    carried = None
                    logger.info("answer interrupted")
                    await announce(ctx, "listening")
                    continue
                if not asked_again:
                    break
                logger.info("asked again, waiting for the child")
                await announce(ctx, "listening")
            if question is None:
                continue

            await asyncio.sleep(RESUME_BREATH_SECONDS)
            target = (
                carried["end"] if carried else resume_point(timings, player.position)
            )
            player.seek(seconds_to_bytes(target - player.position))
            ramp.resume()

        if session.phase is not Phase.LEFT:
            await producer
            logger.info("story finished")
    finally:
        session.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(source.wait_for_playout(), 2.0)
        complete = producer.done() and not producer.cancelled()
        failure = producer.exception() if complete else None
        producer.cancel()
        broadcaster.cancel()
        await ears.aclose()
        await asyncio.gather(producer, broadcaster, return_exceptions=True)
        await ctx.delete_room()
        if cached is None:
            if not complete:
                logger.info(f"render unfinished, not cached at={at}")
            elif failure is not None:
                logger.warning(f"render failed at={at} reason={failure!r}")
            else:
                reason = await cache.save(
                    at, player.audio, timings, spoken_text(story["script"])
                )
                if reason is None:
                    logger.info(f"render cached at={at}")
                else:
                    logger.warning(f"render not cached at={at} reason={reason}")
        observe.event(
            "session complete",
            seconds=observe.since(started),
            position=round(player.position, 1),
            answers=answers,
            cached=cached is not None,
        )


if __name__ == "__main__":
    agents.cli.run_app(server)
