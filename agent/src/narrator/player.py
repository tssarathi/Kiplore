"""A recording being written at one end and read at the other."""


class Player:
    def __init__(self) -> None:
        self._buffer = bytearray()
        self._cursor = 0
        self.finished = False

    def append(self, pcm: bytes) -> None:
        self._buffer += pcm

    def finish(self) -> None:
        self.finished = True

    def rewind(self, size: int) -> None:
        self._cursor = max(0, self._cursor - size)

    def read(self, size: int) -> bytes | None:
        if len(self._buffer) - self._cursor < size:
            return None
        chunk = bytes(self._buffer[self._cursor : self._cursor + size])
        self._cursor += size
        return chunk
