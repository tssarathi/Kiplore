"""A recording being written at one end and read at the other.

Nothing is discarded once played, which is what makes seeking back, resuming after an
interruption, and caching the finished render possible.
"""

from narrator.config import SAMPLE_RATE


class Player:
    """The story rendered so far, and how much of it has been played."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._cursor = 0
        self.finished = False

    @property
    def audio(self) -> bytes:
        return bytes(self._buffer)

    @property
    def position(self) -> float:
        """Seconds played. The one place byte offsets are converted to time."""
        return self._cursor / 2 / SAMPLE_RATE

    def append(self, pcm: bytes) -> None:
        self._buffer += pcm

    def finish(self) -> None:
        self.finished = True

    def seek(self, size: int) -> None:
        """Move the cursor `size` bytes, clamped so it cannot run past the render."""
        self._cursor = min(max(0, self._cursor + size), len(self._buffer))

    def read(self, size: int) -> bytes | None:
        """The next `size` bytes, or None if that much has not rendered yet.

        None means not ready, never finished; callers check `finished` for that.
        """
        if len(self._buffer) - self._cursor < size:
            return None
        chunk = bytes(self._buffer[self._cursor : self._cursor + size])
        self._cursor += size
        return chunk
