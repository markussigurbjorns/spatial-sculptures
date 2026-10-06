"""Small linear Kirchhoff-Love shell eigenproblem, using C2 spline finite elements.

Graph surfaces, isotropic plane stress, translational consistent mass, free rims
and rigid average-displacement contact patches. No fluid, prestress, weld/rim
reinforcement, nonlinear deformation or shear/rotary inertia. See research notes
for the covariant membrane/bending energy and verification, including limitations.
NumPy is optional for the rest of the project, required for this numerical backend.
"""

from dataclasses import dataclass
from math import isfinite

import numpy as np

from .splines import SplineSpace


@dataclass(frozen=True)
class Material:
    youngs_modulus: float = 193e9
    density: float = 8030.0
    poisson_ratio: float = 0.30

    def __post_init__(self):
        if not all(isfinite(v) and v > 0 for v in (self.youngs_modulus, self.density)):
            raise ValueError("Modulus and density must be finite and positive")
        if not isfinite(self.poisson_ratio) or not -1 < self.poisson_ratio < 0.5:
            raise ValueError("Poisson ratio must lie between -1 and 0.5")


@dataclass(frozen=True)
class GraphSurface:
    """Parabolic graph with a cubic asymmetry; dimensions/heights are in metres."""

    radius_x: float
    radius_y: float
    rise: float = 0.0
    asymmetry: float = 0.0
    center_z: float = 0.0
    domain: str = "ellipse"

    def __post_init__(self):
        if not all(
            isfinite(v)
            for v in (self.radius_x, self.radius_y, self.rise, self.asymmetry, self.center_z)
        ):
            raise ValueError("Surface parameters must be finite")
        if min(self.radius_x, self.radius_y) <= 0 or self.domain not in ("ellipse", "rectangle"):
            raise ValueError("Positive radii and ellipse/rectangle domain are required")

    def contains(self, x, y):
        if self.domain == "rectangle":
            return (np.abs(x) <= self.radius_x + 1e-12) & (np.abs(y) <= self.radius_y + 1e-12)
        return (np.asarray(x) / self.radius_x) ** 2 + (
            np.asarray(y) / self.radius_y
        ) ** 2 <= 1 + 1e-12

    def geometry(self, x, y):
        """Height and exact first/second graph derivatives, not visual-only curvature."""
        xx, yy = np.asarray(x) / self.radius_x, np.asarray(y) / self.radius_y
        a, b = self.rise, self.asymmetry
        z = self.center_z + a * (xx**2 + yy**2) + b * xx * (1 - xx**2 - yy**2)
        zx = (2 * a * xx + b * (1 - 3 * xx**2 - yy**2)) / self.radius_x
        zy = (2 * a * yy - 2 * b * xx * yy) / self.radius_y
        zxx = (2 * a - 6 * b * xx) / self.radius_x**2
        zyy = (2 * a - 2 * b * xx) / self.radius_y**2
        zxy = -2 * b * yy / (self.radius_x * self.radius_y)
        return z, zx, zy, zxx, zyy, zxy


@dataclass(frozen=True)
class Patch:
    """Square patch in XY coordinates; force/mass couples to mean physical displacement."""

    x: float
    y: float
    width: float

    def __post_init__(self):
        if not all(isfinite(v) for v in (self.x, self.y, self.width)) or self.width <= 0:
            raise ValueError("Finite patch coordinates and positive width are required")


@dataclass(frozen=True)
class Support:
    patch: Patch
    stiffness: tuple[float, float, float]  # Total X/Y/Z spring stiffness, N/m.

    def __post_init__(self):
        if len(self.stiffness) != 3 or not all(isfinite(v) and v >= 0 for v in self.stiffness):
            raise ValueError("Three finite nonnegative support stiffnesses are required")


@dataclass(frozen=True)
class AttachedMass:
    patch: Patch
    mass_kg: float  # Rigid housing inertia in all three translational directions.

    def __post_init__(self):
        if not isfinite(self.mass_kg) or self.mass_kg < 0:
            raise ValueError("Attached mass must be finite and nonnegative")


def quadrature(surface: GraphSurface, nx: int, ny: int, order: int):
    """Cell-wise Gauss integration; ellipse intervals are clipped analytically.

    Split X at ellipse/grid intersections rather than classifying whole cells or
    masking sample points. The curved-boundary integrals still need convergence checks.
    """
    if min(nx, ny) < 1 or order < 4:
        raise ValueError("Positive cell counts and Gauss order >= 4 are required")
    nodes, weights = np.polynomial.legendre.leggauss(order)
    xedges = np.linspace(-surface.radius_x, surface.radius_x, nx + 1)
    yedges = np.linspace(-surface.radius_y, surface.radius_y, ny + 1)
    if surface.domain == "ellipse":
        cuts = surface.radius_x * np.sqrt(np.maximum(0, 1 - (yedges / surface.radius_y) ** 2))
        xedges = np.unique(np.r_[xedges, cuts, -cuts])
    points, measures = [], []
    for left, right in zip(xedges[:-1], xedges[1:], strict=True):
        for node, weight in zip(nodes, weights, strict=True):
            x = (left + right + (right - left) * node) / 2
            ymax = surface.radius_y
            if surface.domain == "ellipse":
                ymax *= np.sqrt(max(0.0, 1 - (x / surface.radius_x) ** 2))
            for lower, upper in zip(yedges[:-1], yedges[1:], strict=True):
                bottom, top = max(lower, -ymax), min(upper, ymax)
                if top <= bottom:
                    continue
                ys = (bottom + top + (top - bottom) * nodes) / 2
                points.extend((x, y) for y in ys)
                measures.extend(weight * (right - left) / 2 * (top - bottom) / 2 * weights)
    xy = np.asarray(points)
    return xy[:, 0], xy[:, 1], np.asarray(measures)


