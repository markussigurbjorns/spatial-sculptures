"""Small consumer-independent snapshots and scalar-field vocabulary.

These are artistic observables, not a solver interface or a calibrated physical
model. The producer documents the units and interpretation of each metric.
"""

from collections.abc import Callable
from dataclasses import dataclass

# A displacement field f(x_metres, y_metres, time_seconds) -> metres.
ScalarField = Callable[[float, float, float], float]


@dataclass(frozen=True)
class SensorState:
    """One named field sample; amplitude uses the producer's field units."""

    name: str
    amplitude: float


@dataclass(frozen=True)
class ExciterState:
    """Excitation controls: relative amplitude and configured frequency in Hz."""

    name: str
    amplitude: float
    frequency: float


@dataclass(frozen=True)
class FieldState:
    """One immutable snapshot, with ordered sensors/exciters and time in seconds.

    total_energy is currently a displacement-squared proxy, NOT energy in joules.
    max_displacement is a sampled absolute displacement, not a global bound.
    drop_impact is a short 0..1 control envelope, not a measured impulse force.
    """

    time: float
    sensor_states: tuple[SensorState, ...]
    exciter_states: tuple[ExciterState, ...]
    total_energy: float
    max_displacement: float
    drop_impact: float = 0.0
