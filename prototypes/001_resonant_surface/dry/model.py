"""Structural solve/cache and pure-Python modal response of the dry sculpture."""

import hashlib
import json
from dataclasses import asdict, replace
from math import isfinite
from pathlib import Path

import numpy as np

from spatial_sculptures.simulation.modal import Mode
from spatial_sculptures.simulation.mode_bank import ModalResponse
from spatial_sculptures.simulation.mode_cache import load_modes, modes_from_system, save_modes
from spatial_sculptures.simulation.structures import AttachedMass, assemble_shell

from .config import DryBasinConfig

ROOT = Path(__file__).resolve().parents[3]


def structural_parameters(config: DryBasinConfig) -> dict:
    """Only settings that change eigenmodes; force/frequency/camera changes reuse the cache."""
    return {
        "surface": asdict(config.surface),
        "material": asdict(config.material),
        "thickness": config.thickness,
        "supports": [asdict(s) for s in config.supports],
        "attached_masses": [
            {"patch": asdict(e.patch), "mass_kg": e.added_mass_kg}
            for e in config.exciters
            if e.added_mass_kg != 0
        ],
        "elements": config.elements,
        "gauss_order": config.gauss_order,
        "mode_count": config.mode_count,
        "eigensolver": config.eigensolver,
        "patch_refinement": config.patch_refinement,
    }


def cache_identity(config: DryBasinConfig) -> tuple[str, dict]:
    """Hash structural parameters and solver source to prevent silently stale modes."""
    names = ("splines.py", "structures.py", "mode_cache.py")
    sources = {
        name: hashlib.sha256(
            (ROOT / "src/spatial_sculptures/simulation" / name).read_bytes()
        ).hexdigest()
        for name in names
    }
    identity = {"parameters": structural_parameters(config), "source_sha256": sources}
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(), identity


def validate_config(config: DryBasinConfig) -> None:
    """Validate physics and sampling before creating artifacts or launching Blender."""
    if config.surface.domain != "ellipse":
        raise ValueError("Dry basin visualization currently requires an elliptical graph surface")
    if config.water_depth_m != 0:
        raise ValueError("Dry basin does not support water_depth_m != 0; no fluid loading/pressure")
    if config.eigensolver not in ("numpy", "scipy"):
        raise ValueError("eigensolver must be numpy or scipy")
    if (
        not isinstance(config.patch_refinement, int)
        or isinstance(config.patch_refinement, bool)
        or not 0 <= config.patch_refinement <= 3
    ):
        raise ValueError("patch_refinement must be an integer from 0 to 3")
    if not isfinite(config.damping_ratio) or not 0 <= config.damping_ratio < 1:
        raise ValueError("Modal damping ratio must lie in [0,1)")
    if not isfinite(config.duration) or config.duration <= 0:
        raise ValueError("Duration must be finite and positive")
    if config.audio_stop_hz is not None and (
        not isfinite(config.audio_stop_hz) or not 0 < config.audio_stop_hz < config.sample_rate / 2
    ):
        raise ValueError("audio_stop_hz must be positive and below audio Nyquist")
    for name in (
        "fps",
        "sample_rate",
        "mode_count",
        "gauss_order",
        "rings",
        "segments",
        "exposure_samples",
    ):
        value = getattr(config, name)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if config.gauss_order < 4 or config.segments < 3:
        raise ValueError("Gauss order >=4 and segments >=3 required")
    if len(config.resolution) != 2 or any(
        not isinstance(v, int) or v <= 0 for v in config.resolution
    ):
        raise ValueError("Two positive resolution dimensions required")
    if not isfinite(config.visual_gain) or config.visual_gain <= 0:
        raise ValueError("Visual gain must be finite and positive")
    if not isfinite(config.exposure_fraction) or not 0 <= config.exposure_fraction <= 1:
        raise ValueError("Exposure fraction must lie in [0,1]")
    if not config.pickups or any(
        len(p) != 2 or not all(isfinite(v) for v in p) or not config.surface.contains(*p)
        for p in config.pickups
    ):
        raise ValueError("At least one finite pickup on the surface required")
    if not config.exciters:
        raise ValueError("At least one mounting patch required")
    for event in config.impulses:
        if not isinstance(event.exciter, int) or not 0 <= event.exciter < len(config.exciters):
            raise ValueError("Impulse must refer to an existing zero-based exciter index")
        if not all(isfinite(v) for v in (event.time, event.impulse_ns)) or event.time < 0:
            raise ValueError("Finite impulse and nonnegative impact time required")
    for exciter in config.exciters:
        if (
            len(exciter.direction) != 3
            or not all(isfinite(v) for v in exciter.direction)
            or not np.isclose(sum(v * v for v in exciter.direction), 1)
        ):
            raise ValueError("Exciter direction must be a finite unit three-vector")
        if not all(
            isfinite(v)
            for v in (
                exciter.added_mass_kg,
                exciter.force_n,
                exciter.frequency_hz,
                exciter.phase,
                exciter.start,
            )
        ):
            raise ValueError("Finite exciter parameters required")
        if min(exciter.added_mass_kg, exciter.frequency_hz, exciter.start) < 0:
            raise ValueError("Mass/frequency/start must be nonnegative")


