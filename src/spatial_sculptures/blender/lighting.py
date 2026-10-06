"""Generic light creation."""

from collections.abc import Sequence
from typing import Any

from .utils import look_at


def area_light(
    name: str,
    location: Sequence[float],
    target: Sequence[float],
    *,
    energy: float = 600.0,
    size: float = 3.0,
    color: Sequence[float] = (1.0, 1.0, 1.0),
) -> Any:
    """Create a disk area light aimed at target. Energy is Blender's power in watts."""
    import bpy

    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, target)
    return obj
