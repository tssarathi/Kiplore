"""The tape: written at one end, read at the other."""

from narrator.config import SAMPLE_RATE


class Player:
    """The story rendered so far, and how much of it has been played."""

    def __init__(self) -> None:
        # nothing is ever thrown away, which is what makes seeking back possible
        self._buffer = bytearray()
        self._cursor = 0
        self.finished = False

    @property
    def audio(self) -> bytes:
        return bytes(self._buffer)

    @property
    def position(self) -> float:
        """The one place bytes become seconds."""
        return self._cursor / 2 / SAMPLE_RATE

    def append(self, pcm: bytes) -> None:
        """Add rendered audio to the end. Never touches the cursor."""
        self._buffer += pcm

    def finish(self) -> None:
        """Mark the render complete."""
        self.finished = True

    def seek(self, size: int) -> None:
        """Move the cursor relatively, clamped to the buffer."""
        self._cursor = min(max(0, self._cursor + size), len(self._buffer))

    def read(self, size: int) -> bytes | None:
        """The next `size` bytes, or None meaning not ready yet."""
        if len(self._buffer) - self._cursor < size:
            return None
        chunk = bytes(self._buffer[self._cursor : self._cursor + size])
        self._cursor += size
        return chunk
