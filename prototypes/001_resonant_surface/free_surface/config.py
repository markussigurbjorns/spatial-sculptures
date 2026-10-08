"""Editable assumptions for a linear dynamic free surface, in SI units."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class FreeSurfaceConfig:
    depth_m: float = 0.065
    density_kg_m3: float = 1000.0
    gravity_m_s2: float = 9.81
    surface_tension_n_m: float = 0.072  # Provisional clean-water value; not a measured fluid.
    surface_damping_ratio: float = 0.02  # Phenomenological, not a viscosity calculation.
    hydrophones: tuple[tuple[float, float, float], ...] = (
        (-0.20, -0.04, 0.02),
        (0.25, -0.10, 0.02),
    )
    horizontal_degree: int = 12
    vertical_degree: int = 3
    surface_degree: int = 10
    dry_basis_count: int = 256
    playback_count: int = 128
    pulse_seconds: float = 0.01
    output_stop_hz: float = 80.0
    duration_s: float = 6.0

    def __post_init__(self):
        positive = (
            self.depth_m,
            self.density_kg_m3,
            self.gravity_m_s2,
            self.pulse_seconds,
            self.output_stop_hz,
            self.duration_s,
        )
        if (
            not all(isfinite(v) and v > 0 for v in positive)
            or not isfinite(self.surface_tension_n_m)
            or self.surface_tension_n_m < 0
            or not isfinite(self.surface_damping_ratio)
            or not 0 <= self.surface_damping_ratio < 1
            or not self.hydrophones
            or any(
                len(p) != 3 or not all(isfinite(v) for v in p) or p[2] <= 0
                for p in self.hydrophones
            )
        ):
            raise ValueError(
                "Positive finite SI settings and valid damping/tension/probes required"
            )
        for name, minimum in (
            ("horizontal_degree", 2),
            ("vertical_degree", 1),
            ("surface_degree", 1),
            ("dry_basis_count", 1),
            ("playback_count", 1),
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
        if self.surface_degree > self.horizontal_degree:
            raise ValueError("Surface degree cannot exceed potential horizontal degree")
        n = (self.surface_degree + 1) * (self.surface_degree + 2) // 2 - 1
        if self.playback_count > self.dry_basis_count + n:
            raise ValueError("Too many requested coupled playback modes")
