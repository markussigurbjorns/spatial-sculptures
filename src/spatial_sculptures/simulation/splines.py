"""Cubic C2 tensor-product B-splines for small offline structural studies (NumPy)."""

from dataclasses import dataclass

import numpy as np


def open_knots(lower: float, upper: float, elements: int) -> np.ndarray:
    """Open uniform cubic knot vector, with four copies of each endpoint."""
    if not lower < upper or not isinstance(elements, int) or elements < 1:
        raise ValueError("Positive domain extent and element count are required")
    edges = np.linspace(lower, upper, elements + 1)
    return np.r_[np.repeat(lower, 4), edges[1:-1], np.repeat(upper, 4)]


def basis_1d(knots, points) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate cubic basis values and their first/second spatial derivatives."""
    knots, points = np.asarray(knots), np.asarray(points, dtype=float)
    # Use the left-hand limit at the closed endpoint, including for derivatives.
    x = np.minimum(points, np.nextafter(knots[-1], knots[0]))[:, None]
    value = ((x >= knots[:-1]) & (x < knots[1:])).astype(float)
    first, second = np.zeros_like(value), np.zeros_like(value)
    for degree in range(1, 4):
        count = len(knots) - degree - 1
        left, right = (
            knots[degree : degree + count] - knots[:count],
            (knots[degree + 1 : degree + count + 1] - knots[1 : count + 1]),
        )
        a = np.divide(1.0, left, out=np.zeros(count), where=left > 0)
        b = np.divide(1.0, right, out=np.zeros(count), where=right > 0)
        new = (x - knots[:count]) * a * value[:, :count]
        new += (knots[degree + 1 : degree + count + 1] - x) * b * value[:, 1 : count + 1]
        new_first = degree * (a * value[:, :count] - b * value[:, 1 : count + 1])
        new_second = degree * (a * first[:, :count] - b * first[:, 1 : count + 1])
        value, first, second = new, new_first, new_second
    return value, first, second


@dataclass
class SplineSpace:
    """Active tensor-product basis; inactive cut-domain functions may be removed."""

    knots_x: np.ndarray
    knots_y: np.ndarray
    active: np.ndarray

    @classmethod
    def rectangle(cls, radius_x: float, radius_y: float, nx: int, ny: int):
        kx, ky = open_knots(-radius_x, radius_x, nx), open_knots(-radius_y, radius_y, ny)
        return cls(kx, ky, np.arange((nx + 3) * (ny + 3)))

    def evaluate(self, x, y) -> tuple[np.ndarray, ...]:
        """Return N, Nx, Ny, Nxx, Nyy and Nxy at paired XY coordinates."""
        bx, dx, ddx = basis_1d(self.knots_x, x)
        by, dy, ddy = basis_1d(self.knots_y, y)
        return tuple(
            (a[:, :, None] * b[:, None, :]).reshape(len(bx), -1)[:, self.active]
            for a, b in ((bx, by), (dx, by), (bx, dy), (ddx, by), (bx, ddy), (dx, dy))
        )
