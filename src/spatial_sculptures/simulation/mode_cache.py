"""Portable mode shapes with explicit normalization; no Blender or solver at playback."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .splines import SplineSpace
from .structures import GraphSurface, Patch, ShellSystem, patch_average, quadrature, solve_modes


@dataclass
class CachedModes:
    surface: GraphSurface
    space: SplineSpace
    coefficients: np.ndarray  # component x active basis x mode, dimensionless.
    frequencies: np.ndarray
    masses: np.ndarray  # kg, matched to the sampled unit-peak vector shapes.
    metadata: dict

    def weights(self, x, y):
        """Vector mode shapes at points, shape (point, component, mode)."""
        x, y = np.atleast_1d(x), np.atleast_1d(y)
        if x.shape != y.shape or not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            raise ValueError("Finite paired XY coordinates required")
        if not np.all(self.surface.contains(x, y)):
            raise ValueError("Sensor/visualization points must lie on the surface")
        return np.einsum("pb,cbm->pcm", self.space.evaluate(x, y)[0], self.coefficients)

    def patch_weights(self, patch: Patch, direction=(0.0, 0.0, 1.0)):
        """Project a total force/impulse through a rigid patch's unit drive direction."""
        direction = np.asarray(direction, dtype=float)
        if (
            direction.shape != (3,)
            or not np.all(np.isfinite(direction))
            or not np.isclose(np.linalg.norm(direction), 1)
        ):
            raise ValueError("Force direction must be a finite unit 3-vector")
        mean = patch_average(self.space, self.surface, patch)
        return np.einsum("b,cbm,c->m", mean, self.coefficients, direction)


def modes_from_system(system: ShellSystem, mode_count: int, metadata: dict) -> CachedModes:
    """Normalize mode shapes and masses together; retain numerical diagnostics."""
    frequencies, coefficients, diagnostics = solve_modes(system, mode_count)
    vector = np.zeros((3, len(system.space.active), mode_count))
    for block, component in enumerate(system.components):
        vector[component] = coefficients[
            block * len(system.space.active) : (block + 1) * len(system.space.active)
        ]
    x, y, _ = quadrature(system.surface, 8, 8, 5)
    values = np.einsum("pb,cbm->pcm", system.space.evaluate(x, y)[0], vector)
    peaks = np.max(np.linalg.norm(values, axis=1), axis=0)
    vector /= peaks
    return CachedModes(
        system.surface,
        system.space,
        vector,
        frequencies,
        1 / peaks**2,
        {
            **metadata,
            "diagnostics": diagnostics,
            "normalization": "unit sampled vector peak on 8x8/order-5 grid; modal masses in kg",
            "normalization_grid": [8, 8, 5],
        },
    )


def save_modes(path: Path, modes: CachedModes) -> None:
    """Save arrays plus JSON metadata without Python pickle objects."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        np.savez_compressed(
            handle,
            coefficients=modes.coefficients,
            frequencies=modes.frequencies,
            masses=modes.masses,
            knots_x=modes.space.knots_x,
            knots_y=modes.space.knots_y,
            active=modes.space.active,
            metadata=json.dumps({**modes.metadata, "schema": 1, "surface": asdict(modes.surface)}),
        )


def load_modes(path: Path, *, expected_key: str | None = None) -> CachedModes:
    """Load a validated archive; optionally reject stale structural/source parameters."""
    with np.load(path, allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata"]))
        if metadata.get("schema") != 1 or (
            expected_key is not None and metadata.get("cache_key") != expected_key
        ):
            raise ValueError("Mode cache schema/key mismatch; rebuild numerical modes")
        modes = CachedModes(
            GraphSurface(**metadata["surface"]),
            SplineSpace(
                archive["knots_x"].copy(), archive["knots_y"].copy(), archive["active"].copy()
            ),
            archive["coefficients"].copy(),
            archive["frequencies"].copy(),
            archive["masses"].copy(),
            metadata,
        )
    count = len(modes.frequencies)
    if modes.coefficients.shape != (3, len(modes.space.active), count) or modes.masses.shape != (
        count,
    ):
        raise ValueError("Inconsistent cached modal array dimensions")
    if not count or not all(
        np.all(np.isfinite(a)) for a in (modes.coefficients, modes.frequencies, modes.masses)
    ):
        raise ValueError("Empty or non-finite mode cache")
    if (
        np.any(modes.frequencies <= 0)
        or np.any(modes.masses <= 0)
        or np.any(np.diff(modes.frequencies) < 0)
    ):
        raise ValueError("Cache requires positive masses and ascending positive frequencies")
    return modes
