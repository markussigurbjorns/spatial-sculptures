"""Editable wet pressure-release model; separate from certified dry/column studies."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class WetConfig:
    depth_m: float = 0.065
    density_kg_m3: float = 1000.0
    # x, y, depth below mean water surface, metres. Positive depth is into the fluid.
    hydrophones: tuple[tuple[float, float, float], ...] = (
        (-0.20, -0.04, 0.02),
        (0.25, -0.10, 0.02),
    )
    horizontal_degree: int = 10
    vertical_degree: int = 2
    dry_basis_count: int = 256
    playback_count: int = 64
    pulse_seconds: float = 0.01  # Finite box pulse replaces an ideal pressure-singular impulse.
    output_stop_hz: float = 80.0

    def __post_init__(self):
        if (
            not all(
                isfinite(v) and v > 0
                for v in (self.depth_m, self.density_kg_m3, self.pulse_seconds, self.output_stop_hz)
            )
            or not self.hydrophones
            or any(
                len(p) != 3 or not all(isfinite(v) for v in p) or p[2] <= 0
                for p in self.hydrophones
            )
        ):
            raise ValueError(
                "Positive finite water/pulse/band settings and XYZ-depth probes required"
            )
        for name, minimum in (
            ("horizontal_degree", 0),
            ("vertical_degree", 0),
            ("dry_basis_count", 1),
            ("playback_count", 1),
        ):
            v = getattr(self, name)
            if not isinstance(v, int) or isinstance(v, bool) or v < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
        if self.playback_count > self.dry_basis_count:
            raise ValueError("Playback count cannot exceed the dry modal subspace")
