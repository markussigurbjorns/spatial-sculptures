"""Ordinary-Python resonant field and state; no Blender or transport dependencies.

The equations are artistic approximations, intentionally not CFD, FEM, or acoustics.
Blender and OSC consume the same state without owning the simulated system.
"""

from collections.abc import Sequence
from copy import deepcopy
from math import ceil, cos, floor, hypot, isfinite, sin, sqrt, tau

from spatial_sculptures.simulation.fields import ExciterState, FieldState, SensorState
from spatial_sculptures.simulation.sensors import VirtualSensor
from spatial_sculptures.simulation.waves import expanding_ripple, radial_wave

from .config import PrototypeConfig
from .sampling import FieldSampler


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


def virtual_hydrophones(config: PrototypeConfig) -> tuple[VirtualSensor, ...]:
    """Make genuine point samplers at the same positions as the visible hydrophones."""
    return tuple(
        VirtualSensor(f"hydrophone_{i}", x, y)
        for i, (x, y) in enumerate(config.hydrophones, start=1)
    )


class ResonantField:
    """A deterministic field that can be stepped and sampled without a visualizer.

    step(time) sets ABSOLUTE simulation time in seconds, not a time increment.
    Repeated times and backward steps reproduce identical states. Configuration is
    copied so independent experiments/consumers cannot mutate each other's controls.
    """

    def __init__(self, config: PrototypeConfig):
        config.validate()
        self.config = deepcopy(config)
        self.sensors = virtual_hydrophones(self.config)
        self.time = 0.0
        self._ages = impact_ages(self.time, self.config)
        self.state: FieldState | None = None
        water = self.config.water
        rings, segments = water["state_rings"], water["state_segments"]
        # Equal-area polar cells: these sample positions do not depend on Blender topology.
        self._metric_points = tuple(
            (
                water["radius_x"] * sqrt((ring + 0.5) / rings) * cos(tau * j / segments),
                water["radius_y"] * sqrt((ring + 0.5) / rings) * sin(tau * j / segments),
            )
            for ring in range(rings)
            for j in range(segments)
        )
        self._metric_sampler = self.prepare(self._metric_points)

    def prepare(
        self, points: Sequence[tuple[float, float]], *, use_numpy: bool | None = None
    ) -> FieldSampler:
        """Prepare fixed field samples; uses NumPy if available, otherwise cached Python math."""
        return FieldSampler(self.config, points, use_numpy=use_numpy)

    def sample(self, x: float, y: float, time: float | None = None) -> float:
        """Sample displacement in metres at the current or explicitly supplied time."""
        time = self.time if time is None else time
        ages = self._ages if time == self.time else impact_ages(time, self.config)
        return displacement(x, y, time, self.config, ages)

    def step(self, time: float) -> FieldState:
        """Produce hydrophone samples, exciter controls, and small artistic state metrics."""
        if not isfinite(time):
            raise ValueError("Simulation time must be finite")
        self.time = float(time)
        self._ages = impact_ages(self.time, self.config)
        samples = self._metric_sampler.sample(self.time)
        completed, phase = _drip_clock(self.time, self.config.drip["interval"])
        impact = (
            max(0.0, 1.0 - phase / self.config.drip["impact_duration"]) if completed >= 1 else 0.0
        )
        self.state = FieldState(
            time=self.time,
            sensor_states=tuple(
                SensorState(sensor.name, sensor.sample(self.sample, self.time))
                for sensor in self.sensors
            ),
            exciter_states=tuple(
                ExciterState(f"exciter_{i}", source["amplitude"], source["frequency"])
                for i, source in enumerate(self.config.exciters, start=1)
            ),
            # Mean squared displacement is a visual energy PROXY in m², not joules.
            total_energy=float(sum(value * value for value in samples) / len(samples)),
            max_displacement=float(max(abs(value) for value in samples)),
            drop_impact=impact,
        )
        return self.state
