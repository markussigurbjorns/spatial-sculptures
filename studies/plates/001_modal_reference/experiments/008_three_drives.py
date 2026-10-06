"""Add three prescribed harmonic drives to the baseline impulse ring-down."""

from ..config import StudyConfig, default_config


def configure(config: StudyConfig) -> StudyConfig:
    config.drives = default_config(driven=True).drives
    return config
