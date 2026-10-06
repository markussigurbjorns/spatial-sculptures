"""Independent disk-polynomial Ritz check for the configured dry graph shell.

This study shares the stated physical assumptions, but imports no production
geometry, spline, integration, assembly or eigensolve code. Cartesian polynomials
on a disk, polar quadrature, orthonormal tangents and variation of the unit normal
give an independently assembled linear Kirchhoff-Love reference. It is numerical
cross-verification, not an analytical exact solution or measured-vessel validation.
"""

from dataclasses import dataclass
from math import comb, factorial, pi

import numpy as np
from numpy.polynomial import polynomial as poly


def disk_polynomials(degree: int):
    """Normalized real Zernike polynomials expressed in Cartesian X/Y coefficients."""
    if not isinstance(degree, int) or not 3 <= degree <= 20:
        raise ValueError("Reference polynomial degree must lie between 3 and 20")
    coefficients = []
    for n in range(degree + 1):
        for m in range(n % 2, n + 1, 2):
            for imaginary in (False,) if m == 0 else (False, True):
                terms = np.zeros((degree + 1, degree + 1))
                for s in range((n - m) // 2 + 1):
                    radial = (
                        (-1) ** s
                        * factorial(n - s)
                        / (factorial(s) * factorial((n + m) // 2 - s) * factorial((n - m) // 2 - s))
                    )
                    power = (n - m) // 2 - s
                    for k in range(m + 1):
                        phase = (1j**k).imag if imaginary else (1j**k).real
                        for j in range(power + 1):
                            terms[m - k + 2 * (power - j), k + 2 * j] += (
                                radial * comb(m, k) * phase * comb(power, j)
                            )
                terms *= np.sqrt((n + 1) * (1 if m == 0 else 2))
                coefficients.append(terms)
    return np.asarray(coefficients)


def evaluate(
    coefficients,
    x,
    y,
    radius_x,
    radius_y,
    orders=((0, 0), (1, 0), (0, 1), (2, 0), (0, 2), (1, 1)),
):
    """Independent polynomial values and derivatives in physical Cartesian coordinates."""
    result = []
    for nx, ny in orders:
        rows = []
        for coefficient in coefficients:
            derivative = poly.polyder(poly.polyder(coefficient, nx, axis=0), ny, axis=1)
            rows.append(
                poly.polyval2d(x / radius_x, y / radius_y, derivative) / radius_x**nx / radius_y**ny
            )
        result.append(np.array(rows).T)
    return result


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


def patch_mean(coefficients, surface, patch):
    nodes, weights = np.polynomial.legendre.leggauss(12)
    half = patch["width"] / 2
    x, y = np.meshgrid(patch["x"] + half * nodes, patch["y"] + half * nodes, indexing="ij")
    if np.max((x / surface["radius_x"]) ** 2 + (y / surface["radius_y"]) ** 2) > 1:
        raise ValueError("Reference contact patch must lie inside the ellipse")
    zx, zy = geometry(surface, x.ravel(), y.ravel())[1:3]
    measure = np.outer(weights, weights).ravel() * np.sqrt(1 + zx * zx + zy * zy)
    values = evaluate(
        coefficients,
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
    basis: np.ndarray
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
            "radial_order": radial_order,
            "angular_points": angular_points,
            "degrees_of_freedom": 3 * count,
            "area_m2": float(measure.sum()),
            "mass_condition_number": float(np.linalg.cond(mass)),
            "discarded_rigid_modes": int(np.count_nonzero(~keep)),
            "maximum_relative_eigen_residual": float(
                np.max(
                    np.linalg.norm(residual, axis=0)
                    / np.linalg.norm(stiffness @ coefficients, axis=0)
                )
            ),
        },
    )
