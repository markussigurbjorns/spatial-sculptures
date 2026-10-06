"""Reduce all translational support stiffnesses by a factor of four."""

from dataclasses import replace


def configure(config):
    config.supports = tuple(
        replace(s, stiffness=tuple(v / 4 for v in s.stiffness)) for s in config.supports
    )
    return config
