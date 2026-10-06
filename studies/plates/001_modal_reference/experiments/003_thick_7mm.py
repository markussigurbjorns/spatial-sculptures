"""Change only uniform plate thickness to 7 mm."""

from dataclasses import replace

from ..config import StudyConfig


def configure(config: StudyConfig) -> StudyConfig:
    config.plate = replace(config.plate, thickness=0.007)
    return config
