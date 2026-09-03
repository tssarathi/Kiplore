"""Sliding the volume instead of jumping it.

A step change in amplitude is heard as a click, so ducking, pausing and resuming all
move the gain across a few frames instead.
"""

import array


class GainRamp:
    """A gain moving towards a target at a fixed rate."""

    def __init__(self) -> None:
        self.gain = 1.0
        self.target = 1.0
        self._rate = 0.0

    def snap(self, gain: float) -> None:
        """Jump to `gain` now, cancelling any ramp in progress."""
        self.gain = self.target = gain
        self._rate = 0.0

    def set(self, target: float, seconds: float) -> None:
        """Move towards `target` over `seconds`, from wherever the gain is now."""
        self.target = target
        self._rate = (target - self.gain) / seconds

    def step(self, seconds: float) -> float:
        """Advance one frame and return the gain to apply to it."""
        if self.gain != self.target:
            self.gain += self._rate * seconds
            # A frame rarely lands on the target, so stop on the first overshoot.
            if (self._rate > 0) == (self.gain > self.target):
                self.gain = self.target
        return self.gain


def scale(pcm: bytes, gain: float) -> bytes:
    """Apply `gain` to a frame of signed 16-bit PCM."""
    # Full volume is the common case and not worth copying every sample for.
    if gain > 0.999:
        return pcm
    samples = array.array("h", pcm)
    for i in range(len(samples)):
        samples[i] = int(samples[i] * gain)
    return samples.tobytes()
