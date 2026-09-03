"""Sliding the volume instead of jumping it."""

import array


class GainRamp:
    """A gain moving towards a target at a fixed rate."""

    def __init__(self) -> None:
        self.gain = 1.0
        self.target = 1.0
        self._rate = 0.0

    def snap(self, gain: float) -> None:
        """Jump to a volume, cancelling any slide."""
        self.gain = self.target = gain
        self._rate = 0.0

    def set(self, target: float, seconds: float) -> None:
        """Head for a target over `seconds`, from wherever the gain is now."""
        self.target = target
        self._rate = (target - self.gain) / seconds

    def step(self, seconds: float) -> float:
        """Advance one frame; stop on the first overshoot."""
        if self.gain != self.target:
            self.gain += self._rate * seconds
            # a frame rarely lands exactly on the target, in either direction
            if (self._rate > 0) == (self.gain > self.target):
                self.gain = self.target
        return self.gain


def scale(pcm: bytes, gain: float) -> bytes:
    """Multiply a frame by a gain; skip the work at full volume."""
    if gain > 0.999:
        return pcm
    samples = array.array("h", pcm)
    for i in range(len(samples)):
        samples[i] = int(samples[i] * gain)
    return samples.tobytes()
