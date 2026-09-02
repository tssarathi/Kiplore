"""Sliding the volume instead of jumping it."""

import array


class GainRamp:
    def __init__(self) -> None:
        self.gain = 1.0
        self.target = 1.0
        self._rate = 0.0

    def snap(self, gain: float) -> None:
        self.gain = self.target = gain
        self._rate = 0.0

    def set(self, target: float, seconds: float) -> None:
        self.target = target
        self._rate = (target - self.gain) / seconds

    def step(self, seconds: float) -> float:
        if self.gain != self.target:
            self.gain += self._rate * seconds
            if (self._rate > 0) == (self.gain > self.target):
                self.gain = self.target
        return self.gain


def scale(pcm: bytes, gain: float) -> bytes:
    if gain > 0.999:
        return pcm
    samples = array.array("h", pcm)
    for i in range(len(samples)):
        samples[i] = int(samples[i] * gain)
    return samples.tobytes()
