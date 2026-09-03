"""Writing the narrator's reply.

Called straight rather than through an SDK: one request, one message back, and the
constraints that matter live in the prompt rather than in code.
"""

import os

import aiohttp

from narrator.config import ANSWER_MODEL, ANSWER_PROMPT, RECENT_ANSWERS


async def write_answer(
    title: str, story_so_far: str, question: str, spoken: list[str]
) -> str:
    """One reply to the child, written from the story so far and nothing more."""
    # The narrator's own recent replies go back in so it does not open two answers the
    # same way in one story.
    recent = "\n".join(f"- {reply}" for reply in spoken[-RECENT_ANSWERS:])
    prompt = ANSWER_PROMPT.format(
        title=title, story_so_far=story_so_far, recent=recent or "- (nothing yet)"
    )
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            json={
                "model": ANSWER_MODEL,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": question},
                ],
            },
        ) as response:
            if response.status != 200:
                detail = (await response.content.read(200)).decode(errors="replace")
                raise RuntimeError(f"answer failed, HTTP {response.status}: {detail}")
            body = await response.json()
            return body["choices"][0]["message"]["content"].strip()
