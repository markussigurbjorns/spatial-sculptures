"""Generic procedural meshes and primitives; sculpture geometry lives in prototypes."""

from collections.abc import Callable, Sequence
from math import tau
from typing import Any

Point = tuple[float, float, float]


def create_mesh(
    name: str, vertices: Sequence[Point], faces: Sequence[Sequence[int]], material: Any = None
) -> Any:
    """Link an object built from vertices and indexed polygon faces to the current scene."""
    import bpy

    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    if material is not None:
        mesh.materials.append(material)
    return obj


def radial_surface(
    name: str,
    rings: int,
    segments: int,
    position: Callable[[float, float], Point],
    material: Any = None,
) -> Any:
    """Create a disk with one center vertex and quad rings using position(radius, angle).

    Radius is normalized to [0, 1]; angles are in radians. For a standard XY disk,
    faces point upward. The callback supplies shape, scale, and height.
    """
    if rings < 1 or segments < 3:
        raise ValueError("Radial surfaces need at least one ring and three segments")
    vertices = [position(0.0, 0.0)]
    vertices.extend(
        position(ring / rings, tau * segment / segments)
        for ring in range(1, rings + 1)
        for segment in range(segments)
    )
    faces = [(0, 1 + j, 1 + (j + 1) % segments) for j in range(segments)]
    for ring in range(1, rings):
        inner = 1 + (ring - 1) * segments
        outer = inner + segments
        for j in range(segments):
            following = (j + 1) % segments
            faces.append((inner + j, outer + j, outer + following, inner + following))
    return create_mesh(name, vertices, faces, material)


def add_sphere(
    name: str,
    radius: float,
    location: Sequence[float],
    material: Any = None,
    scale: Sequence[float] = (1.0, 1.0, 1.0),
) -> Any:
    """Create a smooth UV sphere, optionally stretched along its local axes."""
    import bpy

    from .utils import set_smooth

    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=24, ring_count=12, radius=radius, location=location
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    if material is not None:
        obj.data.materials.append(material)
    return set_smooth(obj)
