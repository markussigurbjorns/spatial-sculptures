"""Nonlocal incompressible potential-flow inertia in a graph-bounded water volume.

Ritz/Galerkin polynomials solve the 3D Laplace weak problem. Potential is zero
on the mean water surface; wall-normal velocity is prescribed on the wet floor.
Flat rectangular cells have rigid vertical sides. The bowl has no artificial
vertical sides. Gravity/capillary dynamics, compressibility, viscosity, static
prestress and moving contact lines remain outside this linear model.
NumPy is optional until assembly/evaluation; no Blender or NGSolve import.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import TYPE_CHECKING

from .fluid_loading import ColumnWater, floor_minimum, water_quadrature

if TYPE_CHECKING:
    import numpy as np

    from .structures import GraphSurface


@dataclass(frozen=True)
class PotentialSettings:
    horizontal_degree: int = 12
    vertical_degree: int = 2
    integration_order: int = 7
    integration_refinement: int = 2
    cells: int = 10

    def __post_init__(self):
        for name, minimum in (
            ("horizontal_degree", 0),
            ("vertical_degree", 0),
            ("integration_order", 4),
            ("integration_refinement", 1),
            ("cells", 2),
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")


@dataclass
class PotentialBasis:
    """(z-H) times Legendre polynomials; gradients have physical Cartesian units."""

    indices: np.ndarray
    origin_x: float
    scale_x: float
    scale_y: float
    level: float
    depth: float

    def evaluate(self, x, y, z):
        """Return potential shapes (metres) and XYZ gradients, point x basis."""
        import numpy as np
        from numpy.polynomial.legendre import legder, legval, legvander

        x, y, z = np.broadcast_arrays(x, y, z)
        xyz = (
            ((x.ravel() - self.origin_x) / self.scale_x, 1 / self.scale_x),
            (y.ravel() / self.scale_y, 1 / self.scale_y),
            (2 * (z.ravel() - self.level) / self.depth + 1, 2 / self.depth),
        )
        tables, derivatives = [], []
        for axis, (values, scale) in enumerate(xyz):
            maximum = int(self.indices[:, axis].max())
            tables.append(legvander(values, maximum))
            derivatives.append(
                np.column_stack(
                    [
                        legval(values, legder([0] * degree + [1])) * scale
                        for degree in range(maximum + 1)
                    ]
                )
            )
        px, py, pz = [table[:, self.indices[:, i]] for i, table in enumerate(tables)]
        dx, dy, dz = [table[:, self.indices[:, i]] for i, table in enumerate(derivatives)]
        height = z.ravel()[:, None] - self.level
        values = height * px * py * pz
        gradients = (height * dx * py * pz, height * px * dy * pz, px * py * (pz + height * dz))
        return values, gradients


def make_basis(
    surface: GraphSurface, water: ColumnWater, settings: PotentialSettings
) -> PotentialBasis:
    import numpy as np

    if water.depth_m <= 0:
        raise ValueError("A spatial fluid volume requires positive water depth")
    minimum = floor_minimum(surface)
    level = minimum + water.depth_m
    if surface.domain == "rectangle":
        ox, sx, sy = 0.0, surface.radius_x, surface.radius_y
    else:
        a, b = surface.rise, surface.asymmetry
        ox = -surface.radius_x * b / (a + sqrt(a * a + 3 * b * b))
        sx = surface.radius_x * sqrt(water.depth_m / (a - 3 * abs(b)))
        sy = surface.radius_y * sqrt(water.depth_m / (a - abs(b)))
    indices = np.array(
        [
            (i, j, k)
            for total in range(settings.horizontal_degree + 1)
            for i in range(total + 1)
            for j in [total - i]
            for k in range(settings.vertical_degree + 1)
        ],
        dtype=int,
    )
    return PotentialBasis(indices, ox, sx, sy, level, water.depth_m)


@dataclass
class PotentialSystem:
    surface: GraphSurface
    water: ColumnWater
    settings: PotentialSettings
    basis: PotentialBasis
    energy: np.ndarray
    x: np.ndarray
    y: np.ndarray
    measures: np.ndarray
    heights: np.ndarray
    volume_m3: float

    def solve_flux(self, normal_flux):
        """Solve prescribed upward graph flux; return coefficients and added inertia.

        normal_flux is point x wall-mode, with units of dimensionless wall shapes.
        Fluid outward flux on the bottom is minus this flux / graph Jacobian.
        """
        import numpy as np

        flux = np.asarray(normal_flux, dtype=float)
        if flux.ndim != 2 or flux.shape[0] != len(self.x) or not np.all(np.isfinite(flux)):
            raise ValueError("Finite quadrature-point x wall-mode flux required")
        coupling = np.zeros((len(self.basis.indices), flux.shape[1]))
        z = self.basis.level - self.heights
        for start in range(0, len(z), 128):
            part = slice(start, start + 128)
            values = self.basis.evaluate(self.x[part], self.y[part], z[part])[0]
            coupling -= values.T @ (self.measures[part, None] * flux[part])
        scale = 1 / np.sqrt(np.diag(self.energy))
        scaled = scale[:, None] * self.energy * scale[None, :]
        factor = np.linalg.cholesky(scaled)
        coefficients = scale[:, None] * np.linalg.solve(
            factor.T, np.linalg.solve(factor, scale[:, None] * coupling)
        )
        added_mass = self.water.density_kg_m3 * coupling.T @ coefficients
        residual = self.energy @ coefficients - coupling
        diagnostics = {
            "relative_equation_residual": float(
                np.linalg.norm(residual) / max(np.linalg.norm(coupling), 1e-30)
            ),
            "scaled_energy_condition_number": float(np.linalg.cond(scaled)),
            "added_mass_symmetry_relative": float(
                np.linalg.norm(added_mass - added_mass.T) / max(np.linalg.norm(added_mass), 1e-30)
            ),
        }
        return coefficients, (added_mass + added_mass.T) / 2, diagnostics

    def observations(self, coefficients, positions):
        """Pressure/acceleration weights (Pa per m/s²) at actual fluid XYZ positions."""
        import numpy as np

        points = np.asarray(positions, dtype=float)
        if points.ndim != 2 or points.shape[1] != 3 or not np.all(np.isfinite(points)):
            raise ValueError("Finite XYZ pressure positions required")
        x, y, z = points.T
        floor = self.surface.geometry(x, y)[0]
        if (
            not np.all(self.surface.contains(x, y))
            or np.any(z <= floor)
            or np.any(z >= self.basis.level)
        ):
            raise ValueError("Pressure probes must lie strictly inside the resting fluid volume")
        return -self.water.density_kg_m3 * self.basis.evaluate(x, y, z)[0] @ coefficients

    def surface_weights(self, coefficients, positions):
        """Linear mean-surface elevation/displacement weights from phi_z at z=H.

        Initial surface displacement is zero. Gravity/capillary waves and contact
        line motion are not solved; this is the kinematic pressure-release surface.
        """
        import numpy as np

        points = np.asarray(positions, dtype=float)
        if points.ndim != 2 or points.shape[1] != 2 or not np.all(np.isfinite(points)):
            raise ValueError("Finite XY mean-surface positions required")
        x, y = points.T
        if not np.all(self.surface.contains(x, y)) or np.any(
            self.surface.geometry(x, y)[0] > self.basis.level + 1e-12
        ):
            raise ValueError("Surface sample outside resting wet footprint")
        z = np.full_like(x, self.basis.level)
        return self.basis.evaluate(x, y, z)[1][2] @ coefficients


def assemble_potential(
    surface: GraphSurface, water: ColumnWater, settings: PotentialSettings | None = None
) -> PotentialSystem:
    """Assemble 3D kinetic energy over the actual wet graph volume, in bounded batches."""
    import numpy as np

    settings = PotentialSettings() if settings is None else settings
    basis = make_basis(surface, water, settings)
    x, y, measures, h = water_quadrature(
        surface,
        water,
        np.linspace(-surface.radius_x, surface.radius_x, settings.cells + 1),
        np.linspace(-surface.radius_y, surface.radius_y, settings.cells + 1),
        order=settings.integration_order,
        refinement=settings.integration_refinement,
    )
    # All trial gradients are polynomials in z; this rule integrates their products exactly.
    nodes, weights = np.polynomial.legendre.leggauss(settings.vertical_degree + 2)
    energy = np.zeros((len(basis.indices),) * 2)
    for start in range(0, len(x), 64):
        part = slice(start, start + 64)
        zz = basis.level - h[part, None] * (nodes + 1) / 2
        xx, yy = (
            np.broadcast_arrays(x[part, None], zz)[0],
            np.broadcast_arrays(y[part, None], zz)[0],
        )
        measure = (measures[part, None] * h[part, None] * weights / 2).ravel()
        gradients = basis.evaluate(xx.ravel(), yy.ravel(), zz.ravel())[1]
        for gradient in gradients:
            energy += gradient.T @ (measure[:, None] * gradient)
    return PotentialSystem(
        surface,
        water,
        settings,
        basis,
        (energy + energy.T) / 2,
        x,
        y,
        measures,
        h,
        float(measures @ h),
    )


def couple_wall_modes(fluid, wall_modes, *, chunk_points=128):
    """Project reusable Cartesian structural modes onto wet-wall volume flux."""
    import numpy as np

    if not isinstance(chunk_points, int) or isinstance(chunk_points, bool) or chunk_points <= 0:
        raise ValueError("Positive integer wall-evaluation chunk size required")
    if wall_modes.surface != fluid.surface:
        raise ValueError("Wall modes and fluid floor must use the same graph surface")
    count = len(wall_modes.frequencies)
    flux = np.empty((len(fluid.x), count))
    # Batched matrix multiplication avoids a slow three-index sum for every wall point.
    # Keep the existing structural/cache source unchanged and retain all Cartesian components.
    coefficients = wall_modes.coefficients.transpose(1, 0, 2).reshape(-1, 3 * count)
    for start in range(0, len(fluid.x), chunk_points):
        part = slice(start, start + chunk_points)
        basis = wall_modes.space.evaluate(fluid.x[part], fluid.y[part])[0]
        values = (basis @ coefficients).reshape(-1, 3, count)
        _, zx, zy, *_ = fluid.surface.geometry(fluid.x[part], fluid.y[part])
        flux[part] = values[:, 2] - zx[:, None] * values[:, 0] - zy[:, None] * values[:, 1]
    return fluid.solve_flux(flux)


def loaded_modal_modes(dry, added_mass, potentials, count):
    """Solve wet K/M in the retained dry modal subspace, preserving common shape units."""
    import numpy as np

    from .mode_cache import CachedModes
    from .structures import quadrature

    size = len(dry.frequencies)
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or not 0 < count <= size
        or added_mass.shape != (size, size)
        or potentials.shape[1] != size
    ):
        raise ValueError("Matching dry/modal-fluid dimensions and valid playback count required")
    mass = np.diag(dry.masses) + added_mass
    stiffness = dry.masses * (2 * np.pi * dry.frequencies) ** 2
    scale = 1 / np.sqrt(np.diag(mass))
    factor = np.linalg.cholesky(scale[:, None] * mass * scale[None, :])
    left = np.linalg.solve(factor, np.diag(scale**2 * stiffness))
    symmetric = np.linalg.solve(factor, left.T).T
    eigenvalues, vectors = np.linalg.eigh((symmetric + symmetric.T) / 2)
    if np.any(eigenvalues <= 0):
        raise ValueError("Nonpositive wet structural eigenvalue")
    transform = scale[:, None] * np.linalg.solve(factor.T, vectors[:, :count])
    coefficients = np.einsum("cbm,mn->cbn", dry.coefficients, transform, optimize=True)
    x, y, _ = quadrature(dry.surface, 8, 8, 5)
    shapes = np.einsum("pb,cbm->pcm", dry.space.evaluate(x, y)[0], coefficients, optimize=True)
    peaks = np.max(np.linalg.norm(shapes, axis=1), axis=0)
    coefficients /= peaks
    transform /= peaks
    frequencies = np.sqrt(eigenvalues[:count]) / (2 * np.pi)
    wet = CachedModes(
        dry.surface,
        dry.space,
        coefficients,
        frequencies,
        1 / peaks**2,
        {
            "model": "reduced dry shell + 3D pressure-release potential fluid",
            "dry_basis_count": size,
            "normalization": "unit sampled vector peak; SI kg",
        },
    )
    residual = stiffness[:, None] * transform - (mass @ transform) * eigenvalues[:count]
    diagnostics = {
        "maximum_relative_eigen_residual": float(
            np.linalg.norm(residual) / np.linalg.norm(stiffness[:, None] * transform)
        ),
        "modal_mass_orthogonality_error": float(
            np.max(np.abs(transform.T @ mass @ transform - np.diag(wet.masses)))
        ),
    }
    return wet, potentials @ transform, diagnostics
