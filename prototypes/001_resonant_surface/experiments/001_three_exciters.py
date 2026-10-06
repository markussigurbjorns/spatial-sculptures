"""Baseline: three slightly different exciters, exactly matching the default settings."""

from ..config import PrototypeConfig


def configure(config: PrototypeConfig) -> PrototypeConfig:
    """Leave the supplied fresh baseline unchanged."""
    return config
