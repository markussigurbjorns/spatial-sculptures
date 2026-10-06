"""Analytical checks for the public, dependency-free artistic wave functions."""

import math
import unittest

from spatial_sculptures.simulation.waves import expanding_ripple, radial_wave


class WaveTests(unittest.TestCase):
    def wave(self, x: float, y: float, time: float = 0.0, damping: float = 0.0) -> float:
        return radial_wave(x, y, 0, 0, time, 2, 1, 0, 1, damping, 0.25)

    def test_known_phase_and_radial_symmetry(self) -> None:
        self.assertAlmostEqual(self.wave(0.25, 0), 1.0)
        self.assertAlmostEqual(self.wave(0, -0.25), 1.0)
        self.assertAlmostEqual(self.wave(0.75, 0), -1.0)

    def test_scaled_temporal_period(self) -> None:
        # Effective frequency is 2 * 0.25 = 0.5 Hz, hence a two-second period.
        self.assertAlmostEqual(self.wave(0.25, 0, 0), self.wave(0.25, 0, 2))
        self.assertAlmostEqual(self.wave(0.25, 0, 1), -1.0)

    def test_exponential_spatial_damping(self) -> None:
        near = self.wave(0.25, 0, damping=1.5)
        far = self.wave(1.25, 0, damping=1.5)
        self.assertAlmostEqual(far / near, math.exp(-1.5))

    def test_translation_invariance(self) -> None:
        original = self.wave(0.25, 0.0)
        shifted = radial_wave(10.25, -2, 10, -2, 0, 2, 1, 0, 1, 0, 0.25)
        self.assertAlmostEqual(original, shifted)

    def test_ripple_causality_locality_and_decay(self) -> None:
        options = {"amplitude": 1.0, "speed": 0.28}
        self.assertEqual(expanding_ripple(0.1, 0, 0, 0, -0.1, **options), 0.0)
        offset = 0.075 / 4
        early = expanding_ripple(0.28 + offset, 0, 0, 0, 1, **options)
        late = expanding_ripple(0.56 + offset, 0, 0, 0, 2, **options)
        distant = expanding_ripple(2, 0, 0, 0, 1, **options)
        self.assertGreater(early, late)
        self.assertGreater(late, 0)
        self.assertLess(abs(distant), 1e-20)

    def test_invalid_wave_parameters(self) -> None:
        with self.assertRaises(ValueError):
            radial_wave(0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 1)
        with self.assertRaises(ValueError):
            expanding_ripple(0, 0, 0, 0, 1, amplitude=1, speed=0)


if __name__ == "__main__":
    unittest.main()
