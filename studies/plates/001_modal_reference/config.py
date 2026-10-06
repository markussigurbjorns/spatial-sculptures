"""Provisional reference parameters, not predictions for the curved sculpture.

E and density: Cleveland-Cliffs 304/304L product sheet (2021), see paper bibliography.
Poisson ratio and modal damping are unmeasured assumptions. All edges simply supported.
"""

from dataclasses import dataclass, field

from spatial_sculptures.simulation.plates import RectangularPlate


@dataclass(frozen=True)
class Impulse:
    """Uniform square contact patch, total transverse impulse in N*s."""

    time: float = 0.0
    x: float = -0.34
    y: float = 0.14
    impulse_ns: float = 0.03
    patch_width: float = 0.05


@dataclass(frozen=True)
class Drive:
    """Uniform square contact patch, total transverse harmonic force in N."""

    x: float
    y: float
    frequency_hz: float
    force_n: float
    phase: float = 0.0
    start: float = 0.0
    patch_width: float = 0.05


@dataclass
class StudyConfig:
    plate: RectangularPlate = field(
        default_factory=lambda: RectangularPlate(
            length_x=1.44,
            length_y=1.16,
            thickness=0.005,
            youngs_modulus=193e9,
            density=8030.0,
            poisson_ratio=0.30,
        )
    )
    modes_per_axis: int = 6  # 36 retained modes; truncation is part of the experiment.
    damping_ratio: float = 0.005  # Assumed, not a measured material constant.
    impulses: tuple[Impulse, ...] = (Impulse(),)
    drives: tuple[Drive, ...] = ()  # Default is a ring-down, with no noise floor or feedback.
    pickups: tuple[tuple[float, float], ...] = ((-0.20, -0.04), (0.25, -0.10))
    duration: float = 4.0
    sample_rate: int = 48000
    display_fps: int = 30
    visual_time_scale: float = (
        0.02  # Explicit slow motion: 1 visual second = 0.02 physical seconds.
    )
    visual_gain: float = 2000.0  # Displacement magnification only; audio/data stay in SI units.


def default_config(*, driven: bool = False) -> StudyConfig:
    """Select impulse ring-down, or add three drives at the sculpture's proposed positions."""
    config = StudyConfig()
    if driven:
        config.drives = (
            Drive(-0.34, 0.14, 59.0, 1.0),
            Drive(0.31, 0.13, 61.3, 0.85, phase=1.7),
            Drive(0.02, -0.32, 57.8, 0.95, phase=3.1),
        )
    return config