def get_modes(config: DryBasinConfig, cache_directory: Path, *, rebuild: bool = False):
    """Compute the eigenproblem once, otherwise load its matching portable mode archive."""
    validate_config(config)
    key, identity = cache_identity(config)
    path = cache_directory / f"dry_modes_{key[:20]}.npz"
    if path.is_file() and not rebuild:
        return load_modes(path, expected_key=key), path, True
    if not rebuild:
        # An offline convergence study often already computed a larger bank of
        # exactly this structure. Its leading modes can serve a smaller playback
        # bank without another eigenproblem. Source/physical identity must match.
        eligible = []
        # JSON archives turn tuples into lists; compare their canonical representation.
        expected_parameters = json.loads(json.dumps(identity["parameters"]))
        for candidate in cache_directory.glob("dry_modes_*.npz"):
            with np.load(candidate, allow_pickle=False) as archive:
                metadata = json.loads(str(archive["metadata"]))
            parameters = metadata.get("parameters", {})
            count = parameters.get("mode_count", 0)
            if (
                count >= config.mode_count
                and metadata.get("source_sha256") == identity["source_sha256"]
                and parameters == {**expected_parameters, "mode_count": count}
            ):
                eligible.append((count, candidate))
        if eligible:
            _, candidate = min(eligible)
            original = load_modes(candidate)
            count = config.mode_count
            modes = replace(
                original,
                coefficients=original.coefficients[:, :, :count].copy(),
                frequencies=original.frequencies[:count].copy(),
                masses=original.masses[:count].copy(),
                metadata={
                    **original.metadata,
                    **identity,
                    "cache_key": key,
                    "derived_from_cache_key": original.metadata["cache_key"],
                },
            )
            save_modes(path, modes)
            return modes, path, True
    system = assemble_shell(
        config.surface,
        config.material,
        config.thickness,
        elements=config.elements,
        gauss_order=config.gauss_order,
        patch_refinement=config.patch_refinement,
        supports=config.supports,
        attached_masses=tuple(
            AttachedMass(e.patch, e.added_mass_kg) for e in config.exciters if e.added_mass_kg
        ),
    )
    modes = modes_from_system(
        system, config.mode_count, {**identity, "cache_key": key}, backend=config.eigensolver
    )
    save_modes(path, modes)
    return modes, path, False


class DryBasinSimulation:
    """The same modal response drives vector deformation and point contact-velocity audio."""

    def __init__(self, config: DryBasinConfig, cached):
        validate_config(config)
        self.config, self.cached = config, cached
        self.modes = tuple(
            Mode(f"shell_{i + 1}", float(f), float(m), config.damping_ratio)
            for i, (f, m) in enumerate(zip(cached.frequencies, cached.masses, strict=True))
        )
        projections = [cached.patch_weights(e.patch, e.direction) for e in config.exciters]
        impulses, drives = [], []
        for i in range(len(self.modes)):
            impulses.append(
                tuple(
                    (event.time, event.impulse_ns * projections[event.exciter][i])
                    for event in config.impulses
                )
            )
            drives.append(
                tuple(
                    (e.start, e.frequency_hz, e.phase, e.force_n * p[i])
                    for e, p in zip(config.exciters, projections, strict=True)
                    if e.force_n
                )
            )
        self.response = ModalResponse(self.modes, impulses, drives)
        self.pickup_weights = cached.weights(*np.asarray(config.pickups).T)[:, 2, :]

    def step(self, time: float):
        """Return modal SI state and mechanical energy of the retained structure."""
        return self.response.step(time)

    def trace(self, times):
        return self.response.trace(times, use_numpy=True)

    def pickup_velocities(self, modal_velocities):
        """Global vertical velocity in m/s; ideal metal contacts, not hydrophones."""
        return self.pickup_weights @ modal_velocities
