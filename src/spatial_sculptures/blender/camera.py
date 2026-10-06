"""Generic camera setup."""

from collections.abc import Sequence
from typing import Any

from .utils import look_at


def create_camera(
    name: str,
    location: Sequence[float],
    target: Sequence[float],
    *,
    lens: float = 50.0,
    active: bool = True,
) -> Any:
    """Create a perspective camera aimed at target; optionally make it the active camera."""
    import bpy

    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.clip_start = 0.01
    data.clip_end = 100.0
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, target)
    if active:
        bpy.context.scene.camera = obj
    return obj
