"""The loop. Connect, load, narrate, take a question, resume."""

import asyncio
import itertools
import json
import logging
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
    fill,
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
    RESUME_FADE_FROM,
    RESUME_FADE_SECONDS,
)
from narrator.content import load_story, load_voice
from narrator.envelope import GainRamp
from narrator.listen import Listener
from narrator.player import Player
from narrator.render import Narration, stream_answer
from narrator.session import Phase, Session

load_dotenv()
logger = logging.getLogger("narrator")

server = AgentServer(num_idle_processes=1)


async def broadcast(
    ctx: JobContext, player: Player, timings: Timings, paused: asyncio.Event
) -> None:
    """Position, duration, paused and caption, once a second, unreliably."""
    for seq in itertools.count(1):
        # past a sentence's end is the silence before the next, so show no caption
        segment = segment_at(timings.segments, player.position)
        if segment is not None and player.position >= segment["end"]:
            segment = None
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
        await ctx.room.local_participant.publish_data(payload, reliable=False)
        await asyncio.sleep(1)


async def announce(ctx: JobContext, state: str) -> None:
    """Agent state as a room attribute, so the client can animate on it."""
    await ctx.room.local_participant.set_attributes({ATTRIBUTE_AGENT_STATE: state})


async def next_question(
    questions: asyncio.Queue[str | None], within: float | None
) -> str | None:
    """The next thing the child says, or "" after `within` seconds of silence."""
    if within is None:
        return await questions.get()
    try:
        return await asyncio.wait_for(questions.get(), within)
    except TimeoutError:
        return ""


async def caption(ctx: JobContext, text: str) -> None:
    """One line of the narrator's own speech on the transcription topic."""
    writer = await ctx.room.local_participant.stream_text(
        topic=TOPIC_TRANSCRIPTION,
        attributes={
            ATTRIBUTE_TRANSCRIPTION_SEGMENT_ID: shortuuid("SG_"),
            ATTRIBUTE_TRANSCRIPTION_FINAL: "true",
        },
    )
    await writer.write(text)
    await writer.aclose()


async def timed(chunks: AsyncIterator[bytes], started: float) -> AsyncIterator[bytes]:
    """Wrap the render iterator to log time to first audio."""
    first = True
    async for chunk in chunks:
        if first:
            observe.event(logger, "first audio", seconds=observe.since(started))
            first = False
        yield chunk


