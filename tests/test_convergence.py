"""Independent reference, mode permutation/mixing and SI response-validation tests."""

import importlib
import itertools
import unittest
from dataclasses import asdict

try:
    import numpy as np

    from spatial_sculptures.simulation.convergence import (
        assignment,
        compare_modes,
        contact_transfer,
        relative_response_error,
    )
except ImportError:
    np = None


@unittest.skipIf(np is None, "Optional numerical NumPy backend unavailable")
class ConvergenceTests(unittest.TestCase):
    def test_global_assignment_agrees_with_exhaustive_search(self):
        scores = np.random.default_rng(5).random((4, 6))
        matching = assignment(scores)
        actual = sum(scores[i, j] for i, j in enumerate(matching))
        expected = max(
            sum(scores[i, j] for i, j in enumerate(p)) for p in itertools.permutations(range(6), 4)
        )
        self.assertAlmostEqual(actual, expected)

    def test_degenerate_subspaces_survive_rotation_permutation_and_scale(self):
        reference = np.eye(9)[:, :3].reshape(3, 3, 3)
        rotation = np.array([[0.6, -0.8, 0], [0.8, 0.6, 0], [0, 0, 1]])
        candidate = np.einsum("pcm,mn->pcn", reference, rotation)[:, :, [2, 0, 1]]
        candidate *= np.array([-4, 2, -3])
        result = compare_modes([10, 10, 20], reference, [20, 10, 10], candidate, np.ones(3))
        self.assertEqual([len(g["reference_indices"]) for g in result["groups"]], [2, 1])
        self.assertLess(result["groups"][0]["individual_MAC"][0], 1)
        for group in result["groups"]:
            self.assertAlmostEqual(group["minimum_subspace_MAC"], 1)
            self.assertAlmostEqual(group["maximum_relative_frequency_difference"], 0)

    def test_shape_or_frequency_errors_are_not_hidden_by_matching(self):
        reference = np.eye(9)[:, :3].reshape(3, 3, 3)
        candidate = reference.copy()
        candidate[1, 0, 2] = 0.5
        result = compare_modes([10, 20, 30], reference, [10, 20, 33], candidate, np.ones(3))
        self.assertAlmostEqual(result["groups"][2]["maximum_relative_frequency_difference"], 0.1)
        self.assertLess(result["groups"][2]["minimum_subspace_MAC"], 0.99)

    def test_velocity_transfer_matches_existing_harmonic_solution(self):
        from spatial_sculptures.simulation.modal import Mode, harmonic_amplitude

        mode = Mode("test", 45, 3, 0.02)
        sample = np.array([0, 20, 45, 60])
        actual = contact_transfer([45], [3], [[0.4]], [[0.7]], 0.02, sample)[0, 0]
        expected = np.array(
            [1j * 2 * np.pi * f * harmonic_amplitude(mode, 0.7, float(f), 0) * 0.4 for f in sample]
        )
        np.testing.assert_allclose(actual, expected, atol=1e-16)

    def test_complex_phase_and_gain_errors_and_silence(self):
        signal = np.ones((2, 3, 50), dtype=complex)
        np.testing.assert_allclose(relative_response_error(signal, signal * 1.5), 0.5)
        np.testing.assert_allclose(relative_response_error(signal, signal * 1j), np.sqrt(2))
        self.assertEqual(float(relative_response_error(np.zeros(4), np.zeros(4))), 0)
        self.assertTrue(np.isinf(relative_response_error(np.zeros(4), np.ones(4))))

    def test_disk_basis_orthogonality_and_derivatives(self):
        ritz = importlib.import_module("studies.plates.002_curved_shell_reference.ritz")
        surface = {"radius_x": 0.72, "radius_y": 0.58}
        basis = ritz.disk_polynomials(6)
        x, y, w = ritz.disk_quadrature(surface, 8, 32)
        values = ritz.evaluate(basis, x, y, 0.72, 0.58, orders=((0, 0),))[0]
        np.testing.assert_allclose(
            values.T @ (w[:, None] * values) / (np.pi * 0.72 * 0.58), np.eye(len(basis)), atol=1e-12
        )
        x, y = np.array([0.2, -0.1]), np.array([-0.13, 0.1])
        h = 1e-5
        v, dx, dy, dxx, dyy, dxy = ritz.evaluate(basis, x, y, 0.72, 0.58)
        plus = ritz.evaluate(basis, x + h, y, 0.72, 0.58, orders=((0, 0),))[0]
        minus = ritz.evaluate(basis, x - h, y, 0.72, 0.58, orders=((0, 0),))[0]
        np.testing.assert_allclose((plus - minus) / (2 * h), dx, atol=1e-7)
        np.testing.assert_allclose((plus - 2 * v + minus) / h**2, dxx, atol=1e-4)

    def test_independent_free_curved_shell_has_six_rigid_modes(self):
        ritz = importlib.import_module("studies.plates.002_curved_shell_reference.ritz")
        config = importlib.import_module("prototypes.001_resonant_surface.dry.config").load_config()
        config.supports, config.exciters = (), ()
        modes = ritz.solve(asdict(config), 6, 8)
        self.assertEqual(modes.diagnostics["discarded_rigid_modes"], 6)
        self.assertLess(modes.diagnostics["maximum_relative_eigen_residual"], 1e-6)

    def test_report_is_json_serializable_and_rejects_invalid_plan(self):
        import json

        from tools.validate_dry_basin import run_validation

        config = importlib.import_module("prototypes.001_resonant_surface.dry.config").load_config()
        config.elements, config.mode_count = (4, 4), 8
        result = run_validation(
            config,
            meshes=(4, 6),
            degrees=(6, 8),
            counts=(8, 16),
            bands=(5.0, 10.0),
            signal_duration=0.05,
        )
        json.dumps(result, allow_nan=False)
        self.assertEqual(result["parameters"]["water_depth_m"], 0)
        self.assertEqual(result["sampling"]["normalization"], "none; raw SI velocity per N s")
        with self.assertRaises(ValueError):
            run_validation(config, meshes=(4, 4), degrees=(6, 8), counts=(8, 16), bands=(5.0, 10.0))

    def test_accuracy_gate_rejects_failed_or_unexamined_band(self):
        from tools.validate_dry_basin import required_band_passes

        report = {"default_supported_sampled_band_hz": 10, "evaluated_bands_hz": [5, 10, 20]}
        self.assertFalse(required_band_passes(report, 20))
        self.assertFalse(required_band_passes(report, 7))
        self.assertTrue(required_band_passes(report, 10))
        report["default_supported_sampled_band_hz"] = None
        self.assertFalse(required_band_passes(report, 10))

    def test_empty_responses_and_dependent_shapes_are_rejected(self):
        with self.assertRaises(ValueError):
            relative_response_error(np.empty((2, 0)), np.empty((2, 0)))
        with self.assertRaises(ValueError):
            contact_transfer([10], [1], [[1]], [[1]], 0.01, [])
        duplicated = np.ones((4, 3, 2))
        with self.assertRaisesRegex(ValueError, "Dependent"):
            compare_modes([10, 10], duplicated, [10, 10], duplicated, np.ones(4))


if __name__ == "__main__":
    unittest.main()
