"""Linear gravity/capillary free-surface modes coupled to a retained structural bank.

An incompressible Neumann potential solves wall and surface volume flux together.
Surface gravity/capillary energy closes the dynamics; no Blender or audio server.
The shell equilibrium/stiffness is frozen: hydrostatic prestress and elastogravity
wall-traction corrections are not included. This is not a free rigid-body model.
NumPy is imported only when numerical assembly/evaluation is requested.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, pi, sqrt, tanh
from typing import TYPE_CHECKING

from .fluid_loading import ColumnWater, water_quadrature
from .fluid_potential import PotentialSettings, make_basis

if TYPE_CHECKING:
    import numpy as np


def gravity_capillary_frequency(
    wavenumber: float,
    depth: float,
    density: float = 1000.0,
    gravity: float = 9.81,
    surface_tension: float = 0.072,
) -> float:
    """Finite-depth rigid-cell dispersion in Hz; k=0 gives the volume/constant mode.

    omega² = (g*k + sigma*k³/rho)*tanh(k*h). This is a reference equation,
    not a dispersion relation for an arbitrary curved, moving vessel.
    """
    if (
        not all(isfinite(v) for v in (wavenumber, depth, density, gravity, surface_tension))
        or min(depth, density) <= 0
        or min(wavenumber, gravity, surface_tension) < 0
    ):
        raise ValueError("Finite nonnegative k/g/tension and positive depth/density required")
    return sqrt(
        (gravity * wavenumber + surface_tension * wavenumber**3 / density)
        * tanh(wavenumber * depth)
    ) / (2 * pi)


def _legendre_tables(values, maximum, scale):
    import numpy as np
    from numpy.polynomial.legendre import legder, legval, legvander

    return legvander(values, maximum), np.column_stack(
        [legval(values, legder([0] * i + [1])) * scale for i in range(maximum + 1)]
    )


@dataclass
class FreePotentialBasis:
    """Metre-valued polynomial potentials, with zero area-mean trace as pressure gauge."""

    indices: np.ndarray
    origin_x: float
    scale_x: float
    scale_y: float
    level: float
    depth: float
    trace_means: np.ndarray

    def evaluate(self, x, y, z):
        """Potential shapes (m) and Cartesian gradients at paired physical positions."""
        import numpy as np

        x, y, z = np.broadcast_arrays(x, y, z)
        coordinates = (
            ((x.ravel() - self.origin_x) / self.scale_x, 1 / self.scale_x),
            (y.ravel() / self.scale_y, 1 / self.scale_y),
            (2 * (z.ravel() - self.level) / self.depth + 1, 2 / self.depth),
        )
        tables = [
            _legendre_tables(v, int(self.indices[:, i].max()), scale)
            for i, (v, scale) in enumerate(coordinates)
        ]
        px, py, pz = [table[0][:, self.indices[:, i]] for i, table in enumerate(tables)]
        dx, dy, dz = [table[1][:, self.indices[:, i]] for i, table in enumerate(tables)]
        return (
            self.depth * px * py * pz - self.trace_means,
            (self.depth * dx * py * pz, self.depth * px * dy * pz, self.depth * px * py * dz),
        )


@dataclass
class SurfaceBasis:
    """Dimensionless, zero-mean, area-orthonormal elevation shapes on the wet footprint."""

    indices: np.ndarray
    origin_x: float
    scale_x: float
    scale_y: float
    means: np.ndarray
    transform: np.ndarray

    def evaluate(self, x, y):
        """Return elevation shapes and their two physical horizontal derivatives."""
        import numpy as np

        x, y = np.broadcast_arrays(x, y)
        px, dx = _legendre_tables(
            (x.ravel() - self.origin_x) / self.scale_x,
            int(self.indices[:, 0].max()),
            1 / self.scale_x,
        )
        py, dy = _legendre_tables(
            y.ravel() / self.scale_y, int(self.indices[:, 1].max()), 1 / self.scale_y
        )
        i, j = self.indices.T
        return (
            (px[:, i] * py[:, j] - self.means) @ self.transform,
            ((dx[:, i] * py[:, j]) @ self.transform, (px[:, i] * dy[:, j]) @ self.transform),
        )


def make_surface_basis(basis, x, y, measures, degree=6):
    """Remove the volume-changing constant mode and orthonormalize area-mean shapes."""
    import numpy as np

    if not isinstance(degree, int) or isinstance(degree, bool) or degree < 1:
        raise ValueError("Positive integer surface degree required")
    indices = np.array([(i, total - i) for total in range(1, degree + 1) for i in range(total + 1)])
    result = SurfaceBasis(
        indices,
        basis.origin_x,
        basis.scale_x,
        basis.scale_y,
        np.zeros(len(indices)),
        np.eye(len(indices)),
    )
    raw = result.evaluate(x, y)[0]
    result.means = measures @ raw / measures.sum()
    raw -= result.means
    gram = raw.T @ (measures[:, None] * raw) / measures.sum()
    factor = np.linalg.cholesky((gram + gram.T) / 2)
    result.transform = np.linalg.solve(factor.T, np.eye(len(indices)))
    return result


@dataclass
class FreeSurfaceSystem:
    surface: object
    water: ColumnWater
    basis: FreePotentialBasis
    surface_basis: object
    mass: np.ndarray
    stiffness: np.ndarray
    surface_stiffness: np.ndarray
    potentials: np.ndarray
    elevations: np.ndarray  # constant + relative elevation basis x generalized coordinates
    wall_count: int
    area_m2: float
    volume_m3: float
    gravity: float
    surface_tension: float
    diagnostics: dict

    def surface_weights(self, positions):
        """Elevation/generalized-coordinate weights in the resting wet footprint."""
        import numpy as np

        xy = np.asarray(positions, dtype=float)
        if (
            xy.ndim != 2
            or xy.shape[1] != 2
            or not np.all(np.isfinite(xy))
            or not np.all(self.surface.contains(*xy.T))
            or np.any(self.surface.geometry(*xy.T)[0] > self.basis.level + 1e-12)
        ):
            raise ValueError("Finite XY surface positions in the resting wet footprint required")
        values = self.surface_basis.evaluate(*xy.T)[0]
        return np.column_stack((np.ones(len(xy)), values)) @ self.elevations

    def pressure_weights(self, positions):
        """Return acceleration and displacement weights for pressure perturbation, Pa.

        p' = -rho*chi_ddot + rho*g*mean(eta), with mean top chi=0 as gauge.
        Both terms are required; hydrostatic resting pressure is not included.
        """
        import numpy as np

        xyz = np.asarray(positions, dtype=float)
        if (
            xyz.ndim != 2
            or xyz.shape[1] != 3
            or not np.all(np.isfinite(xyz))
            or not np.all(self.surface.contains(*xyz[:, :2].T))
            or np.any(xyz[:, 2] <= self.surface.geometry(*xyz[:, :2].T)[0])
            or np.any(xyz[:, 2] >= self.basis.level)
        ):
            raise ValueError("Pressure positions must lie strictly inside the resting fluid")
        a = -self.water.density_kg_m3 * self.basis.evaluate(*xyz.T)[0] @ self.potentials
        q = np.broadcast_to(
            self.water.density_kg_m3 * self.gravity * self.elevations[0], a.shape
        ).copy()
        return a, q


def assemble_free_surface(
    surface,
    water: ColumnWater,
    *,
    settings: PotentialSettings | None = None,
    surface_degree=6,
    gravity=9.81,
    surface_tension=0.072,
    wall_modes=None,
    surface_basis=None,
) -> FreeSurfaceSystem:
    """Assemble reciprocal kinetic coupling and free-surface restoring energy.

    Mean surface displacement follows integrated wall flux exactly. Remaining
    elevation shapes have zero mean. Natural capillary edge condition is zero
    normal slope; physical wetting/contact-line laws remain outside this model.
    """
    import numpy as np

    if (
        not all(isfinite(v) for v in (gravity, surface_tension))
        or min(gravity, surface_tension) < 0
        or gravity + surface_tension == 0
    ):
        raise ValueError("Nonnegative gravity/tension, with a restoring mechanism, required")
    settings = settings or PotentialSettings(12, 3)
    template = make_basis(surface, water, settings)
    # Excluding the global constant removes the Neumann nullspace.
    indices = template.indices[np.any(template.indices != 0, axis=1)]
    basis = FreePotentialBasis(
        indices,
        template.origin_x,
        template.scale_x,
        template.scale_y,
        template.level,
        template.depth,
        np.zeros(len(indices)),
    )
    x, y, w, h = water_quadrature(
        surface,
        water,
        np.linspace(-surface.radius_x, surface.radius_x, settings.cells + 1),
        np.linspace(-surface.radius_y, surface.radius_y, settings.cells + 1),
        order=settings.integration_order,
        refinement=settings.integration_refinement,
    )
    if not len(w):
        raise ValueError("Positive resting fluid volume required")
    area = float(w.sum())
    raw_means = np.zeros(len(indices))
    for start in range(0, len(x), 128):
        part = slice(start, start + 128)
        raw_means += w[part] @ basis.evaluate(x[part], y[part], basis.level)[0] / area
    basis.trace_means = raw_means
    elevation_basis = surface_basis or make_surface_basis(basis, x, y, w, surface_degree)
    eta, derivatives = elevation_basis.evaluate(x, y)
    if np.max(abs(w @ eta)) > 1e-9 * area:
        raise ValueError("Relative elevation shapes must have zero area mean")
    nwall = 0 if wall_modes is None else len(wall_modes.frequencies)
    if wall_modes is not None and wall_modes.surface != surface:
        raise ValueError("Wall and fluid must use the same graph")
    flux = np.zeros((len(x), nwall))
    if nwall:
        coefficients = wall_modes.coefficients.transpose(1, 0, 2).reshape(-1, 3 * nwall)
        for start in range(0, len(x), 128):
            part = slice(start, start + 128)
            values = (wall_modes.space.evaluate(x[part], y[part])[0] @ coefficients).reshape(
                -1, 3, nwall
            )
            _, bx, by, *_ = surface.geometry(x[part], y[part])
            flux[part] = values[:, 2] - bx[:, None] * values[:, 0] - by[:, None] * values[:, 1]
    mean = w @ flux / area
    elevations = np.zeros((eta.shape[1] + 1, nwall + eta.shape[1]))
    elevations[0, :nwall] = mean
    elevations[1:, nwall:] = np.eye(eta.shape[1])
    energy = np.zeros((len(indices), len(indices)))
    coupling = np.zeros((len(indices), elevations.shape[1]))
    nodes, weights = np.polynomial.legendre.leggauss(settings.vertical_degree + 1)
    for start in range(0, len(x), 64):
        part = slice(start, start + 64)
        z = basis.level - h[part, None] * (nodes + 1) / 2
        xx, yy = np.broadcast_arrays(x[part, None], z)[0], np.broadcast_arrays(y[part, None], z)[0]
        measure = (w[part, None] * h[part, None] * weights / 2).ravel()
        for gradient in basis.evaluate(xx, yy, z)[1]:
            energy += gradient.T @ (measure[:, None] * gradient)
        top = basis.evaluate(x[part], y[part], basis.level)[0]
        bottom = basis.evaluate(x[part], y[part], basis.level - h[part])[0]
        coupling[:, :nwall] += top.T @ (w[part, None] * np.broadcast_to(mean, flux[part].shape))
        coupling[:, :nwall] -= bottom.T @ (w[part, None] * flux[part])
        coupling[:, nwall:] += top.T @ (w[part, None] * eta[part])
    energy = (energy + energy.T) / 2
    scale = 1 / np.sqrt(np.diag(energy))
    scaled = scale[:, None] * energy * scale[None, :]
    factor = np.linalg.cholesky(scaled)
    potentials = scale[:, None] * np.linalg.solve(
        factor.T, np.linalg.solve(factor, scale[:, None] * coupling)
    )
    mass = water.density_kg_m3 * coupling.T @ potentials
    symmetry = float(np.linalg.norm(mass - mass.T) / max(np.linalg.norm(mass), 1e-30))
    mass = (mass + mass.T) / 2
    if nwall:
        mass[np.arange(nwall), np.arange(nwall)] += wall_modes.masses
    eta_all = np.column_stack((np.ones(len(x)), eta))
    surface_stiffness = water.density_kg_m3 * gravity * (eta_all.T @ (w[:, None] * eta_all))
    surface_stiffness[1:, 1:] += surface_tension * sum(d.T @ (w[:, None] * d) for d in derivatives)
    restoring = elevations.T @ surface_stiffness @ elevations
    stiffness = restoring.copy()
    if nwall:
        stiffness[np.arange(nwall), np.arange(nwall)] += (
            wall_modes.masses * (2 * np.pi * wall_modes.frequencies) ** 2
        )
    diagnostics = {
        "fluid_equation_relative_residual": float(
            np.linalg.norm(energy @ potentials - coupling) / max(np.linalg.norm(coupling), 1e-30)
        ),
        "fluid_scaled_condition_number": float(np.linalg.cond(scaled)),
        "fluid_mass_symmetry_relative": symmetry,
        "maximum_relative_surface_mean": float(np.max(abs(w @ eta)) / area),
        "flux_compatibility_relative": float(
            np.max(abs(area * mean - w @ flux)) / max(np.linalg.norm(w @ flux), 1e-30)
        )
        if nwall
        else 0.0,
        "potential_functions": len(indices),
        "surface_functions": eta.shape[1],
        "wall_functions": nwall,
    }
    return FreeSurfaceSystem(
        surface,
        water,
        basis,
        elevation_basis,
        mass,
        (stiffness + stiffness.T) / 2,
        (restoring + restoring.T) / 2,
        potentials,
        elevations,
        nwall,
        area,
        float(w @ h),
        gravity,
        surface_tension,
        diagnostics,
    )


def solve_free_modes(system: FreeSurfaceSystem, count: int):
    """Solve the positive symmetric generalized eigenproblem with unit modal masses."""
    import numpy as np

    if not isinstance(count, int) or isinstance(count, bool) or not 0 < count <= len(system.mass):
        raise ValueError("Valid retained coupled mode count required")
    scale = 1 / np.sqrt(np.diag(system.mass))
    factor = np.linalg.cholesky(scale[:, None] * system.mass * scale[None, :])
    stiffness = scale[:, None] * system.stiffness * scale[None, :]
    left = np.linalg.solve(factor, stiffness)
    reduced = np.linalg.solve(factor, left.T).T
    eigenvalues, vectors = np.linalg.eigh((reduced + reduced.T) / 2)
    if np.any(eigenvalues <= 0):
        raise ValueError("Nonpositive coupled eigenvalue; check restoring terms and constraints")
    transform = scale[:, None] * np.linalg.solve(factor.T, vectors[:, :count])
    frequencies = np.sqrt(eigenvalues[:count]) / (2 * np.pi)
    residual = system.stiffness @ transform - (system.mass @ transform) * eigenvalues[:count]
    diagnostics = {
        "eigen_relative_residual": float(
            np.linalg.norm(residual) / np.linalg.norm(system.stiffness @ transform)
        ),
        "mass_orthogonality_error": float(
            np.max(abs(transform.T @ system.mass @ transform - np.eye(count)))
        ),
    }
    return frequencies, transform, diagnostics
