"""Optimized batches must reproduce the reference artistic equations and controls."""

import importlib
import unittest
from unittest.mock import patch

config_module = importlib.import_module("prototypes.001_resonant_surface.config")
simulation = importlib.import_module("prototypes.001_resonant_surface.simulation")


class SamplingTests(unittest.TestCase):
    points = [(0.0, 0.0), (-0.20, -0.04), (0.25, -0.10), (0.60, 0.0), (0.8, 0.0)]

    def check_backend(self, use_numpy: bool) -> None:
        for experiment in (None, "002_close_frequencies"):
            field = simulation.ResonantField(config_module.load_config(experiment))
            sampler = field.prepare(self.points, use_numpy=use_numpy)
            for time in (-0.5, 0.0, 3.199, 3.2, 3.3, 6.6, 19.9):
                for actual, (x, y) in zip(sampler.sample(time), self.points, strict=True):
                    self.assertAlmostEqual(actual, field.sample(x, y, time), places=13)
            # Amplitude/frequency are dynamic controls, unlike cached source positions.
            field.config.exciters[0].update(amplitude=0.25, frequency=61.25)
            state = field.step(4.3)
            for actual, (x, y) in zip(
                sampler.sample(state.time, exciters=state.exciter_states), self.points, strict=True
            ):
                self.assertAlmostEqual(actual, field.sample(x, y), places=13)

    def test_cached_standard_library_equivalence(self) -> None:
        self.check_backend(False)

    def test_numpy_equivalence(self) -> None:
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("Optional NumPy is not installed")
        self.check_backend(True)

    def test_missing_numpy_selects_fallback(self) -> None:
        with patch.dict("sys.modules", {"numpy": None}):
            field = simulation.ResonantField(config_module.default_config())
            sampler = field.prepare(self.points)
            self.assertEqual(sampler.backend, "python")
            self.assertEqual(len(sampler.sample(0.0)), len(self.points))
            self.assertEqual(len(field.step(3.5).sensor_states), 2)
            with self.assertRaises(ImportError):
                field.prepare(self.points, use_numpy=True)


if __name__ == "__main__":
    unittest.main()
