"""Reusable Principled BSDF material factories with Blender 3/4 socket aliases."""

from collections.abc import Sequence
from typing import Any


def principled_material(
    name: str,
    base_color: Sequence[float],
    *,
    metallic: float = 0.0,
    roughness: float = 0.4,
    transmission: float = 0.0,
    ior: float = 1.45,
) -> Any:
    """Create or update a named material. Base color is a linear RGBA value.

    Transmission Weight in Blender 4+ was called Transmission in Blender 3.
    """
    import bpy

    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = tuple(base_color)
    bsdf = next(node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    values = {
        ("Base Color",): tuple(base_color),
        ("Metallic",): metallic,
        ("Roughness",): roughness,
        ("Transmission Weight", "Transmission"): transmission,
        ("IOR",): ior,
    }
    for aliases, value in values.items():
        for name in aliases:
            socket = bsdf.inputs.get(name)
            if socket is not None:
                socket.default_value = value
                break
        else:
            raise RuntimeError(f"Principled BSDF has no input matching {aliases}")
    return material


def brushed_steel(name: str = "Brushed steel") -> Any:
    """Soft silver metal; roughness suggests brushing without a texture dependency."""
    return principled_material(name, (0.42, 0.46, 0.49, 1.0), metallic=0.94, roughness=0.27)


def dark_metal(name: str = "Dark metal") -> Any:
    """Dark metallic finish for structural components."""
    return principled_material(name, (0.045, 0.055, 0.065, 1.0), metallic=0.8, roughness=0.32)


def black_sensor(name: str = "Black sensor") -> Any:
    """Matte black housing for sensors or other small components."""
    return principled_material(name, (0.012, 0.016, 0.02, 1.0), roughness=0.52)


def concrete(name: str = "Concrete") -> Any:
    """Neutral matte surface suitable for a simple studio floor."""
    return principled_material(name, (0.16, 0.18, 0.19, 1.0), roughness=0.92)


def water(name: str = "Water") -> Any:
    """Water-like dielectric with IOR 1.333; this shader supplies no fluid physics."""
    return principled_material(
        name, (0.68, 0.88, 0.92, 1.0), roughness=0.075, transmission=0.9, ior=1.333
    )
