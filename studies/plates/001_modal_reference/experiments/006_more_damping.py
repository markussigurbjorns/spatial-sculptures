"""Increase the assumed damping ratio from 0.005 to 0.02 for every mode."""

from ..config import StudyConfig


def configure(config: StudyConfig) -> StudyConfig:
    config.damping_ratio = 0.02
    return config
