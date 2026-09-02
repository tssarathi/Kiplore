import json
from pathlib import Path

from narrator.config import LIBRARY_DIR


def load_story(
    collection: str, story_id: str, library: Path = LIBRARY_DIR
) -> dict | None:
    path = library / collection / f"{story_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())
