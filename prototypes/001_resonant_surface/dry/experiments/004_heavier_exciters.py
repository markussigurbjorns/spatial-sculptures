"""Increase each rigid housing mass from 120 g to 600 g."""

from dataclasses import replace


def configure(config):
    config.exciters = tuple(replace(e, added_mass_kg=0.6) for e in config.exciters)
    return config
