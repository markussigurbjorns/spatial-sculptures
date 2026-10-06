"""Flatten the same elliptical planform; keep four supports and housing masses."""

from dataclasses import replace


def configure(config):
    config.surface = replace(config.surface, rise=0.0, asymmetry=0.0)
    return config
