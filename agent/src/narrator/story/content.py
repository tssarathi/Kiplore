import json

from narrator.config import LIBRARY_DIR


def load_story(collection: str, story_id: str) -> dict | None:
    path = LIBRARY_DIR / collection / f"{story_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())
