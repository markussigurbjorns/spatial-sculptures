"""Fluid energy/pressure invariants and a common finite-force physical response."""

import importlib
import importlib.util
import unittest
from types import SimpleNamespace

try:
    import numpy as np

    from spatial_sculptures.simulation.fluid_loading import ColumnWater
    from spatial_sculptures.simulation.fluid_potential import (
        PotentialSettings,
        assemble_potential,
        couple_wall_modes,
        loaded_modal_modes,
    )
    from spatial_sculptures.simulation.mode_cache import CachedModes
    from spatial_sculptures.simulation.structures import GraphSurface
except ImportError:
    np = None


@unittest.skipIf(np is None, "Optional NumPy potential-flow backend unavailable")
class PotentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = importlib.import_module("studies.water.002_potential_flow.reference")

    def test_manufactured_harmonic_fields_on_asymmetric_bowl(self):
        result = self.reference.manufactured_bowl()
        self.assertTrue(result["passed"])
        self.assertLess(result["maximum_absolute_pressure_weight_error"], 1e-8)

    def test_analytical_rigid_cell_pressure_and_full_inertia_matrix(self):
        result = self.reference.rigid_cell_reference()
        self.assertTrue(result["passed"])
        first, last = result["refinements"][0], result["refinements"][-1]
        self.assertLess(
            last["relative_pressure_weight_difference"],
            first["relative_pressure_weight_difference"] / 20,
        )

    @unittest.skipUnless(importlib.util.find_spec("ngsolve"), "Optional NGSolve unavailable")
    def test_independent_tetrahedral_cell_pressure(self):
        self.assertTrue(self.reference.ngsolve_rigid_cell(mesh_sizes=(0.25,))["passed"])

    def test_nonlocal_inertia_is_reciprocal_positive_and_density_scaled(self):
        surface = GraphSurface(0.72, 0.58, 0.12, 0.006, 0.72)
        fluid = assemble_potential(surface, ColumnWater(0.065), PotentialSettings(4, 1))
        flux = np.column_stack(
            (
                np.exp(-((fluid.x + 0.1) ** 2 + fluid.y**2) / 0.02),
                np.exp(-((fluid.x - 0.1) ** 2 + fluid.y**2) / 0.02),
            )
        )
        coefficients, mass, diagnostics = fluid.solve_flux(flux)
        np.testing.assert_array_equal(mass, mass.T)
        self.assertGreater(np.linalg.eigvalsh(mass).min(), 0)
        self.assertGreater(abs(mass[0, 1]), 0.01)
        self.assertLess(diagnostics["relative_equation_residual"], 1e-8)
        kinetic = 1000 * coefficients.T @ fluid.energy @ coefficients
        np.testing.assert_allclose(kinetic, mass, rtol=1e-9)
        fluid.water = ColumnWater(0.065, 500)
        np.testing.assert_allclose(fluid.solve_flux(flux)[1], mass / 2)

    def test_pressure_and_surface_come_from_same_translation_potential(self):
        surface = GraphSurface(0.72, 0.58, domain="rectangle")
        fluid = assemble_potential(surface, ColumnWater(0.065), PotentialSettings(0, 0))
        c, mass, _ = fluid.solve_flux(np.ones((len(fluid.x), 1)))
        pressure = fluid.observations(c, [[-0.2, -0.04, 0.045]])
        elevation = fluid.surface_weights(c, [[-0.2, -0.04]])
        self.assertAlmostEqual(mass[0, 0], 1000 * fluid.volume_m3, places=10)
        self.assertAlmostEqual(pressure[0, 0], 20, places=10)
        self.assertAlmostEqual(elevation[0, 0], 1, places=10)
        for point in ([0, 0, 0], [0, 0, 0.065], [1, 0, 0.04], [0, 0, np.nan]):
            with self.assertRaises(ValueError):
                fluid.observations(c, [point])
        with self.assertRaises(ValueError):
            fluid.surface_weights(c, [[1, 0]])
        with self.assertRaises(ValueError):
            fluid.solve_flux(np.zeros((1, 1)))

    def test_zero_added_inertia_recovers_dry_transfer_and_nonzero_lowers_modes(self):
        surface = GraphSurface(0.72, 0.58, domain="rectangle")
        space = SimpleNamespace(
            active=(0, 1), evaluate=lambda x, y: (np.column_stack((np.ones_like(x), x)),)
        )
        coefficients = np.zeros((3, 2, 2))
        coefficients[2] = np.eye(2)
        dry = CachedModes(
            surface, space, coefficients, np.array([10.0, 20.0]), np.array([2.0, 3.0]), {}
        )
        zero, p, diagnostics = loaded_modal_modes(dry, np.zeros((2, 2)), np.eye(2), 2)
        np.testing.assert_allclose(zero.frequencies, dry.frequencies, atol=1e-12)
        # Shape normalization may change; shape products / matched masses are invariant.
        x, y = np.array([0.2, -0.3]), np.array([0.0, 0.1])
        old, new = dry.weights(x, y)[:, 2], zero.weights(x, y)[:, 2]
        np.testing.assert_allclose(
            (new / zero.masses) @ new.T, (old / dry.masses) @ old.T, atol=1e-12
        )
        self.assertLess(diagnostics["maximum_relative_eigen_residual"], 1e-12)
        self.assertEqual(p.shape, (2, 2))
        wet, _, _ = loaded_modal_modes(dry, np.array([[1.0, 0.4], [0.4, 2.0]]), np.eye(2), 2)
        self.assertTrue(np.all(wet.frequencies < dry.frequencies))
        self.assertGreater(abs(wet.coefficients[2, 1, 0]), 0.001)

    def test_batched_wall_projection_matches_cartesian_shape_sampling(self):
        surface = GraphSurface(0.72, 0.58, 0.12, 0.006, 0.72)
        fluid = assemble_potential(surface, ColumnWater(0.065), PotentialSettings(2, 0))
        space = SimpleNamespace(
            active=(0, 1), evaluate=lambda x, y: (np.column_stack((np.ones_like(x), x)),)
        )
        coefficients = np.arange(12, dtype=float).reshape(3, 2, 2) / 10
        wall = CachedModes(surface, space, coefficients, np.array([10.0, 20.0]), np.ones(2), {})
        values = wall.weights(fluid.x, fluid.y)
        _, bx, by, *_ = surface.geometry(fluid.x, fluid.y)
        expected = fluid.solve_flux(
            values[:, 2] - bx[:, None] * values[:, 0] - by[:, None] * values[:, 1]
        )
        actual = couple_wall_modes(fluid, wall, chunk_points=73)
        np.testing.assert_allclose(actual[0], expected[0], atol=1e-10)
        np.testing.assert_allclose(actual[1], expected[1], atol=1e-10)

    def test_configuration_rejects_zero_volume_bad_counts_and_nonfinite_settings(self):
        config = importlib.import_module("prototypes.001_resonant_surface.wet.config").WetConfig
        for kwargs in (
            {"depth_m": 0},
            {"density_kg_m3": np.nan},
            {"pulse_seconds": 0},
            {"hydrophones": ((0.0, 0.0, -1.0),)},
            {"playback_count": 300},
        ):
            with self.assertRaises(ValueError):
                config(**kwargs)
        for kwargs in (
            {"horizontal_degree": True},
            {"vertical_degree": -1},
            {"integration_order": 3},
        ):
            with self.assertRaises(ValueError):
                PotentialSettings(**kwargs)
        with self.assertRaises(ValueError):
            assemble_potential(GraphSurface(1, 1, domain="rectangle"), ColumnWater(0))


