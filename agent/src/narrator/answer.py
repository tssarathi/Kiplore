"""Writing the narrator's reply."""

import os

import aiohttp

from narrator.config import ANSWER_MODEL, ANSWER_PROMPT, RECENT_ANSWERS


async def write_answer(
    title: str, story_so_far: str, question: str, spoken: list[str]
) -> str:
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
