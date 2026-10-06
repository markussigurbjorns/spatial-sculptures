"""Prepared samples of this sculpture's artistic field, with optional NumPy batching.

Positions, damping, wavelengths and source phases are cached. Prepare again after
changing those parameters. Exciter amplitude/frequency remain per-state controls.
No mesh or Blender dependency belongs here.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import exp, hypot, sin, tau
from typing import TYPE_CHECKING

from spatial_sculptures.simulation.fields import ExciterState

from .config import PrototypeConfig

if TYPE_CHECKING:
    import numpy as np


class FieldSampler:
    """Evaluate fixed XY positions efficiently using the original field equations."""

    def __init__(
        self,
        config: PrototypeConfig,
        points: Sequence[tuple[float, float]],
        *,
        use_numpy: bool | None = None,
    ) -> None:
        self.config = config
        self.points = tuple(points)
        self.np = None
        if use_numpy is not False:
            try:
                import numpy
            except ImportError:
                if use_numpy:
                    raise
            else:
                self.np = numpy
        self.backend = "numpy" if self.np is not None else "python"
        water = config.water
        self.edge = tuple(
            max(
                0.0,
                1.0
                - hypot(x / water["radius_x"], y / water["radius_y"]) ** water["edge_fade_power"],
            )
            for x, y in self.points
        )
        self.phases, self.attenuation = [], []
        for source in config.exciters:
            radii = tuple(hypot(x - source["x"], y - source["y"]) for x, y in self.points)
            self.phases.append(
                tuple(tau * r / source["wavelength"] + source["phase"] for r in radii)
            )
            self.attenuation.append(tuple(exp(-water["damping"] * r) for r in radii))
        drop_x, drop_y = config.drip["position"]
        self.drop_radii = tuple(hypot(x - drop_x, y - drop_y) for x, y in self.points)
        self.irregular_a = tuple(3.7 * x + 5.3 * y for x, y in self.points)
        self.irregular_b = tuple(2.1 * x - 4.2 * y for x, y in self.points)
        if self.np is not None:
            self.edge = self.np.asarray(self.edge)
            self.phases = [self.np.asarray(row) for row in self.phases]
            self.attenuation = [self.np.asarray(row) for row in self.attenuation]
            self.drop_radii = self.np.asarray(self.drop_radii)
            self.irregular_a = self.np.asarray(self.irregular_a)
            self.irregular_b = self.np.asarray(self.irregular_b)

    def sample(
        self,
        time: float,
        *,
        exciters: tuple[ExciterState, ...] | None = None,
    ) -> list[float] | np.ndarray:
        """Return displacements in metres; callers choose how to consume the values."""
        from .simulation import impact_ages

        controls = (
            exciters
            if exciters is not None
            else tuple(
                ExciterState(f"exciter_{i}", source["amplitude"], source["frequency"])
                for i, source in enumerate(self.config.exciters, start=1)
            )
        )
        if len(controls) != len(self.phases):
            raise ValueError("Exciter state count does not match the prepared field")
        water, drip = self.config.water, self.config.drip
        temporal_phases = tuple(
            tau * source.frequency * water["time_scale"] * time for source in controls
        )
        ages = impact_ages(time, self.config)
        if self.np is not None:
            np = self.np
            values = np.zeros(len(self.points))
            for source, phase, attenuation, temporal in zip(
                controls, self.phases, self.attenuation, temporal_phases, strict=True
            ):
                values += source.amplitude * attenuation * np.sin(phase - temporal)
            values *= water["wave_amplitude"]
            for age in ages:
                distance = self.drop_radii - drip["wave_speed"] * age
                envelope = np.exp(-((distance / drip["ripple_width"]) ** 2))
                strength = (
                    drip["ripple_amplitude"]
                    * (1 - exp(-age / 0.04))
                    * exp(-drip["ripple_decay"] * age)
                )
                values += strength * envelope * np.sin(tau * distance / drip["ripple_wavelength"])
            values += (
                water["irregularity"]
                * np.sin(self.irregular_a + 0.35 * time)
                * np.sin(self.irregular_b - 0.23 * time)
            )
            return values * self.edge
        values = []
        for index, edge in enumerate(self.edge):
            value = water["wave_amplitude"] * sum(
                source.amplitude * attenuation[index] * sin(phase[index] - temporal)
                for source, phase, attenuation, temporal in zip(
                    controls, self.phases, self.attenuation, temporal_phases, strict=True
                )
            )
            for age in ages:
                distance = self.drop_radii[index] - drip["wave_speed"] * age
                envelope = exp(-((distance / drip["ripple_width"]) ** 2))
                value += (
                    drip["ripple_amplitude"]
                    * (1 - exp(-age / 0.04))
                    * exp(-drip["ripple_decay"] * age)
                    * envelope
                    * sin(tau * distance / drip["ripple_wavelength"])
                )
            value += (
                water["irregularity"]
                * sin(self.irregular_a[index] + 0.35 * time)
                * sin(self.irregular_b[index] - 0.23 * time)
            )
            values.append(float(edge * value))
        return values
