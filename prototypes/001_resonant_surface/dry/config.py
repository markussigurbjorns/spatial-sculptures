"""Provisional dry basin parameters in SI; edit here or use a saved JSON configuration."""

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from spatial_sculptures.simulation.structures import GraphSurface, Material, Patch, Support


@dataclass(frozen=True)
class Exciter:
    patch: Patch
    added_mass_kg: float = 0.12
    direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    force_n: float = 0.0  # Prescribed harmonic force, not an electrical voltage.
    frequency_hz: float = 59.0
    phase: float = 0.0
    start: float = 0.0


@dataclass(frozen=True)
class Impulse:
    exciter: int = 0  # Zero-based index into configured mounting patches.
    time: float = 0.0
    impulse_ns: float = 0.03


@dataclass
class DryBasinConfig:
    surface: GraphSurface = GraphSurface(0.72, 0.58, 0.12, 0.006, 0.72)
    material: Material = Material()
    thickness: float = 0.005
    supports: tuple[Support, ...] = field(
        default_factory=lambda: tuple(
            Support(Patch(x, y, 0.035), (10000.0, 10000.0, 300000.0))
            for x in (-0.48, 0.48)
            for y in (-0.32, 0.32)
        )
    )
    exciters: tuple[Exciter, ...] = (
        Exciter(Patch(-0.34, 0.14, 0.05), frequency_hz=59.0),
        Exciter(Patch(0.31, 0.13, 0.05), frequency_hz=61.3, phase=1.7),
        Exciter(Patch(0.02, -0.32, 0.05), frequency_hz=57.8, phase=3.1),
    )
    impulses: tuple[Impulse, ...] = (Impulse(),)
    pickups: tuple[tuple[float, float], ...] = ((-0.20, -0.04), (0.25, -0.10))
    elements: tuple[int, int] = (8, 8)
    gauss_order: int = 5
    mode_count: int = 16
    damping_ratio: float = 0.005  # Assumed diagonal modal damping; not fitted support damping.
    water_depth_m: float = 0.0  # Positive depth is rejected until fluid coupling exists.
    duration: float = 2.0
    sample_rate: int = 48000
    fps: int = 30
    visual_gain: float = 1500.0  # Geometry only; audio/data remain in physical SI units.
    exposure_fraction: float = 0.5  # Average displacement over this fraction of a frame.
    exposure_samples: int = 8
    resolution: tuple[int, int] = (720, 540)
    rings: int = 16
    segments: int = 64


def from_dict(parameters: dict) -> DryBasinConfig:
    """Read explicit typed configuration; unknown fields are rejected by constructors."""
    values = dict(parameters)
    for key, constructor in (("surface", GraphSurface), ("material", Material)):
        if key in values:
            values[key] = constructor(**values[key])
    if "supports" in values:
        values["supports"] = tuple(
            Support(Patch(**v["patch"]), tuple(v["stiffness"])) for v in values["supports"]
        )
    if "exciters" in values:
        values["exciters"] = tuple(
            Exciter(
                **{
                    **v,
                    "patch": Patch(**v["patch"]),
                    "direction": tuple(v.get("direction", (0.0, 0.0, 1.0))),
                }
            )
            for v in values["exciters"]
        )
    if "impulses" in values:
        values["impulses"] = tuple(Impulse(**v) for v in values["impulses"])
    if "pickups" in values:
        values["pickups"] = tuple(tuple(v) for v in values["pickups"])
    for key in ("elements", "resolution"):
        if key in values:
            values[key] = tuple(values[key])
    return DryBasinConfig(**values)


def load_config(path: Path | None = None, experiment: str | None = None) -> DryBasinConfig:
    """Select editable defaults, an explicit experiment, or a complete saved snapshot."""
    if path is not None:
        if experiment is not None:
            raise ValueError("Choose either --config or --experiment")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Dry basin configuration must be a JSON object")
        return from_dict(payload.get("parameters", payload))
    config = DryBasinConfig()
    if experiment:
        directory = Path(__file__).parent / "experiments"
        names = sorted(v.stem for v in directory.glob("[0-9]*.py"))
        if experiment not in names:
            raise ValueError(f"Unknown dry experiment; choose from: {', '.join(names)}")
        config = importlib.import_module(f"{__package__}.experiments.{experiment}").configure(
            config
        )
    return config