@unittest.skipIf(np is None, "Optional NumPy wet response backend unavailable")
class WetResponseTests(unittest.TestCase):
    def setUp(self):
        module = importlib.import_module("prototypes.001_resonant_surface.wet.model")
        physical = SimpleNamespace(
            damping_ratio=0.005,
            exciters=[
                SimpleNamespace(
                    patch=None, direction=(0, 0, 1), start=0, frequency_hz=0, phase=0, force_n=0
                )
            ],
            impulses=[SimpleNamespace(exciter=0, time=0.05, impulse_ns=0.03)],
        )
        modes = SimpleNamespace(
            frequencies=np.array([10.0]),
            masses=np.array([2.0]),
            patch_weights=lambda *args: np.array([1.0]),
        )
        self.simulation = module.WetSimulation(
            physical, SimpleNamespace(pulse_seconds=0.01), modes, np.array([[2.0], [4.0]])
        )

    def test_finite_force_area_pressure_units_and_zero_prehistory(self):
        response = self.simulation.response
        self.assertEqual(response.impulses, ((),))
        start, end = response.drives[0]
        self.assertAlmostEqual(start[3] * (end[0] - start[0]), 0.03)
        times = np.array([0, 0.049, 0.05, 0.07])
        pressure = self.simulation.pressure_trace(times)
        np.testing.assert_array_equal(pressure[:, :2], 0)
        self.assertAlmostEqual(pressure[0, 2], 3.0)  # (3 N / 2 kg) * 2 Pa/(m/s²)
        np.testing.assert_allclose(pressure[1], 2 * pressure[0])

    def test_pressure_acceleration_agrees_with_velocity_derivative(self):
        times = np.array([0.052, 0.055, 0.065, 0.1])
        q, v = self.simulation.response.trace(times, use_numpy=True)
        h = 1e-7
        before = self.simulation.response.trace(times - h, use_numpy=True)[1]
        after = self.simulation.response.trace(times + h, use_numpy=True)[1]
        np.testing.assert_allclose(
            self.simulation.accelerations(times, q, v),
            (after - before) / (2 * h),
            rtol=1e-7,
            atol=1e-9,
        )

    def test_pressure_chunk_size_does_not_change_response(self):
        times = np.linspace(0, 0.3, 301)
        np.testing.assert_allclose(
            self.simulation.pressure_trace(times, chunk_samples=1),
            self.simulation.pressure_trace(times, chunk_samples=301),
            atol=1e-12,
        )
        for times, chunk in (([-1], 2), ([np.inf], 2), ([0], 0), ([0], True)):
            with self.assertRaises(ValueError):
                self.simulation.pressure_trace(times, chunk_samples=chunk)


if __name__ == "__main__":
    unittest.main()
