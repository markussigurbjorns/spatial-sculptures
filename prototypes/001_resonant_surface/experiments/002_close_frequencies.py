"""Close frequencies and a shared wavelength make slow beating easier to observe.

At time_scale=1, pairwise periods are ~12.5, 11.1 and 5.9 seconds.
Using the baseline's 0.06 visual time scale would stretch these to ~208, 185 and
98 seconds, so this experiment uses real-time phase motion and a 60-second timeline.
This is still an artistic field, not a measured physical basin response.
"""

from ..config import PrototypeConfig


def configure(config: PrototypeConfig) -> PrototypeConfig:
    """Override only this experiment's parameters, preserving the sculpture implementation."""
    for source, frequency in zip(config.exciters, (59.00, 59.08, 59.17), strict=True):
        source["frequency"] = frequency
        source["wavelength"] = 0.19
    config.water["time_scale"] = 1.0
    config.animation["seconds"] = 60
    # More temporal samples reduce aliasing of the ~59 Hz visual phase motion.
    config.animation["fps"] = 240
    return config
