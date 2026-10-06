"""Future flow: water/metal field -> virtual hydrophone -> processing -> another exciter.

Default builds never apply this feedback. Field samples currently represent visual
displacement, not hydrophone voltage or acoustic pressure. A future experiment must
choose that mapping and introduce explicit delay, filtering and gain control.
"""

from dataclasses import dataclass

from spatial_sculptures.simulation.feedback import bounded_gain
from spatial_sculptures.simulation.sensors import VirtualSensor

from .config import PrototypeConfig
from .simulation import displacement


@dataclass(frozen=True)
class FeedbackRoute:
    """An opt-in sensor-to-exciter route; indexes refer to config.exciters."""

    sensor_name: str
    exciter_index: int
    gain: float = 1.0
    limit: float = 0.1


def virtual_hydrophones(config: PrototypeConfig) -> list[VirtualSensor]:
    """Create virtual samples at the same XY positions as the visible hydrophones."""
    return [
        VirtualSensor(f"hydrophone_{i}", x, y)
        for i, (x, y) in enumerate(config.hydrophones, start=1)
    ]


def sample_field(config: PrototypeConfig, time: float) -> dict[str, float]:
    """Read the artistic field in metres; no feedback or scene mutation occurs."""

    def field(x: float, y: float, sample_time: float) -> float:
        return displacement(x, y, sample_time, config)

    return {sensor.name: sensor.sample(field, time) for sensor in virtual_hydrophones(config)}


def apply_feedback(samples: dict[str, float], routes: list[FeedbackRoute]) -> dict[int, float]:
    """Compute bounded target adjustments without applying them to the scene.

    These values are proposals for a future experiment to map into exciter controls.
    This function is stateless and supplies no delay, frequency shift or closed loop.
    """
    targets: dict[int, float] = {}
    for route in routes:
        if route.exciter_index < 0:
            raise ValueError("Exciter indexes must be non-negative")
        adjustment = bounded_gain(samples[route.sensor_name], route.gain, route.limit)
        targets[route.exciter_index] = targets.get(route.exciter_index, 0.0) + adjustment
    return targets