def patch_average(space: SplineSpace, surface: GraphSurface, patch: Patch, order: int = 5):
    """Area-weighted mean basis over a fully contained mounting/support patch."""
    half = patch.width / 2
    if not all(
        surface.contains(patch.x + dx * half, patch.y + dy * half)
        for dx in (-1, 1)
        for dy in (-1, 1)
    ):
        raise ValueError("Every contact-patch corner must lie inside the structural surface")
    nodes, weights = np.polynomial.legendre.leggauss(order)
    # Integrate each polynomial span separately, including patches crossing knots.
    edges = []
    for center, knots in ((patch.x, space.knots_x), (patch.y, space.knots_y)):
        low, high = center - half, center + half
        edges.append(np.unique(np.r_[low, knots[(knots > low) & (knots < high)], high]))
    numerator = np.zeros(len(space.active))
    area = 0.0
    for xa, xb in zip(edges[0][:-1], edges[0][1:], strict=True):
        for ya, yb in zip(edges[1][:-1], edges[1][1:], strict=True):
            x, y = np.meshgrid(
                (xa + xb) / 2 + (xb - xa) / 2 * nodes,
                (ya + yb) / 2 + (yb - ya) / 2 * nodes,
                indexing="ij",
            )
            _, zx, zy, *_ = surface.geometry(x.ravel(), y.ravel())
            measure = (
                np.outer(weights, weights).ravel()
                * (xb - xa)
                * (yb - ya)
                / 4
                * np.sqrt(1 + zx**2 + zy**2)
            )
            numerator += measure @ space.evaluate(x.ravel(), y.ravel())[0]
            area += measure.sum()
    return numerator / area


@dataclass
class ShellSystem:
    surface: GraphSurface
    space: SplineSpace
    stiffness: np.ndarray
    mass: np.ndarray
    components: tuple[int, ...]
    area: float
    shell_mass_kg: float


