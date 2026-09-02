"""The job: one room, one listener, one story."""

import json
import logging

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentServer, JobContext

from narrator.story.content import load_story

load_dotenv()
logger = logging.getLogger("narrator")

server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    listener = await ctx.wait_for_participant()
    request = json.loads(listener.metadata)
    story = load_story(request["collection"], request["storyId"])

    logger.info(f"listener={listener.identity} story={story['title']!r}")


if __name__ == "__main__":
    agents.cli.run_app(server)
