"""Provisional shallow-column water inertia on graph shells (optional NumPy).

This is the local, pressure-release shallow-layer approximation, not a fluid
solver. It neglects lateral flow, gravity/capillary waves, fluid damping and
hydrostatic prestress. Its finite-depth Fourier reference is provided separately
so approximation error can be distinguished from numerical integration error.
No hydrophone pressure or wet contact-band accuracy is implied.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite, sqrt, tanh
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

    from .structures import GraphSurface, ShellSystem


@dataclass(frozen=True)
class ColumnWater:
    """SI water settings; depth is measured above the lowest point of the graph."""

    depth_m: float = 0.065
    density_kg_m3: float = 1000.0

    def __post_init__(self):
        if not isfinite(self.depth_m) or self.depth_m < 0:
            raise ValueError("Water depth must be finite and nonnegative")
        if not isfinite(self.density_kg_m3) or self.density_kg_m3 <= 0:
            raise ValueError("Water density must be finite and positive")


@dataclass
class ColumnLoading:
    """Added inertia and integrated physical water volume; no fluid state."""

    matrix: np.ndarray
    volume_m3: float
    wetted_projected_area_m2: float
    surface_level_m: float
    water_mass_kg: float


def pressure_release_mass_per_area(wavenumber: float, water: ColumnWater) -> float:
    """Exact Fourier added mass rho*tanh(k*h)/k, kg/m²; k=0 has limit rho*h.

    Incompressible inviscid fluid, flat floor, pressure-release top and separated
    lateral Fourier mode. This is not a rigid-wall tank or a sloshing solution.
    """
    if not isfinite(wavenumber) or wavenumber < 0:
        raise ValueError("Wavenumber must be finite and nonnegative")
    if wavenumber == 0:
        return water.density_kg_m3 * water.depth_m
    return water.density_kg_m3 * tanh(wavenumber * water.depth_m) / wavenumber


def floor_minimum(surface: GraphSurface) -> float:
    """Lowest height of a flat rectangle or strictly convex elliptical graph bowl.

    Restrict supported geometry rather than assigning a fictitious water volume
    to a saddle, open tilted plate or overflowing vessel. The shell mid-surface
    is used as the fluid floor; wall thickness offsets are not modeled yet.
    """
    if surface.domain == "rectangle" and surface.rise == surface.asymmetry == 0:
        return surface.center_z
    if surface.domain != "ellipse" or surface.rise <= 3 * abs(surface.asymmetry):
        raise ValueError("Column water requires a flat rectangle or strictly convex ellipse bowl")
    a, b = surface.rise, surface.asymmetry
    xx = -b / (a + sqrt(a * a + 3 * b * b))
    return float(surface.geometry(xx * surface.radius_x, 0)[0])


def _real_roots(coefficients):
    import numpy as np

    return [
        float(root.real)
        for root in np.roots(np.trim_zeros(coefficients, "f"))
        if abs(root.imag) < 1e-10 and -1 < root.real < 1
    ]


def _subdivide(edges, refinement):
    import numpy as np

    return np.unique(
        np.concatenate(
            [np.linspace(a, b, refinement + 1) for a, b in zip(edges[:-1], edges[1:], strict=True)]
        )
    )


def water_quadrature(surface, water, spans_x, spans_y, *, order=5, refinement=1):
    """Integrate the wet XY footprint, clipping at the analytic graph shoreline.

    Gaussian rules are split at spline spans and shoreline/span intersections.
    Clipped endpoint integrals still require numerical refinement checks.
    Returns x, y, projected-area weights and local vertical water heights.
    """
    import numpy as np

    for value, minimum in ((order, 4), (refinement, 1)):
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
            raise ValueError("Integer quadrature order >=4 and refinement >=1 required")
    level = floor_minimum(surface) + water.depth_m
    if surface.domain == "ellipse" and level > surface.center_z + surface.rise + 1e-12:
        raise ValueError("Water level exceeds the rim; overflow is not modeled")
    if water.depth_m == 0:
        return (np.empty(0),) * 4
    xedges, yedges = _subdivide(spans_x, refinement), _subdivide(spans_y, refinement)
    a, b = surface.rise, surface.asymmetry
    d = level - surface.center_z
    if surface.domain == "ellipse":
        cuts = []
        for yy in np.r_[0.0, yedges / surface.radius_y]:
            cuts.extend(_real_roots([-b, a, b * (1 - yy**2), a * yy**2 - d]))
        xedges = np.unique(np.r_[xedges, np.asarray(cuts) * surface.radius_x])
    nodes, weights = np.polynomial.legendre.leggauss(order)
    points, areas, depths = [], [], []
    for left, right in zip(xedges[:-1], xedges[1:], strict=True):
        for node, weight in zip(nodes, weights, strict=True):
            x = (left + right + (right - left) * node) / 2
            ymax = surface.radius_y
            if surface.domain == "ellipse":
                xx = x / surface.radius_x
                height_at_axis = a * xx**2 + b * xx * (1 - xx**2)
                wet_radius_squared = (d - height_at_axis) / (a - b * xx)
                if wet_radius_squared <= 0:
                    continue
                ymax *= sqrt(max(0, min(1 - xx**2, wet_radius_squared)))
            for lower, upper in zip(yedges[:-1], yedges[1:], strict=True):
                bottom, top = max(lower, -ymax), min(upper, ymax)
                if top <= bottom:
                    continue
                ys = (bottom + top + (top - bottom) * nodes) / 2
                points.extend((x, y) for y in ys)
                areas.extend(weight * (right - left) / 2 * (top - bottom) / 2 * weights)
                depths.extend(np.maximum(0, level - surface.geometry(x, ys)[0]))
    if not points:
        return (np.empty(0),) * 4
    return (*np.asarray(points).T, np.asarray(areas), np.asarray(depths))


def column_loading(system: ShellSystem, water: ColumnWater, *, order=5, refinement=1):
    """Assemble a symmetric added-mass matrix with bounded local-support batches.

    T_water = (rho/2) integral h*(vz - bx*vx - by*vy)^2 dx dy.
    The projected area and unnormalized graph normal preserve vertical volume
    flux. Tangential wall motion produces no inviscid column loading. A flat
    floor reduces to rho*h acting only on vertical displacement.
    """
    import numpy as np

    x, y, measure, h = water_quadrature(
        system.surface,
        water,
        np.unique(system.space.knots_x),
        np.unique(system.space.knots_y),
        order=order,
        refinement=refinement,
    )
    count = len(system.space.active)
    matrix = np.zeros_like(system.mass)
    for start in range(0, len(x), 32):
        part = slice(start, start + 32)
        values = system.space.evaluate(x[part], y[part])[0]
        local = np.flatnonzero(np.any(values != 0, axis=0))
        _, zx, zy, *_ = system.surface.geometry(x[part], y[part])
        directions = (-zx, -zy, np.ones_like(zx))
        normal_flux = np.concatenate(
            [values[:, local] * directions[c][:, None] for c in system.components], axis=1
        )
        indices = np.concatenate([block * count + local for block in range(len(system.components))])
        weighted = water.density_kg_m3 * h[part] * measure[part]
        matrix[np.ix_(indices, indices)] += normal_flux.T @ (weighted[:, None] * normal_flux)
    volume = float(measure @ h)
    return ColumnLoading(
        (matrix + matrix.T) / 2,
        volume,
        float(measure.sum()),
        floor_minimum(system.surface) + water.depth_m,
        water.density_kg_m3 * volume,
    )


def with_column_water(system: ShellSystem, water: ColumnWater, *, order=5, refinement=1):
    """Return a new inertially loaded system and its loading; preserve dry K/M."""
    loading = column_loading(system, water, order=order, refinement=refinement)
    return replace(system, mass=system.mass + loading.matrix), loading
