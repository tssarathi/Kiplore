"""Story ids arrive in the join metadata, so they are not to be trusted with a path."""

import pytest

from narrator.content import load_story


@pytest.mark.parametrize(
    ("collection", "story_id"),
    [("aesop", "../../../etc/passwd"), ("../../..", "passwd")],
)
def test_a_path_outside_the_library_is_refused(collection: str, story_id: str):
    with pytest.raises(ValueError):
        load_story(collection, story_id)
