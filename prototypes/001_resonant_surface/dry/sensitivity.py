"""Explicit one-factor variations of provisional support and rigid mounting assumptions."""

from copy import deepcopy
from dataclasses import replace

CASES = {
    "support_half": ("support_scale", 0.5),
    "support_double": ("support_scale", 2.0),
    "mount_narrow": ("mount_width_scale", 0.5),
    "mount_wide": ("mount_width_scale", 1.5),
}


def configure(base, name):
    """Change one parameter family while retaining material, positions, mass and damping."""
    if name not in CASES:
        raise ValueError(f"Unknown sensitivity case: {name}")
    parameter, scale = CASES[name]
    config = deepcopy(base)
    if parameter == "support_scale":
        config.supports = tuple(
            replace(s, stiffness=tuple(v * scale for v in s.stiffness)) for s in base.supports
        )
    elif parameter == "mount_width_scale":
        config.exciters = tuple(
            replace(e, patch=replace(e.patch, width=e.patch.width * scale)) for e in base.exciters
        )
    return config