def resume_point(timings: Timings, position: float) -> float:
    """The interrupted sentence, or failing that its chunk."""
    segment = segment_at(timings.segments, position)
    if segment is not None:
        return segment["start"]
    return chunk_start(timings.chunk_timings, position)


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """One room, one child, one story, from connection to teardown."""
    started = time.monotonic()
    answers = 0

    # both are cleared to stop: playing by an interruption, paused by the button
    playing = asyncio.Event()
    paused = asyncio.Event()
    paused.set()
    spoke = asyncio.Event()
    questions: asyncio.Queue[str | None] = asyncio.Queue()
    player = Player()
    ramp = GainRamp()
    acks: set[asyncio.Task[None]] = set()
    spoken: list[str] = []

    await ctx.connect()

    # logging is set up after connect: the room name is the only session id yet
    observe.setup()
    observe.session.set(ctx.room.name)
    source = await publish_voice(ctx)
    session = Session(source, player, playing, paused, spoke, questions, ramp)

    # sent reliably, because the client retries the report until it hears back
    def publish_ack(seq: int) -> None:
        payload = json.dumps({"type": "resume-ack", "seq": seq})
        task = asyncio.create_task(
            ctx.room.local_participant.publish_data(payload, reliable=True)
        )
        acks.add(task)  # a reference, or the task is collected mid-flight
        task.add_done_callback(acks.discard)

    @ctx.room.on("data_received")
    def on_control(packet: rtc.DataPacket) -> None:
        control = json.loads(packet.data)
        logger.info(f"control {control}")
        action = control["action"]
        # resume-at is taken in any phase; pause, resume and seek need a live story
        if action == "resume-at":
            seq = session.report(control["seq"], control["position"], control["paused"])
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
            player.seek(seconds_to_bytes(control["offset"]))

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
        session.dropped(participant.disconnect_reason)

    @ctx.room.on("participant_connected")
    def on_participant_connected(_: rtc.RemoteParticipant) -> None:
        session.rejoined()

    # the join token's metadata is how the agent learns which story and which voice
    listener = await ctx.wait_for_participant()
    request = json.loads(listener.metadata)
    story = load_story(request["collection"], request["storyId"])
    voice = load_voice(request["voiceId"])

    logger.info(
        f"listener={listener.identity} story={story['title']!r} voice={voice['name']}"
    )

    ears = Listener(
        story["script"], ctx.room, listener.identity, playing, spoke, questions, ramp
    )
    # a microphone published before now never fires the event, so take both kinds
    ctx.room.on("track_subscribed", lambda track, *_: ears.add_microphone(track))
    for publication in listener.track_publications.values():
        if publication.track is not None:
            ears.add_microphone(publication.track)

    # cache or synthesise; a hit brings its timings, so both look alike from here
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

    # render, report and play at once, so the story starts on the first chunk
    producer = asyncio.create_task(fill(player, timed(chunks, started)))
    broadcaster = asyncio.create_task(broadcast(ctx, player, timings, paused))

    try:
        while True:
            # blocks here while a dropped listener is being waited out
            await session.ready()
            if session.phase is Phase.LEFT:
                break
            playing.set()
            await announce(ctx, "speaking")
            await play(source, player, playing, paused, ramp, producer)
            # play only returns with `playing` still set when the story ran out
            if playing.is_set():
                break
            logger.info(
                f"rewound {discard_queued(source, player):.2f}s of queued audio"
            )
            await announce(ctx, "listening")

            # one question and answer, repeating only while asking them to clarify
            waiting: float | None = None
            carried: dict | None = None
            while question := await next_question(questions, waiting):
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
                    # a child who just spoke must hear something, or it reads broken
                    logger.exception("answer failed")
                    answer = ANSWER_FALLBACK
                answers += 1
                spoken.append(answer)
                logger.info(f"answering {answer!r}")
                # a reply ending in "?" is asking the child again, so it waits here
                asked_again = answer.rstrip().endswith("?")
                # otherwise the interrupted sentence follows, spoken again in full
                carried = (
                    None
                    if asked_again
                    else segment_at(timings.segments, player.position)
                )
                said = f"{answer} {carried['text']}" if carried else answer
                await caption(ctx, said)
                await announce(ctx, "speaking")
                observe.event(logger, "answered", seconds=observe.since(asked))
                replied = await speak_reply(
                    source, stream_answer(said, voice["elevenLabsId"]), spoke
                )
                # cut short means they are still talking, so hear them out first
                if not replied:
                    carried = None
                    logger.info("answer interrupted")
                    await announce(ctx, "listening")
                    waiting = None
                    continue
                if not asked_again:
                    break
                logger.info("asked again, waiting for the child")
                await announce(ctx, "listening")
                waiting = CLARIFY_WAIT_SECONDS
            # None is the wake-up from a drop or a departure, not something asked
            if question is None:
                continue

            # a breath, then past the sentence just re-spoken, or back to the cut
            await asyncio.sleep(RESUME_BREATH_SECONDS)
            target = (
                carried["end"] if carried else resume_point(timings, player.position)
            )
            player.seek(seconds_to_bytes(target - player.position))
            ramp.snap(RESUME_FADE_FROM)
            ramp.set(1.0, RESUME_FADE_SECONDS)

        if session.phase is not Phase.LEFT:
            await producer
            logger.info("story finished")
    finally:
        # read before cancelling; afterwards finished and torn-down look alike
        session.close()
        complete = producer.done() and not producer.cancelled()
        failure = producer.exception() if complete else None
        producer.cancel()
        broadcaster.cancel()
        await ears.aclose()
        await asyncio.gather(producer, broadcaster, return_exceptions=True)
        await ctx.delete_room()
        # only a completed render, and only one rendered here, is worth storing
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
            logger,
            "session complete",
            seconds=observe.since(started),
            position=round(player.position, 1),
            answers=answers,
            cached=cached is not None,
        )


if __name__ == "__main__":
    agents.cli.run_app(server)
