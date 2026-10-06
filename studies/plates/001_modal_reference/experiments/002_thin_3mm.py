"""Change only uniform plate thickness to 3 mm."""

from dataclasses import replace

from ..config import StudyConfig


def configure(config: StudyConfig) -> StudyConfig:
    config.plate = replace(config.plate, thickness=0.003)
    return config
