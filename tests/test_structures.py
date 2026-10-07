"""Independent energy, rigid motion, boundary, convergence and modal-cache checks."""

import importlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

try:
    import numpy as np

    from spatial_sculptures.simulation.mode_cache import load_modes, modes_from_system, save_modes
    from spatial_sculptures.simulation.splines import SplineSpace, basis_1d, open_knots
    from spatial_sculptures.simulation.structures import (
        AttachedMass,
        GraphSurface,
        Material,
        Patch,
        Support,
        assemble_shell,
        patch_average,
        quadrature,
        solve_modes,
    )
except ImportError:
    np = None


@unittest.skipIf(np is None, "Optional numerical NumPy backend unavailable")
class StructureTests(unittest.TestCase):
    def test_partition_derivatives_and_patch_normalization(self):
        knots = open_knots(-1, 1, 4)
        x = np.linspace(-1, 1, 39)
        n, d, dd = basis_1d(knots, x)
        np.testing.assert_allclose(n.sum(axis=1), 1, atol=1e-14)
        np.testing.assert_allclose(d.sum(axis=1), 0, atol=1e-13)
        np.testing.assert_allclose(dd.sum(axis=1), 0, atol=1e-12)
        h = 1e-6
        xp = np.array([-0.81, -0.31, 0.12, 0.74])
        v, derivative, second = basis_1d(knots, xp)
        plus = basis_1d(knots, xp + h)[0]
        minus = basis_1d(knots, xp - h)[0]
        np.testing.assert_allclose((plus - minus) / (2 * h), derivative, atol=1e-9)
        np.testing.assert_allclose((plus - 2 * v + minus) / h**2, second, atol=3e-4)
        surface = GraphSurface(1, 1, 0.12, 0.006)
        space = SplineSpace.rectangle(1, 1, 4, 4)
        mean = patch_average(space, surface, Patch(0.2, -0.1, 0.05))
        self.assertAlmostEqual(float(mean.sum()), 1)
        with self.assertRaises(ValueError):
            patch_average(space, surface, Patch(0.99, 0.8, 0.1))

    def test_contact_span_refinement_preserves_rigid_motion(self):
        surface = GraphSurface(0.72, 0.58, 0.12, 0.006)
        supports = (Support(Patch(0.2, 0.1, 0.05), (0, 0, 0)),)
        system = assemble_shell(
            surface, Material(), 0.005, elements=(3, 3), supports=supports, patch_refinement=1
        )
        for expected in (0.175, 0.2, 0.225):
            self.assertTrue(np.any(np.isclose(system.space.knots_x, expected)))
        _, _, diagnostics = solve_modes(system, 8)
        self.assertEqual(diagnostics["discarded_rigid_or_near_zero_modes"], 6)
        self.assertLess(diagnostics["maximum_relative_eigen_residual"], 1e-6)

    def test_sparse_backend_requires_optional_dependency_or_matches_dense(self):
        surface = GraphSurface(0.72, 0.58, domain="rectangle")
        system = assemble_shell(
            surface, Material(), 0.005, elements=(5, 5), simply_supported_plate=True
        )
        if importlib.util.find_spec("scipy") is None:
            with self.assertRaisesRegex(ImportError, "optional"):
                solve_modes(system, 6, backend="scipy")
            return
        dense, c, _ = solve_modes(system, 6)
        sparse, v, diagnostics = solve_modes(system, 6, backend="scipy")
        np.testing.assert_allclose(sparse, dense, rtol=1e-8)
        np.testing.assert_allclose(v.T @ system.mass @ v, np.eye(6), atol=1e-8)
        self.assertLess(diagnostics["maximum_relative_eigen_residual"], 1e-6)

    def test_numerical_plate_convergence_and_shapes(self):
        from tools.validate_structure import validate_plate

        report = validate_plate()
        self.assertTrue(report["passed"])
        errors = [max(abs(v) for v in row["relative_frequency_errors"]) for row in report["meshes"]]
        self.assertEqual(errors, sorted(errors, reverse=True))

    def test_free_shell_has_six_rigid_modes(self):
        surface = GraphSurface(0.72, 0.58, 0.12, 0.006)
        system = assemble_shell(surface, Material(), 0.005, elements=(4, 4))
        frequencies, c, diagnostics = solve_modes(system, 8)
        self.assertEqual(diagnostics["discarded_rigid_or_near_zero_modes"], 6)
        np.testing.assert_allclose(c.T @ system.mass @ c, np.eye(8), atol=1e-10)
        self.assertLess(diagnostics["maximum_relative_eigen_residual"], 1e-6)
        x, y, w = quadrature(surface, 4, 4, 5)
        z, *_ = surface.geometry(x, y)
        n = system.space.evaluate(x, y)[0]
        coordinates = np.column_stack([x, y, z])
        for axis in np.eye(3):
            for values in (np.broadcast_to(axis, coordinates.shape), np.cross(axis, coordinates)):
                coefficients = np.linalg.lstsq(n, values, rcond=None)[0].T.ravel()
                energy = float(coefficients @ system.stiffness @ coefficients)
                scale = float(
                    np.abs(coefficients) @ np.abs(system.stiffness) @ np.abs(coefficients)
                )
                self.assertLess(abs(energy), scale * 1e-11 + 1e-8)

    def test_uniform_flat_membrane_energy(self):
        surface = GraphSurface(0.72, 0.58, domain="rectangle")
        material = Material()
        h = 0.005
        system = assemble_shell(surface, material, h, elements=(3, 3))
        x, y, w = quadrature(surface, 3, 3, 5)
        n = system.space.evaluate(x, y)[0]
        strain = 1e-5
        coefficients = np.zeros((3, len(system.space.active)))
        coefficients[0] = np.linalg.lstsq(n, x * strain, rcond=None)[0]
        actual = float(coefficients.ravel() @ system.stiffness @ coefficients.ravel() / 2)
        expected = (
            0.5
            * material.youngs_modulus
            / (1 - material.poisson_ratio**2)
            * h
            * system.area
            * strain**2
        )
        self.assertAlmostEqual(actual / expected, 1, places=9)

    def test_support_mass_and_curvature_change_computed_modes(self):
        surface = GraphSurface(0.72, 0.58, 0.12, 0.006)
        supports = tuple(
            Support(Patch(x, y, 0.035), (10000, 10000, 300000))
            for x in (-0.48, 0.48)
            for y in (-0.32, 0.32)
        )

        def solve(surface=surface, supports=supports, masses=()):
            return solve_modes(
                assemble_shell(
                    surface,
                    Material(),
                    0.005,
                    elements=(4, 4),
                    supports=supports,
                    attached_masses=masses,
                ),
                10,
            )[0]

        baseline = solve()
        stiff = solve(
            supports=tuple(
                replace(s, stiffness=tuple(2 * v for v in s.stiffness)) for s in supports
            )
        )
        heavy = solve(masses=(AttachedMass(Patch(-0.34, 0.14, 0.05), 2),))
        flat = solve(surface=replace(surface, rise=0, asymmetry=0))
        self.assertTrue(np.all(stiff >= baseline - 1e-6))
        self.assertTrue(np.all(heavy <= baseline + 1e-6))
        self.assertGreater(float(np.max(np.abs(flat / baseline - 1))), 0.1)

    def test_cache_roundtrip_and_normalization(self):
        surface = GraphSurface(0.72, 0.58, domain="rectangle")
        system = assemble_shell(
            surface, Material(), 0.005, elements=(4, 4), simply_supported_plate=True
        )
        modes = modes_from_system(system, 6, {"cache_key": "test"})
        x, y, _ = quadrature(surface, 8, 8, 5)
        peak = np.max(np.linalg.norm(modes.weights(x, y), axis=1), axis=0)
        np.testing.assert_allclose(peak, 1, atol=1e-12)
        c = modes.coefficients[2]
        np.testing.assert_allclose(c.T @ system.mass @ c, np.diag(modes.masses), atol=1e-8)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "modes.npz"
            save_modes(path, modes)
            restored = load_modes(path, expected_key="test")
            np.testing.assert_array_equal(
                modes.weights([0, 0.2], [0, -0.1]), restored.weights([0, 0.2], [0, -0.1])
            )
            with self.assertRaises(ValueError):
                load_modes(path, expected_key="changed")

    def test_cache_key_excludes_playback_but_tracks_structure(self):
        model = importlib.import_module("prototypes.001_resonant_surface.dry.model")
        config = importlib.import_module("prototypes.001_resonant_surface.dry.config").load_config()
        key = model.cache_identity(config)[0]
        config.duration = 5
        config.visual_gain = 20
        config.exciters = tuple(replace(e, frequency_hz=42, force_n=1) for e in config.exciters)
        self.assertEqual(key, model.cache_identity(config)[0])
        config.thickness = 0.003
        self.assertNotEqual(key, model.cache_identity(config)[0])
        config.water_depth_m = 0.02
        with (
            tempfile.TemporaryDirectory() as folder,
            self.assertRaisesRegex(ValueError, "water_depth"),
        ):
            model.get_modes(config, Path(folder))
            self.fail("Wet request silently accepted")


if __name__ == "__main__":
    unittest.main()
