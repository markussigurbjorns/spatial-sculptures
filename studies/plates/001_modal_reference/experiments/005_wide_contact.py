"""Increase impulse patch width to 150 mm while keeping total impulse fixed."""

from dataclasses import replace

from ..config import StudyConfig


def configure(config: StudyConfig) -> StudyConfig:
    config.impulses = tuple(replace(event, patch_width=0.15) for event in config.impulses)
    return config
