"""Independent disk-polynomial Ritz check for the configured dry graph shell.

This study shares the stated physical assumptions, but imports no production
geometry, spline, integration, assembly or eigensolve code. Cartesian polynomials
on a disk, polar quadrature, orthonormal tangents and variation of the unit normal
give an independently assembled linear Kirchhoff-Love reference. It is numerical
cross-verification, not an analytical exact solution or measured-vessel validation.
"""

import hashlib
import json
from dataclasses import dataclass
from math import pi
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class DiskBasis:
    """Real Zernike indices; evaluation uses Jacobi recurrences, never power sums."""

    degree: int
    indices: tuple[tuple[int, int, bool], ...]

    def __len__(self):
        return len(self.indices)


def disk_polynomials(degree: int):
    """Unit mean-square real disk basis, ordered as the original reference.

    Degree 48 is a resource limit, not an accuracy claim. Higher degrees still
    require quadrature, residual and response convergence checks.
    """
    if not isinstance(degree, int) or isinstance(degree, bool) or not 3 <= degree <= 48:
        raise ValueError("Reference polynomial degree must lie between 3 and 48")
    return DiskBasis(
        degree,
        tuple(
            (n, m, imaginary)
            for n in range(degree + 1)
            for m in range(n % 2, n + 1, 2)
            for imaginary in ((False,) if m == 0 else (False, True))
        ),
    )


def jacobi_jets(maximum: int, m: int, s):
    """P_j^(0,m)(s) and two s derivatives via a differentiated three-term recurrence.

    Z_n^m = (X+iY)^m P_((n-m)/2)^(0,m)(2*(X²+Y²)-1).
    This Cartesian product avoids polar-coordinate singularities at the origin.
    See Greengard & Serkh, arXiv:1811.02720, Jacobi/Zernike recurrences.
    """
    zero, one = np.zeros_like(s), np.ones_like(s)
    jets = [(one, zero, zero)]
    if maximum:
        jets.append((((m + 2) * s - m) / 2, one * (m + 2) / 2, zero))
    for j in range(1, maximum):
        a = 2 * (j + 1) * (j + m + 1) * (2 * j + m)
        slope = (2 * j + m + 1) * (2 * j + m) * (2 * j + m + 2)
        b = slope * s - (2 * j + m + 1) * m * m
        c = 2 * j * (j + m) * (2 * j + m + 2)
        p, dp, ddp = jets[-1]
        previous, dprevious, ddprevious = jets[-2]
        jets.append(
            (
                (b * p - c * previous) / a,
                (b * dp + slope * p - c * dprevious) / a,
                (b * ddp + 2 * slope * dp - c * ddprevious) / a,
            )
        )
    return jets


