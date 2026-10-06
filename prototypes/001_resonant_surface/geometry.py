"""Procedural construction of the resonant-water-basin sculpture only."""

from dataclasses import dataclass
from math import atan2, cos, hypot, sin
from typing import Any

from spatial_sculptures.blender.geometry import add_sphere, radial_surface
from spatial_sculptures.blender.utils import add_cylinder, cylinder_between, set_smooth

from .config import PrototypeConfig


@dataclass
class Sculpture:
    """Objects and undeformed coordinates needed by this prototype's animation."""

    basin: Any
    water: Any
    water_base: tuple[tuple[float, float, float], ...]
    exciters: list[Any]
    hydrophones: list[Any]
    supports: list[Any]
    drip_structure: list[Any]
    droplet: Any


def _outline_scale(angle: float, basin: dict[str, Any]) -> float:
    return 1.0 + basin["asymmetry"] * (sin(3 * angle + 0.45) + 0.35 * cos(5 * angle))


def _basin_height(radius: float, angle: float, basin: dict[str, Any]) -> float:
    height = basin["center_z"] + (basin["rim_z"] - basin["center_z"]) * (
        radius ** basin["profile_power"]
    )
    # Millimetre-scale irregularity suggests fabrication, not structural analysis.
    return height + 0.0009 * radius**4 * sin(5 * angle + 0.3)


def _height_at(x: float, y: float, basin: dict[str, Any]) -> float:
    nx, ny = x / basin["radius_x"], y / basin["radius_y"]
    angle = atan2(ny, nx)
    radius = hypot(nx, ny) / _outline_scale(angle, basin)
    return _basin_height(radius, angle, basin)


def create_basin(config: PrototypeConfig, material: Any) -> Any:
    """Create a shallow, asymmetric elliptical vessel with an open, softened rim."""
    basin = config.basin

    def position(radius: float, angle: float) -> tuple[float, float, float]:
        outline = _outline_scale(angle, basin)
        return (
            basin["radius_x"] * radius * outline * cos(angle),
            basin["radius_y"] * radius * outline * sin(angle),
            _basin_height(radius, angle, basin),
        )

    obj = radial_surface("Resonant basin", basin["rings"], basin["segments"], position, material)
    solidify = obj.modifiers.new("Metal thickness", "SOLIDIFY")
    solidify.thickness = basin["thickness"]
    solidify.offset = -1.0
    solidify.use_even_offset = True
    bevel = obj.modifiers.new("Soft fabricated rim", "BEVEL")
    bevel.width = basin["rim_bevel"]
    bevel.segments = 3
    bevel.limit_method = "ANGLE"
    return set_smooth(obj)


def create_water(config: PrototypeConfig, material: Any) -> Any:
    """Create the radial water mesh and store its undeformed vertices on the object."""
    water = config.water

    def position(radius: float, angle: float) -> tuple[float, float, float]:
        return (
            water["radius_x"] * radius * cos(angle),
            water["radius_y"] * radius * sin(angle),
            water["z"],
        )

    obj = radial_surface("Water surface", water["rings"], water["segments"], position, material)
    obj["base_coordinates"] = [axis for vertex in obj.data.vertices for axis in vertex.co]
    return set_smooth(obj)


def create_exciter(
    index: int, source: dict[str, float], config: PrototypeConfig, materials: dict[str, Any]
) -> Any:
    """Attach a visible contact-exciter body to the underside of the metal."""
    x, y = source["x"], source["y"]
    underside = _height_at(x, y, config.basin) - config.basin["thickness"]
    body = add_cylinder(
        f"Exciter {index}", 0.036, 0.036, (x, y, underside - 0.018), materials["sensor"]
    )
    collar = add_cylinder(
        f"Exciter {index} contact", 0.041, 0.006, (x, y, underside - 0.003), materials["dark"]
    )
    collar.parent = body
    collar.matrix_parent_inverse = body.matrix_world.inverted()
    # Cable stubs help communicate attachment without claiming a wiring design.
    cylinder_between(
        f"Exciter {index} cable",
        (x, y, underside - 0.028),
        (x + 0.065, y, underside - 0.09),
        0.002,
        materials["sensor"],
    )
    body["frequency_hz"] = source["frequency"]
    return body


def create_hydrophone(
    index: int,
    position: tuple[float, float],
    config: PrototypeConfig,
    materials: dict[str, Any],
) -> Any:
    """Place a small submerged sensor and a cable reaching the rear rim."""
    x, y = position
    z = config.water["z"] - 0.024
    sensor = add_cylinder(f"Hydrophone {index}", 0.012, 0.027, (x, y, z), materials["sensor"])
    cable_top = (x, y, config.water["z"] + 0.017)
    cylinder_between(
        f"Hydrophone {index} lead", (x, y, z + 0.012), cable_top, 0.0018, materials["sensor"]
    )
    cylinder_between(
        f"Hydrophone {index} cable",
        cable_top,
        (x, config.basin["radius_y"] * 0.91, config.basin["rim_z"] + 0.012),
        0.0018,
        materials["sensor"],
    )
    return sensor


def create_supports(config: PrototypeConfig, material: Any) -> list[Any]:
    """Place four slim legs beneath the broad basin floor."""
    supports = []
    for index, (sx, sy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1)), start=1):
        x, y = sx * config.basin["radius_x"] * 0.57, sy * config.basin["radius_y"] * 0.50
        top = _height_at(x, y, config.basin) - config.basin["thickness"]
        supports.append(
            cylinder_between(
                f"Support {index}",
                (x, y, 0.012),
                (x, y, top),
                config.basin["support_radius"],
                material,
            )
        )
    return supports


def create_drip_structure(
    config: PrototypeConfig, materials: dict[str, Any]
) -> tuple[list[Any], Any]:
    """Create one minimal overhead arm, nozzle, and an independently animated droplet."""
    drip = config.drip
    x, y = drip["position"]
    rear = (0.0, config.basin["radius_y"] + 0.16)
    arm_z = drip["nozzle_z"] + 0.035
    mast = cylinder_between(
        "Drip mast", (*rear, 0.0), (*rear, arm_z), drip["arm_radius"], materials["dark"]
    )
    arm = cylinder_between(
        "Drip arm", (*rear, arm_z), (x, y, arm_z), drip["arm_radius"], materials["dark"]
    )
    nozzle = cylinder_between(
        "Drip nozzle", (x, y, arm_z), (x, y, drip["nozzle_z"]), 0.005, materials["steel"]
    )
    droplet = add_sphere(
        "Water droplet",
        drip["droplet_radius"],
        (x, y, drip["nozzle_z"]),
        materials["water"],
        scale=(0.8, 0.8, 1.35),
    )
    return [mast, arm, nozzle], droplet


def create_sculpture(materials: dict[str, Any], config: PrototypeConfig) -> Sculpture:
    """Assemble only the sculpture; presentation and animation are separate."""
    basin = create_basin(config, materials["steel"])
    water = create_water(config, materials["water"])
    base = tuple(tuple(vertex.co) for vertex in water.data.vertices)
    exciters = [
        create_exciter(i, source, config, materials)
        for i, source in enumerate(config.exciters, start=1)
    ]
    hydrophones = [
        create_hydrophone(i, position, config, materials)
        for i, position in enumerate(config.hydrophones, start=1)
    ]
    supports = create_supports(config, materials["dark"])
    drip_structure, droplet = create_drip_structure(config, materials)
    return Sculpture(basin, water, base, exciters, hydrophones, supports, drip_structure, droplet)
