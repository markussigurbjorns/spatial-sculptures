"""Move the same impulse patch to the centre; even-index modes are nodal there."""

from dataclasses import replace

from ..config import StudyConfig


def configure(config: StudyConfig) -> StudyConfig:
    config.impulses = tuple(replace(event, x=0.0, y=0.0) for event in config.impulses)
    return config
