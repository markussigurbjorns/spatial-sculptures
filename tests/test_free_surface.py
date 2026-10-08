"""Dispersion, volume compatibility, restoring energy and coupled pressure checks."""

import importlib
import importlib.util
import unittest
from math import pi, sqrt
from types import SimpleNamespace

from spatial_sculptures.simulation.free_surface import gravity_capillary_frequency

try:
    import numpy as np

    from spatial_sculptures.simulation.fluid_loading import ColumnWater, water_quadrature
    from spatial_sculptures.simulation.fluid_potential import PotentialSettings
    from spatial_sculptures.simulation.free_surface import assemble_free_surface, solve_free_modes
    from spatial_sculptures.simulation.mode_cache import CachedModes
    from spatial_sculptures.simulation.structures import GraphSurface
except ImportError:
    np = None


class DispersionTests(unittest.TestCase):
    def test_finite_depth_and_restoring_limits(self):
        f = gravity_capillary_frequency
        self.assertEqual(f(0, 0.065), 0)
        k, h = 2.0, 1e-7
        self.assertAlmostEqual(
            f(k, h, surface_tension=0) / (k * sqrt(9.81 * h) / (2 * pi)), 1, places=10
        )
        k = 1000.0
        self.assertAlmostEqual(
            f(k, 10, gravity=0) / (sqrt(0.072 * k**3 / 1000) / (2 * pi)), 1, places=12
        )
        self.assertGreater(f(100, 0.02), f(100, 0.02, surface_tension=0))

    def test_invalid_physical_parameters(self):
        for kwargs in (
            {"wavenumber": -1},
            {"depth": 0},
            {"density": 0},
            {"gravity": -1},
            {"surface_tension": float("nan")},
        ):
            values = {"wavenumber": 4.0, "depth": 0.065, **kwargs}
            with self.assertRaises(ValueError):
                gravity_capillary_frequency(**values)


@unittest.skipIf(np is None, "Optional NumPy free-surface backend unavailable")
class FreeSurfaceTests(unittest.TestCase):
    def test_analytical_gravity_and_capillary_pressure_and_frequencies(self):
        reference = importlib.import_module("studies.water.003_free_surface.reference")
        self.assertTrue(reference.check_cells()["passed"])

    @unittest.skipUnless(importlib.util.find_spec("ngsolve"), "Optional NGSolve unavailable")
    def test_independent_neumann_potential_and_capillary_cell(self):
        reference = importlib.import_module("studies.water.003_free_surface.reference")
        self.assertTrue(reference.ngsolve_cell(mesh_sizes=(0.25,))["passed"])

    def test_frozen_wall_benchmark_conserves_volume_and_pressure_gauge(self):
        surface = GraphSurface(0.72, 0.58, domain="rectangle")
        space = SimpleNamespace(active=(0,), evaluate=lambda x, y: (np.ones((len(x), 1)),))
        coefficients = np.zeros((3, 1, 1))
        coefficients[2, 0, 0] = 1
        wall = CachedModes(surface, space, coefficients, np.array([10.0]), np.array([2.0]), {})
        system = assemble_free_surface(
            surface,
            ColumnWater(0.065),
            wall_modes=wall,
            surface_degree=2,
            settings=PotentialSettings(4, 2),
        )
        self.assertAlmostEqual(system.mass[0, 0], 2 + 1000 * system.volume_m3, places=9)
        self.assertAlmostEqual(system.elevations[0, 0], 1, places=12)
        self.assertAlmostEqual(
            system.stiffness[0, 0], 2 * (2 * pi * 10) ** 2 + 1000 * 9.81 * system.area_m2, places=8
        )
        a, q = system.pressure_weights([[0, 0, 0.045]])
        self.assertAlmostEqual(a[0, 0], 20, places=9)
        self.assertAlmostEqual(q[0, 0], 9810, places=9)
        self.assertLess(system.diagnostics["flux_compatibility_relative"], 1e-12)
        self.assertLess(system.diagnostics["maximum_relative_surface_mean"], 1e-12)
        # This checks the declared frozen-wall approximation, not a free translating vessel.

    def test_surface_tension_increases_water_eigenfrequencies(self):
        surface = GraphSurface(0.025, 0.02, domain="rectangle")
        water = ColumnWater(0.0035)
        kwargs = {"settings": PotentialSettings(8, 3), "surface_degree": 4}
        gravity = assemble_free_surface(surface, water, surface_tension=0, **kwargs)
        capillary = assemble_free_surface(surface, water, surface_tension=0.072, **kwargs)
        a = solve_free_modes(gravity, 6)[0]
        b = solve_free_modes(capillary, 6)[0]
        self.assertTrue(np.all(b > a))
        np.testing.assert_allclose(capillary.mass, gravity.mass)
        self.assertGreater(np.linalg.eigvalsh(capillary.mass).min(), 0)

    def test_inviscid_modal_energy_and_surface_volume_are_conserved(self):
        surface = GraphSurface(0.72, 0.58, 0.12, 0.006, 0.72)
        system = assemble_free_surface(
            surface, ColumnWater(0.065), surface_degree=3, settings=PotentialSettings(6, 2)
        )
        f, transform, diagnostics = solve_free_modes(system, 3)
        times = np.linspace(0, 20, 1001)
        omega, amplitude = 2 * pi * f[0], 0.001
        q = transform[:, :1] @ (amplitude * np.cos(omega * times))[None, :]
        v = transform[:, :1] @ (-amplitude * omega * np.sin(omega * times))[None, :]
        energy = 0.5 * np.sum(v * (system.mass @ v) + q * (system.stiffness @ q), axis=0)
        np.testing.assert_allclose(energy, energy[0], rtol=1e-11)
        x, y, w, _ = water_quadrature(
            surface,
            system.water,
            np.linspace(-0.72, 0.72, 11),
            np.linspace(-0.58, 0.58, 11),
            order=7,
            refinement=2,
        )
        eta = system.surface_weights(np.column_stack((x, y))) @ q
        self.assertLess(np.max(abs(w @ eta)), 1e-12)
        self.assertLess(diagnostics["eigen_relative_residual"], 1e-10)

    def test_probe_volume_and_positive_restoring_constraints(self):
        surface = GraphSurface(0.72, 0.58, domain="rectangle")
        system = assemble_free_surface(
            surface, ColumnWater(0.065), surface_degree=2, settings=PotentialSettings(4, 2)
        )
        for xyz in ([[0, 0, 0.065]], [[0, 0, 0]], [[1, 0, 0.01]], [[0, 0, np.nan]]):
            with self.assertRaises(ValueError):
                system.pressure_weights(xyz)
        with self.assertRaises(ValueError):
            system.surface_weights([[1, 0]])
        with self.assertRaises(ValueError):
            assemble_free_surface(surface, ColumnWater(0.065), gravity=0, surface_tension=0)
        for count in (0, True, len(system.mass) + 1):
            with self.assertRaises(ValueError):
                solve_free_modes(system, count)


if __name__ == "__main__":
    unittest.main()