def assemble_shell(
    surface: GraphSurface,
    material: Material,
    thickness: float,
    *,
    elements: tuple[int, int] = (6, 6),
    gauss_order: int = 5,
    supports: tuple[Support, ...] = (),
    attached_masses: tuple[AttachedMass, ...] = (),
    simply_supported_plate: bool = False,
) -> ShellSystem:
    """Assemble consistent K/M from membrane and bending energy, in SI units."""
    if not isfinite(thickness) or thickness <= 0:
        raise ValueError("Uniform thickness must be finite and positive")
    if len(elements) != 2 or any(not isinstance(v, int) or v < 1 for v in elements):
        raise ValueError("Two positive integer element counts are required")
    if simply_supported_plate and (
        surface.domain != "rectangle" or surface.rise or surface.asymmetry
    ):
        raise ValueError("The plate boundary check requires a flat rectangle")
    if simply_supported_plate and (supports or attached_masses):
        raise ValueError("Plate reference boundary check excludes local supports/attached masses")
    space = SplineSpace.rectangle(surface.radius_x, surface.radius_y, *elements)
    x, y, measure = quadrature(surface, *elements, gauss_order)
    _, zx, zy, zxx, zyy, zxy = surface.geometry(x, y)
    jacobian = np.sqrt(1 + zx**2 + zy**2)
    measure *= jacobian
    values = space.evaluate(x, y)[0]
    diagonal = np.sum(measure[:, None] * values**2, axis=0)
    if simply_supported_plate:
        ix, iy = np.unravel_index(space.active, (elements[0] + 3, elements[1] + 3))
        keep = (ix > 0) & (ix < elements[0] + 2) & (iy > 0) & (iy < elements[1] + 2)
    else:
        keep = diagonal > diagonal.max() * 1e-12
    space.active = space.active[keep]
    n, dx, dy, dxx, dyy, dxy = space.evaluate(x, y)
    count, points = len(space.active), len(x)
    components = (2,) if simply_supported_plate else (0, 1, 2)
    # Inverse graph metric and unit normal.
    determinant = jacobian**2
    gxx, gyy, gxy = (1 + zy**2) / determinant, (1 + zx**2) / determinant, -zx * zy / determinant
    normal = np.stack((-zx, -zy, np.ones(points)), axis=1) / jacobian[:, None]
    gamma_x = (gxx * zx + gxy * zy)[:, None]
    gamma_y = (gxy * zx + gyy * zy)[:, None]
    covariant = [
        hessian - curvature[:, None] * (gamma_x * dx + gamma_y * dy)
        for hessian, curvature in ((dxx, zxx), (dyy, zyy), (2 * dxy, 2 * zxy))
    ]
    strain = np.zeros((points, 3, len(components) * count))
    bending = np.zeros_like(strain)
    for block, component in enumerate(components):
        target = slice(block * count, (block + 1) * count)
        ax = 1 if component == 0 else zx if component == 2 else np.zeros(points)
        ay = 1 if component == 1 else zy if component == 2 else np.zeros(points)
        ax, ay = np.broadcast_to(ax, (points,))[:, None], np.broadcast_to(ay, (points,))[:, None]
        strain[:, 0, target], strain[:, 1, target] = ax * dx, ay * dy
        strain[:, 2, target] = ax * dy + ay * dx
        for row in range(3):
            bending[:, row, target] = normal[:, component, None] * covariant[row]
    trace = np.stack((gxx, gyy, gxy), axis=1)
    contraction = np.empty((points, 3, 3))
    contraction[:, 0, 0], contraction[:, 1, 1] = gxx**2, gyy**2
    contraction[:, 0, 1] = contraction[:, 1, 0] = gxy**2
    contraction[:, 0, 2] = contraction[:, 2, 0] = gxx * gxy
    contraction[:, 1, 2] = contraction[:, 2, 1] = gyy * gxy
    contraction[:, 2, 2] = (gxx * gyy + gxy**2) / 2
    nu, elastic = material.poisson_ratio, material.youngs_modulus
    constitutive = elastic * nu / (1 - nu**2) * trace[:, :, None] * trace[:, None, :]
    constitutive += elastic / (1 + nu) * contraction

    def energy_matrix(operator):
        transformed = np.einsum("pij,pjk->pik", constitutive * measure[:, None, None], operator)
        return operator.reshape(points * 3, -1).T @ transformed.reshape(points * 3, -1)

    stiffness = thickness * energy_matrix(strain) + thickness**3 / 12 * energy_matrix(bending)
    scalar_mass = n.T @ ((measure * material.density * thickness)[:, None] * n)
    mass = np.kron(np.eye(len(components)), scalar_mass)
    for support in supports:
        mean = patch_average(space, surface, support.patch)
        for block, component in enumerate(components):
            target = slice(block * count, (block + 1) * count)
            stiffness[target, target] += support.stiffness[component] * np.outer(mean, mean)
    for attached in attached_masses:
        mean = patch_average(space, surface, attached.patch)
        for block in range(len(components)):
            target = slice(block * count, (block + 1) * count)
            mass[target, target] += attached.mass_kg * np.outer(mean, mean)
    return ShellSystem(
        surface,
        space,
        (stiffness + stiffness.T) / 2,
        (mass + mass.T) / 2,
        components,
        float(measure.sum()),
        float(measure.sum() * material.density * thickness),
    )


def solve_modes(system: ShellSystem, mode_count: int):
    """Mass-whiten the generalized symmetric eigenproblem; return mass-normalized vectors.

    Modes below 0.01 Hz are excluded and counted (free-body motion is not rendered
    as an oscillator). A substantial negative eigenvalue is a failed solve.
    """
    if not isinstance(mode_count, int) or mode_count < 1:
        raise ValueError("Positive integer retained mode count required")
    scale = 1 / np.sqrt(np.diag(system.mass))
    mass = scale[:, None] * system.mass * scale[None, :]
    stiffness = scale[:, None] * system.stiffness * scale[None, :]
    factor = np.linalg.cholesky(mass)
    left = np.linalg.solve(factor, stiffness)
    whitened = np.linalg.solve(factor, left.T).T
    eigenvalues, vectors = np.linalg.eigh((whitened + whitened.T) / 2)
    if eigenvalues[0] < -max(1e-3, abs(eigenvalues[-1]) * 1e-9):
        raise ValueError("Negative structural eigenvalue; inspect formulation/conditioning")
    positive = eigenvalues > (2 * np.pi * 0.01) ** 2
    discarded = int(np.count_nonzero(~positive))
    if np.count_nonzero(positive) < mode_count:
        raise ValueError("Requested more positive modes than the discrete structure provides")
    eigenvalues, vectors = eigenvalues[positive][:mode_count], vectors[:, positive][:, :mode_count]
    coefficients = scale[:, None] * np.linalg.solve(factor.T, vectors)
    residual = system.stiffness @ coefficients - (system.mass @ coefficients) * eigenvalues
    denominator = np.linalg.norm(system.stiffness @ coefficients, axis=0)
    relative_residual = np.linalg.norm(residual, axis=0) / np.maximum(denominator, 1e-15)
    return (
        np.sqrt(eigenvalues) / (2 * np.pi),
        coefficients,
        {
            "discarded_rigid_or_near_zero_modes": discarded,
            "maximum_relative_eigen_residual": float(relative_residual.max()),
            "mass_condition_number_scaled": float(np.linalg.cond(mass)),
            "degrees_of_freedom": len(system.mass),
            "area_m2": system.area,
            "shell_mass_kg": system.shell_mass_kg,
        },
    )
