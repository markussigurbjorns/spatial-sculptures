"""Analytical Kirchhoff-Love modes of a uniform, simply supported rectangular plate.

This reference excludes curvature, fluid loading, shear deformation, rotary inertia,
prestress and point supports. See Leissa, NASA SP-160 (1969), in the research paper.
Coordinates are centred on the plate; mode shapes have unit peak amplitude.
"""

from dataclasses import dataclass
from math import isfinite, pi, sin, sqrt, tau

from .modal import Mode


@dataclass(frozen=True)
class RectangularPlate:
    """Isotropic, homogeneous plate parameters in SI units."""

    length_x: float
    length_y: float
    thickness: float
    youngs_modulus: float
    density: float
    poisson_ratio: float

    def __post_init__(self) -> None:
        values = (self.length_x, self.length_y, self.thickness, self.youngs_modulus, self.density)
        if any(not isfinite(value) or value <= 0 for value in values):
            raise ValueError("Plate dimensions, modulus and density must be finite and positive")
        if not isfinite(self.poisson_ratio) or not -1 < self.poisson_ratio < 0.5:
            raise ValueError("Isotropic Poisson ratio must be between -1 and 0.5")

    @property
    def rigidity(self) -> float:
        """Flexural rigidity D, in N*m."""
        return self.youngs_modulus * self.thickness**3 / (12 * (1 - self.poisson_ratio**2))

    @property
    def modal_mass(self) -> float:
        """Modal mass in kg for the unit-peak sine-product normalization."""
        return self.density * self.thickness * self.length_x * self.length_y / 4

    def contains(self, x: float, y: float) -> bool:
        return abs(x) <= self.length_x / 2 and abs(y) <= self.length_y / 2

    def shape(self, m: int, n: int, x: float, y: float) -> float:
        """Dimensionless sine-product mode shape at a centred XY position."""
        if m < 1 or n < 1:
            raise ValueError("Mode indices must be positive")
        if not self.contains(x, y):
            return 0.0
        return sin(m * pi * (x / self.length_x + 0.5)) * sin(n * pi * (y / self.length_y + 0.5))

    def mode(self, m: int, n: int, damping_ratio: float) -> Mode:
        """Derive frequency and mass from material and geometry, without fitted wavelengths."""
        if m < 1 or n < 1:
            raise ValueError("Mode indices must be positive")
        omega = (
            pi**2
            * sqrt(self.rigidity / (self.density * self.thickness))
            * ((m / self.length_x) ** 2 + (n / self.length_y) ** 2)
        )
        return Mode(f"{m}_{n}", omega / tau, self.modal_mass, damping_ratio)

    def patch_projection(self, m: int, n: int, x: float, y: float, width: float) -> float:
        """Mean mode shape over a square patch; multiplies TOTAL force/impulse.

        A finite contact patch avoids the infinite modal energy of an ideal point
        impulse when the mode count grows. The whole patch must lie on the plate.
        """
        if not isfinite(width) or width <= 0:
            raise ValueError("Contact width must be finite and positive")
        if not self.contains(abs(x) + width / 2, abs(y) + width / 2):
            raise ValueError("The contact patch must fit inside the plate")
        ax, ay = m * pi * width / (2 * self.length_x), n * pi * width / (2 * self.length_y)
        return self.shape(m, n, x, y) * sin(ax) / ax * sin(ay) / ay
