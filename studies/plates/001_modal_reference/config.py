"""Provisional reference parameters, not predictions for the curved sculpture.

E and density: Cleveland-Cliffs 304/304L product sheet (2021), see paper bibliography.
Poisson ratio and modal damping are unmeasured assumptions. All edges simply supported.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from spatial_sculptures.simulation.plates import RectangularPlate


@dataclass(frozen=True)
class Profile:
    """Requested geometry; the reference accepts a flat rectangle only, in metres."""

    kind: str = "flat_rectangle"
    rise_m: float = 0.0
    mesh_path: str | None = None


@dataclass(frozen=True)
class Support:
    """Future local support request; position, contact width, stiffness and damping in SI."""

    position_m: tuple[float, float, float]
    contact_width_m: float
    stiffness_n_per_m: float
    damping_ns_per_m: float = 0.0


@dataclass(frozen=True)
class Supports:
    """The analytical model supports continuous simply supported edges only."""

    kind: str = "simply_supported_edges"
    contacts: tuple[Support, ...] = ()


@dataclass(frozen=True)
class Mounting:
    """Rigid finite-patch drive; attached mass/compliance need a later structural model."""

    force_direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    added_mass_kg: float = 0.0
    stiffness_n_per_m: float | None = None


@dataclass(frozen=True)
class Water:
    """Requested fill depth; positive depth is rejected by this dry model."""

    depth_m: float = 0.0


@dataclass(frozen=True)
class Impulse:
    """Uniform square contact patch, total transverse impulse in N*s."""

    time: float = 0.0
    x: float = -0.34
    y: float = 0.14
    impulse_ns: float = 0.03
    patch_width: float = 0.05
    mounting: Mounting = Mounting()


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
    mounting: Mounting = Mounting()


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
    profile: Profile = Profile()
    thickness_map: str | None = None  # Reserved request; uniform plate.thickness is implemented.
    supports: Supports = Supports()
    water: Water = Water()
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


def config_from_dict(parameters: dict) -> StudyConfig:
    """Restore an exported configuration, rejecting unknown keys rather than dropping them."""
    if not isinstance(parameters, dict):
        raise ValueError("Saved configuration must be a JSON object")
    values = dict(parameters)
    if "plate" in values:
        values["plate"] = RectangularPlate(**values["plate"])
    if "profile" in values:
        values["profile"] = Profile(**values["profile"])
    if "water" in values:
        values["water"] = Water(**values["water"])
    if "supports" in values:
        supports = dict(values["supports"])
        supports["contacts"] = tuple(
            Support(**{**v, "position_m": tuple(v["position_m"])})
            for v in supports.get("contacts", ())
        )
        values["supports"] = Supports(**supports)
    for key, event_type in (("impulses", Impulse), ("drives", Drive)):
        if key not in values:
            continue
        events = []
        for value in values[key]:
            event = dict(value)
            if "mounting" in event:
                mounting = dict(event["mounting"])
                mounting["force_direction"] = tuple(
                    mounting.get("force_direction", (0.0, 0.0, 1.0))
                )
                event["mounting"] = Mounting(**mounting)
            events.append(event_type(**event))
        values[key] = tuple(events)
    if "pickups" in values:
        values["pickups"] = tuple(tuple(v) for v in values["pickups"])
    return StudyConfig(**values)


def load_config(
    *, experiment: str | None = None, config_path: Path | None = None, driven: bool = False
) -> StudyConfig:
    """Select defaults, one explicit Python experiment, or a saved JSON configuration."""
    if config_path is not None:
        if experiment is not None or driven:
            raise ValueError(
                "A saved configuration cannot be combined with --experiment or --driven"
            )
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Saved configuration must be a JSON object")
        try:
            return config_from_dict(payload.get("parameters", payload))
        except (KeyError, TypeError) as error:
            raise ValueError(f"Invalid saved study configuration: {error}") from error
    config = default_config(driven=driven)
    if experiment is not None:
        from .experiments import configure_experiment

        config = configure_experiment(experiment, config)
    return config