def evaluate(
    basis,
    x,
    y,
    radius_x,
    radius_y,
    orders=((0, 0), (1, 0), (0, 1), (2, 0), (0, 2), (1, 1)),
):
    """Stable values and analytic first/second physical XY derivatives, including at r=0."""
    allowed = ((0, 0), (1, 0), (0, 1), (2, 0), (0, 2), (1, 1))
    if any(order not in allowed for order in orders):
        raise ValueError("Only values and derivatives through second order are supported")
    x, y = np.broadcast_arrays(np.atleast_1d(x), np.atleast_1d(y))
    xx, yy = x.ravel() / radius_x, y.ravel() / radius_y
    z, s = xx + 1j * yy, 2 * (xx * xx + yy * yy) - 1
    radial = {m: jacobi_jets((basis.degree - m) // 2, m, s) for m in range(basis.degree + 1)}
    rows = {order: [] for order in orders}
    for n, m, imaginary in basis.indices:
        p, dp, ddp = radial[m][(n - m) // 2]
        angular = z**m
        first = m * z ** (m - 1) if m else np.zeros_like(z)
        second = m * (m - 1) * z ** (m - 2) if m > 1 else np.zeros_like(z)
        jets = {
            (0, 0): angular * p,
            (1, 0): first * p + angular * dp * 4 * xx,
            (0, 1): 1j * first * p + angular * dp * 4 * yy,
            (2, 0): second * p + 8 * xx * first * dp + angular * (16 * xx**2 * ddp + 4 * dp),
            (0, 2): -second * p + 8j * yy * first * dp + angular * (16 * yy**2 * ddp + 4 * dp),
            (1, 1): 1j * second * p
            + 4 * (yy + 1j * xx) * first * dp
            + 16 * xx * yy * angular * ddp,
        }
        scale = np.sqrt((n + 1) * (1 if m == 0 else 2))
        for order in orders:
            value = jets[order].imag if imaginary else jets[order].real
            rows[order].append(scale * value / radius_x ** order[0] / radius_y ** order[1])
    return [np.asarray(rows[order]).T for order in orders]


def geometry(parameters, x, y):
    """Reference graph evaluation, intentionally independent of production geometry."""
    rx, ry = parameters["radius_x"], parameters["radius_y"]
    xx, yy = x / rx, y / ry
    rise, asymmetry = parameters["rise"], parameters["asymmetry"]
    return (
        parameters["center_z"]
        + rise * (xx * xx + yy * yy)
        + asymmetry * xx * (1 - xx * xx - yy * yy),
        (2 * rise * xx + asymmetry * (1 - 3 * xx * xx - yy * yy)) / rx,
        (2 * rise * yy - 2 * asymmetry * xx * yy) / ry,
        (2 * rise - 6 * asymmetry * xx) / rx**2,
        (2 * rise - 2 * asymmetry * xx) / ry**2,
        -2 * asymmetry * yy / (rx * ry),
    )


def disk_quadrature(surface, radial_order: int, angular_points: int):
    """Gauss integration in squared radius and a periodic angular trapezoid rule."""
    nodes, weights = np.polynomial.legendre.leggauss(radial_order)
    radius = np.sqrt((nodes + 1) / 2)
    angle = np.arange(angular_points) * 2 * pi / angular_points
    r, theta = np.meshgrid(radius, angle, indexing="ij")
    x = surface["radius_x"] * r.ravel() * np.cos(theta.ravel())
    y = surface["radius_y"] * r.ravel() * np.sin(theta.ravel())
    measure = np.repeat(weights / 4, angular_points) * 2 * pi / angular_points
    measure *= surface["radius_x"] * surface["radius_y"]
    return x, y, measure


def patch_mean(basis, surface, patch):
    nodes, weights = np.polynomial.legendre.leggauss(max(12, (basis.degree + 3) // 2))
    half = patch["width"] / 2
    x, y = np.meshgrid(patch["x"] + half * nodes, patch["y"] + half * nodes, indexing="ij")
    if np.max((x / surface["radius_x"]) ** 2 + (y / surface["radius_y"]) ** 2) > 1:
        raise ValueError("Reference contact patch must lie inside the ellipse")
    zx, zy = geometry(surface, x.ravel(), y.ravel())[1:3]
    measure = np.outer(weights, weights).ravel() * np.sqrt(1 + zx * zx + zy * zy)
    values = evaluate(
        basis,
        x.ravel(),
        y.ravel(),
        surface["radius_x"],
        surface["radius_y"],
        orders=((0, 0),),
    )[0]
    return measure @ values / measure.sum()


@dataclass
class RitzModes:
    parameters: dict
    basis: DiskBasis
    coefficients: np.ndarray  # component x polynomial x mode; mass normalized.
    frequencies: np.ndarray
    diagnostics: dict

    def weights(self, x, y):
        surface = self.parameters["surface"]
        n = evaluate(
            self.basis,
            np.asarray(x),
            np.asarray(y),
            surface["radius_x"],
            surface["radius_y"],
            orders=((0, 0),),
        )[0]
        return np.einsum("pb,cbm->pcm", n, self.coefficients)

    def patch_weights(self, patch, direction):
        mean = patch_mean(self.basis, self.parameters["surface"], patch)
        return np.einsum("b,cbm,c->m", mean, self.coefficients, direction)


def _reference_matrices(parameters, basis, x, y, measure):
    """Independent orthonormal energy on a bounded quadrature batch."""
    surface = parameters["surface"]
    n, dx, dy, dxx, dyy, dxy = evaluate(basis, x, y, surface["radius_x"], surface["radius_y"])
    _, zx, zy, zxx, zyy, zxy = geometry(surface, x, y)
    jacobian = np.sqrt(1 + zx * zx + zy * zy)
    measure *= jacobian
    zero, one = np.zeros_like(x), np.ones_like(x)
    a1, a2 = np.array([one, zero, zx]).T, np.array([zero, one, zy]).T
    normal = np.cross(a1, a2) / jacobian[:, None]
    t1 = a1 / np.linalg.norm(a1, axis=1)[:, None]
    t2 = np.cross(normal, t1)
    dual1 = np.cross(a2, normal) / jacobian[:, None]
    dual2 = np.cross(normal, a1) / jacobian[:, None]
    transform = np.array(
        [
            [np.einsum("pc,pc->p", dual1, t1), np.einsum("pc,pc->p", dual1, t2)],
            [np.einsum("pc,pc->p", dual2, t1), np.einsum("pc,pc->p", dual2, t2)],
        ]
    ).transpose(2, 0, 1)
    d1 = transform[:, 0, 0, None] * dx + transform[:, 1, 0, None] * dy
    d2 = transform[:, 0, 1, None] * dx + transform[:, 1, 1, None] * dy
    count, points = len(basis), len(x)
    strain, bending = np.zeros((points, 3, 3 * count)), np.zeros((points, 3, 3 * count))
    for c in range(3):
        target = slice(c * count, (c + 1) * count)
        strain[:, 0, target] = t1[:, c, None] * d1
        strain[:, 1, target] = t2[:, c, None] * d2
        strain[:, 2, target] = t1[:, c, None] * d2 + t2[:, c, None] * d1
        # Delta normal enforces perpendicularity to the deformed tangent plane.
        delta_normal_z = -normal[:, c, None] * (dual1[:, 2, None] * dx + dual2[:, 2, None] * dy)
        bxx = normal[:, c, None] * dxx + delta_normal_z * zxx[:, None]
        byy = normal[:, c, None] * dyy + delta_normal_z * zyy[:, None]
        bxy = normal[:, c, None] * dxy + delta_normal_z * zxy[:, None]
        for row, (i, j, factor) in enumerate(((0, 0, 1), (1, 1, 1), (0, 1, 2))):
            bending[:, row, target] = factor * (
                transform[:, 0, i, None] * transform[:, 0, j, None] * bxx
                + transform[:, 1, i, None] * transform[:, 1, j, None] * byy
                + (
                    transform[:, 0, i, None] * transform[:, 1, j, None]
                    + transform[:, 1, i, None] * transform[:, 0, j, None]
                )
                * bxy
            )
    material = parameters["material"]
    elastic, nu, h = material["youngs_modulus"], material["poisson_ratio"], parameters["thickness"]
    constitutive = (
        elastic / (1 - nu * nu) * np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
    )

    def integrate(operator):
        transformed = np.einsum("ij,pjb->pib", constitutive, operator) * measure[:, None, None]
        return operator.reshape(-1, 3 * count).T @ transformed.reshape(-1, 3 * count)

    stiffness = h * integrate(strain) + h**3 / 12 * integrate(bending)
    scalar_mass = n.T @ (n * (measure * material["density"] * h)[:, None])
    return stiffness, scalar_mass, float(measure.sum())


def solve(
    parameters: dict,
    degree: int = 12,
    mode_count: int = 32,
    radial_order: int | None = None,
    angular_points: int | None = None,
) -> RitzModes:
    """Assemble independently in local orthonormal coordinates and solve with unit modal mass."""
    surface = parameters["surface"]
    if surface["domain"] != "ellipse" or parameters["water_depth_m"] != 0:
        raise ValueError("Reference supports only dry elliptical graph shells")
    radial_order = radial_order or degree + 5
    angular_points = angular_points or 4 * degree + 12
    basis = disk_polynomials(degree)
    x, y, measure = disk_quadrature(surface, radial_order, angular_points)
    count = len(basis)
    stiffness, scalar_mass = np.zeros((3 * count,) * 2), np.zeros((count, count))
    area = 0.0
    for start in range(0, len(x), 256):
        part = slice(start, start + 256)
        k, m, a = _reference_matrices(parameters, basis, x[part], y[part], measure[part])
        stiffness += k
        scalar_mass += m
        area += a
    mass = np.kron(np.eye(3), scalar_mass)
    for support in parameters["supports"]:
        mean = patch_mean(basis, surface, support["patch"])
        for c in range(3):
            target = slice(c * count, (c + 1) * count)
            stiffness[target, target] += support["stiffness"][c] * np.outer(mean, mean)
    for exciter in parameters["exciters"]:
        mean = patch_mean(basis, surface, exciter["patch"])
        for c in range(3):
            target = slice(c * count, (c + 1) * count)
            mass[target, target] += exciter["added_mass_kg"] * np.outer(mean, mean)
    factor = np.linalg.cholesky(mass)
    reduced = np.linalg.solve(factor, np.linalg.solve(factor, stiffness).T).T
    values, vectors = np.linalg.eigh((reduced + reduced.T) / 2)
    if values[0] < -max(1e-3, abs(values[-1]) * 1e-9):
        raise ValueError("Indefinite reference stiffness")
    keep = values > (2 * pi * 0.01) ** 2
    if np.count_nonzero(keep) < mode_count:
        raise ValueError("Too many reference modes requested")
    values, vectors = values[keep][:mode_count], vectors[:, keep][:, :mode_count]
    coefficients = np.linalg.solve(factor.T, vectors)
    residual = stiffness @ coefficients - (mass @ coefficients) * values
    return RitzModes(
        parameters,
        basis,
        coefficients.reshape(3, count, mode_count),
        np.sqrt(values) / (2 * pi),
        {
            "degree": degree,
            "basis_evaluation": "Jacobi recurrence with analytic Cartesian derivatives",
            "assembly": "quadrature batches of at most 256 points",
            "radial_order": radial_order,
            "angular_points": angular_points,
            "degrees_of_freedom": 3 * count,
            "area_m2": area,
            "mass_condition_number": float(np.linalg.cond(mass[:count, :count])),
            "discarded_rigid_modes": int(np.count_nonzero(~keep)),
            "maximum_relative_eigen_residual": float(
                np.max(
                    np.linalg.norm(residual, axis=0)
                    / np.linalg.norm(stiffness @ coefficients, axis=0)
                )
            ),
        },
    )


def get_modes(
    parameters, degree, mode_count, directory: Path, *, radial_order=None, angular_points=None
):
    """Cache independent reference solves with full configuration and source identity."""
    identity = {
        "parameters": parameters,
        "degree": degree,
        "mode_count": mode_count,
        "radial_order": radial_order,
        "angular_points": angular_points,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    path = directory / f"ritz_modes_{key[:20]}.npz"
    if path.is_file():
        with np.load(path, allow_pickle=False) as archive:
            metadata = json.loads(str(archive["metadata"]))
            if metadata.get("cache_key") != key or metadata.get("schema") != 1:
                raise ValueError("Independent reference cache identity mismatch")
            coefficients, frequencies = (
                archive["coefficients"].copy(),
                archive["frequencies"].copy(),
            )
        if (
            coefficients.shape != (3, len(disk_polynomials(degree)), mode_count)
            or frequencies.shape != (mode_count,)
            or not np.all(np.isfinite(coefficients))
            or not np.all(np.isfinite(frequencies))
            or np.any(frequencies <= 0)
            or np.any(np.diff(frequencies) < 0)
        ):
            raise ValueError("Invalid independent reference archive")
        return (
            RitzModes(
                parameters,
                disk_polynomials(degree),
                coefficients,
                frequencies,
                metadata["diagnostics"],
            ),
            path,
            True,
        )
    modes = solve(parameters, degree, mode_count, radial_order, angular_points)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        coefficients=modes.coefficients,
        frequencies=modes.frequencies,
        metadata=json.dumps(
            {"schema": 1, "cache_key": key, "diagnostics": modes.diagnostics, "identity": identity}
        ),
    )
    return modes, path, False
