"""Small offline audio helpers; sample generation belongs to the physical/artistic model."""

import sys
import wave
from array import array
from math import isfinite
from pathlib import Path


def write_pickup_wav(path: Path, channels, sample_rate: int, *, peak: float = 0.9) -> float:
    """Write normalized 16-bit PCM with one shared gain; return gain per input unit.

    Callers document input units. Normalization is a listening gain, not acoustic
    calibration. Relative channel levels are retained, silence stays silent.
    """
    if sample_rate < 1 or not 0 < peak <= 1:
        raise ValueError("Sample rate must be positive and peak in (0, 1]")
    if len(channels) == 0 or len(channels[0]) == 0:
        raise ValueError("At least one nonempty audio channel is required")
    length = len(channels[0])
    if any(len(channel) != length for channel in channels):
        raise ValueError("Audio channels must have equal lengths")
    maximum = 0.0
    for channel in channels:
        for value in channel:
            if not isfinite(value):
                raise ValueError("Audio samples must be finite")
            maximum = max(maximum, abs(value))
    gain = peak / maximum if maximum else 0.0
    pcm = array(
        "h",
        (
            round(max(-1.0, min(1.0, float(channel[index]) * gain)) * 32767)
            for index in range(length)
            for channel in channels
        ),
    )
    if sys.byteorder != "little":
        pcm.byteswap()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(len(channels))
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm.tobytes())
    return gain
