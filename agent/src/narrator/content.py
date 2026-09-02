import json

from narrator.config import LIBRARY_DIR


def load_story(collection: str, story_id: str) -> dict:
    return json.loads((LIBRARY_DIR / collection / f"{story_id}.json").read_text())
