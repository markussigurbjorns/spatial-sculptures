"""Artistic interference and drip animation; intentionally not CFD, FEM, or acoustics."""

from dataclasses import dataclass
from math import ceil, floor, hypot, sin
from typing import Any

from spatial_sculptures.blender.utils import HANDLER_TAG, remove_frame_handlers
from spatial_sculptures.simulation.waves import expanding_ripple, radial_wave

from .config import PrototypeConfig
from .geometry import Sculpture

FRAME_HANDLER_NAME = "resonant_surface_frame_change"


def _drip_clock(time: float, interval: float) -> tuple[int, float]:
    # A tiny cycle tolerance keeps e.g. 9.6 / 3.2 from rounding below impact 3.
    completed = floor(time / interval + 1e-9)
    return completed, max(0.0, time - completed * interval)


def impact_ages(time: float, config: PrototypeConfig) -> tuple[float, ...]:
    """Return ages of surviving impacts; the first drip hits after one full interval."""
    interval = config.drip["interval"]
    last, _phase = _drip_clock(time, interval)
    first = max(1, ceil((time - config.drip["ripple_lifetime"]) / interval))
    return tuple(max(0.0, time - impact * interval) for impact in range(first, last + 1))


def displacement(
    x: float,
    y: float,
    time: float,
    config: PrototypeConfig,
    ages: tuple[float, ...] | None = None,
) -> float:
    """Sum exciter waves, drip rings and subtle irregularity, in metres.

    Exciter amplitudes are dimensionless relative weights. The common water amplitude
    converts the sum to visual displacement. A soft edge taper keeps water inside
    the vessel; it is not a simulated physical boundary condition.
    """
    water = config.water
    radius = hypot(x / water["radius_x"], y / water["radius_y"])
    edge = max(0.0, 1.0 - radius ** water["edge_fade_power"])
    result = water["wave_amplitude"] * sum(
        radial_wave(
            x,
            y,
            source["x"],
            source["y"],
            time,
            source["frequency"],
            source["wavelength"],
            source["phase"],
            source["amplitude"],
            water["damping"],
            water["time_scale"],
        )
        for source in config.exciters
    )
    drip = config.drip
    drip_x, drip_y = drip["position"]
    if ages is None:
        ages = impact_ages(time, config)
    result += sum(
        expanding_ripple(
            x,
            y,
            drip_x,
            drip_y,
            age,
            amplitude=drip["ripple_amplitude"],
            speed=drip["wave_speed"],
            wavelength=drip["ripple_wavelength"],
            width=drip["ripple_width"],
            decay=drip["ripple_decay"],
        )
        for age in ages
    )
    result += (
        water["irregularity"]
        * sin(3.7 * x + 5.3 * y + 0.35 * time)
        * sin(2.1 * x - 4.2 * y - 0.23 * time)
    )
    return edge * result


def droplet_state(time: float, config: PrototypeConfig) -> tuple[bool, float]:
    """Return visibility and Z; a quadratic fall ends exactly when an impact begins.

    This normalized fall is a visual approximation rather than a gravity integration.
    """
    drip = config.drip
    _completed, phase = _drip_clock(time, drip["interval"])
    fall_start = drip["interval"] - drip["fall_time"]
    visible = time >= 0 and phase >= fall_start
    progress = max(0.0, (phase - fall_start) / drip["fall_time"])
    z = drip["nozzle_z"] + (config.water["z"] - drip["nozzle_z"]) * progress**2
    return visible, z


@dataclass
class SimulationState:
    sculpture: Sculpture
    config: PrototypeConfig


_state: SimulationState | None = None


def resonant_surface_frame_change(scene: Any, _depsgraph: Any = None) -> None:
    """Named Blender callback, removable by name even after module/script reloads."""
    if _state is None:
        return
    sculpture, config = _state.sculpture, _state.config
    time = (scene.frame_current - config.animation["frame_start"]) / config.animation["fps"]
    ages = impact_ages(time, config)
    # Absolute deformation from base coordinates supports backwards scrubbing.
    for vertex, (x, y, z) in zip(sculpture.water.data.vertices, sculpture.water_base, strict=True):
        vertex.co = (x, y, z + displacement(x, y, time, config, ages))
    sculpture.water.data.update()
    visible, z = droplet_state(time, config)
    sculpture.droplet.location.z = z
    sculpture.droplet.hide_render = not visible
    sculpture.droplet.hide_viewport = not visible


def setup_simulation(sculpture: Sculpture, config: PrototypeConfig) -> None:
    """Replace the previous callback and initialize the water at the first frame."""
    import bpy

    global _state
    remove_frame_handlers((FRAME_HANDLER_NAME,))
    _state = SimulationState(sculpture, config)
    setattr(resonant_surface_frame_change, HANDLER_TAG, True)
    bpy.app.handlers.frame_change_pre.append(resonant_surface_frame_change)
    # Blender recommends locking the interface when render-time handlers mutate meshes.
    bpy.context.scene.render.use_lock_interface = True
    bpy.context.scene.frame_set(config.animation["frame_start"])
