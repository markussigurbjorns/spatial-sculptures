"""Move the contact pickups; the underlying motion and energy remain identical."""

from ..config import StudyConfig


def configure(config: StudyConfig) -> StudyConfig:
    config.pickups = ((0.0, 0.0), (0.40, -0.20))
    return config
