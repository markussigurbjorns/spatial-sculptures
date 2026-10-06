"""Small Blender scene and primitive utilities, independent of any sculpture."""

from collections.abc import Callable, Iterable, Sequence
from typing import Any

HANDLER_TAG = "_spatial_sculptures_handler"
_TIMER_REGISTRY = "_spatial_sculptures_timers"


def remove_timers(names: Iterable[str] = (), *, tagged: bool = False) -> int:
    """Remove tracked research timers, including callbacks from older module reloads."""
    import bpy

    names = set(names)
    callbacks = bpy.app.driver_namespace.setdefault(_TIMER_REGISTRY, [])
    removed = 0
    for callback in list(callbacks):
        if callback.__name__ in names or (tagged and getattr(callback, HANDLER_TAG, False)):
            if bpy.app.timers.is_registered(callback):
                bpy.app.timers.unregister(callback)
                removed += 1
            callbacks.remove(callback)
    return removed


def register_timer(callback: Callable[[], float | None], *, first_interval: float = 0.0) -> None:
    """Register and track a research timer so clear_scene can cancel it on rebuild."""
    import bpy

    setattr(callback, HANDLER_TAG, True)
    bpy.app.timers.register(callback, first_interval=first_interval)
    bpy.app.driver_namespace.setdefault(_TIMER_REGISTRY, []).append(callback)


def remove_frame_handlers(names: Iterable[str] = (), *, tagged: bool = False) -> int:
    """Remove matching callbacks from both frame handler lists, including old reloads."""
    import bpy

    names = set(names)
    removed = 0
    for handlers in (bpy.app.handlers.frame_change_pre, bpy.app.handlers.frame_change_post):
        for handler in list(handlers):
            if handler.__name__ in names or (tagged and getattr(handler, HANDLER_TAG, False)):
                handlers.remove(handler)
                removed += 1
    return removed


def clear_scene(handler_names: Iterable[str] = ()) -> None:
    """Clear scene objects and research callbacks so repeated builds remain clean.

    Prototype callbacks should carry HANDLER_TAG or be supplied by name. Unrelated
    add-on callbacks are left alone. Remove orphaned meshes/materials from old builds.
    """
    import bpy

    remove_frame_handlers(handler_names, tagged=True)
    remove_timers(tagged=True)
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(collection):
            if block.users == 0:
                collection.remove(block)


def set_smooth(obj: Any) -> Any:
    """Enable smooth shading on every face of a mesh object."""
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def look_at(obj: Any, target: Sequence[float]) -> None:
    """Point a camera/light's local -Z axis at target, keeping local Y upright."""
    from mathutils import Vector

    direction = Vector(target) - obj.location
    if direction.length == 0:
        raise ValueError("The look-at target must differ from the object position")
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_cylinder(
    name: str,
    radius: float,
    depth: float,
    location: Sequence[float],
    material: Any = None,
    vertices: int = 48,
) -> Any:
    """Create a smooth, Z-aligned cylinder and optionally attach a material."""
    import bpy

    if radius <= 0 or depth <= 0:
        raise ValueError("Cylinder radius and depth must be positive")
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=depth, location=location
    )
    obj = bpy.context.object
    obj.name = name
    if material is not None:
        obj.data.materials.append(material)
    return set_smooth(obj)


def cylinder_between(
    name: str,
    start: Sequence[float],
    end: Sequence[float],
    radius: float,
    material: Any = None,
    vertices: int = 32,
) -> Any:
    """Create a cylinder whose ends lie at two arbitrary points."""
    from mathutils import Vector

    start, end = Vector(start), Vector(end)
    direction = end - start
    if direction.length == 0:
        raise ValueError("Cylinder endpoints must be distinct")
    obj = add_cylinder(name, radius, direction.length, (start + end) / 2, material, vertices)
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    return obj
