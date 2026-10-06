"""Editable settings for the resonant basin. Units: metres, seconds, Hz, radians.

These are artistic parameters, not material measurements or calibrated acoustics.
Every build receives a deep copy so experiments never mutate the defaults.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

FPS = 30
ANIMATION_SECONDS = 20

ANIMATION = {"fps": FPS, "seconds": ANIMATION_SECONDS, "frame_start": 1}

BASIN = {
    "radius_x": 0.72,
    "radius_y": 0.58,
    "center_z": 0.72,
    "rim_z": 0.84,
    "thickness": 0.005,
    "rings": 28,
    "segments": 144,
    "profile_power": 6.0,
    "asymmetry": 0.022,
    "rim_bevel": 0.0015,
    "support_radius": 0.011,
}

WATER = {
    "radius_x": 0.625,
    "radius_y": 0.485,
    "z": 0.785,
    "rings": 48,
    "segments": 144,
    "wave_amplitude": 0.004,
    "time_scale": 0.06,
    "damping": 1.25,
    "irregularity": 0.00018,
    "edge_fade_power": 8.0,
    # Independent, equal-area sampling for state metrics; not the Blender mesh.
    "state_rings": 8,
    "state_segments": 32,
}

EXCITERS = [
    {
        "x": -0.34,
        "y": 0.14,
        "frequency": 59.0,
        "wavelength": 0.19,
        "phase": 0.0,
        "amplitude": 1.0,
    },
    {
        "x": 0.31,
        "y": 0.13,
        "frequency": 61.3,
        "wavelength": 0.165,
        "phase": 1.7,
        "amplitude": 0.85,
    },
    {
        "x": 0.02,
        "y": -0.32,
        "frequency": 57.8,
        "wavelength": 0.215,
        "phase": 3.1,
        "amplitude": 0.95,
    },
]

HYDROPHONES = [(-0.20, -0.04), (0.25, -0.10)]

DRIP = {
    "position": (0.04, 0.03),
    "interval": 3.2,
    "fall_time": 0.55,
    "ripple_amplitude": 0.009,
    "wave_speed": 0.28,
    "ripple_lifetime": 5.0,
    "ripple_wavelength": 0.075,
    "ripple_width": 0.055,
    "ripple_decay": 0.85,
    "impact_duration": 0.12,
    "nozzle_z": 1.45,
    "droplet_radius": 0.008,
    "arm_radius": 0.009,
}

RENDERING = {
    "engine": "BLENDER_EEVEE_NEXT",
    "resolution_x": 1440,
    "resolution_y": 1080,
    "resolution_percentage": 100,
    "samples": 64,
    "transparent": False,
    "camera_position": (2.05, -2.75, 1.85),
    "camera_target": (0.0, 0.0, 0.75),
    "camera_lens": 48.0,
    "world_strength": 0.25,
}

OSC = {
    "enabled": False,
    "host": "127.0.0.1",
    "port": 57120,
    "send_rate": 30,
}


@dataclass
class PrototypeConfig:
    """One editable parameter set, deliberately limited to this sculpture."""

    animation: dict[str, Any]
    basin: dict[str, Any]
    water: dict[str, Any]
    exciters: list[dict[str, float]]
    hydrophones: list[tuple[float, float]]
    drip: dict[str, Any]
    rendering: dict[str, Any]
    osc: dict[str, Any]

    def validate(self) -> None:
        """Catch basic parameter errors before creating Blender objects."""
        if self.animation["fps"] <= 0 or self.animation["seconds"] <= 0:
            raise ValueError("Animation FPS and duration must be positive")
        for parameters in (self.basin, self.water):
            if parameters["radius_x"] <= 0 or parameters["radius_y"] <= 0:
                raise ValueError("Surface radii must be positive")
            if parameters["rings"] < 1 or parameters["segments"] < 3:
                raise ValueError("Surfaces need at least one ring and three segments")
        if not self.basin["center_z"] < self.water["z"] < self.basin["rim_z"]:
            raise ValueError("Water must sit between the basin floor and rim")
        if self.basin["thickness"] <= 0 or self.basin["profile_power"] <= 0:
            raise ValueError("Basin thickness and profile power must be positive")
        if self.water["damping"] < 0 or self.water["edge_fade_power"] <= 0:
            raise ValueError("Water damping must be >= 0 and edge fade power > 0")
        if self.water["state_rings"] < 1 or self.water["state_segments"] < 3:
            raise ValueError("State sampling needs at least one ring and three segments")
        if not 0 < self.drip["fall_time"] < self.drip["interval"]:
            raise ValueError("Drip fall time must be positive and shorter than its interval")
        if self.drip["nozzle_z"] <= self.water["z"]:
            raise ValueError("Drip nozzle must be above the water")
        if self.drip["wave_speed"] <= 0 or self.drip["ripple_lifetime"] <= 0:
            raise ValueError("Drip wave speed and ripple lifetime must be positive")
        if not 0 < self.drip["impact_duration"] < self.drip["interval"]:
            raise ValueError("Drop impact duration must be positive and shorter than its interval")
        if any(source["wavelength"] <= 0 for source in self.exciters):
            raise ValueError("Exciter wavelengths must be positive")
        if not 1 <= self.osc["port"] <= 65535 or self.osc["send_rate"] <= 0:
            raise ValueError("OSC port must be 1..65535 and send rate must be positive")


def default_config() -> PrototypeConfig:
    """Return fresh settings for a build or experiment."""
    return PrototypeConfig(
        animation=deepcopy(ANIMATION),
        basin=deepcopy(BASIN),
        water=deepcopy(WATER),
        exciters=deepcopy(EXCITERS),
        hydrophones=deepcopy(HYDROPHONES),
        drip=deepcopy(DRIP),
        rendering=deepcopy(RENDERING),
        osc=deepcopy(OSC),
    )
