"""Three prescribed vertical forces; mounting, structure and damping stay unchanged."""

from dataclasses import replace


def configure(config):
    config.impulses = ()
    config.exciters = tuple(
        replace(exciter, force_n=force)
        for exciter, force in zip(config.exciters, (1.0, 0.85, 0.95), strict=True)
    )
    return config
