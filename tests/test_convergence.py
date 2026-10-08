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
        contact_impulses,
        contact_transfer,
        relative_response_error,
        resonance_grid,
        trapezoid_weights,
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

    def test_batched_contacts_preserve_every_force_path_and_retained_bank(self):
        from spatial_sculptures.simulation.modal import Mode
        from spatial_sculptures.simulation.mode_bank import ModalResponse

        frequencies, masses = [12, 47, 190], [3, 2, 0.4]
        pickups = np.array([[0.4, -0.3, 0.1], [-0.2, 0.7, 0.5]])
        forces = np.array([[0.7, 0.2, -0.6], [-0.1, 0.5, 0.3], [0.8, -0.5, 0.1]])
        times = np.linspace(0, 0.13, 81)
        actual = contact_impulses(
            frequencies, masses, pickups, forces, 0.02, times, (1, 2, 3), chunk_samples=7
        )
        for count in (1, 2, 3):
            bank = tuple(Mode(str(i), frequencies[i], masses[i], 0.02) for i in range(count))
            for exciter, projection in enumerate(forces):
                response = ModalResponse(
                    bank, [[(0.0, float(v))] for v in projection[:count]], [[] for _ in bank]
                )
                expected = pickups[:, :count] @ response.trace(times, use_numpy=True)[1]
                np.testing.assert_allclose(actual[count][:, exciter], expected, atol=2e-15)
        with self.assertRaises(ValueError):
            contact_impulses(frequencies, masses, pickups, forces, 0.02, times, (4,))
        with self.assertRaises(ValueError):
            contact_impulses(
                frequencies, masses, pickups, forces, 0.02, times, (1,), chunk_samples=0
            )

    def test_batched_velocity_observations_preserve_drives_and_impulse_times(self):
        from spatial_sculptures.simulation.modal import Mode
        from spatial_sculptures.simulation.mode_bank import ModalResponse

        response = ModalResponse(
            (Mode("a", 13, 2, 0.005), Mode("b", 105, 0.7, 0.02)),
            [[(0.003, 0.02), (0.06, -0.01)], [(0.021, -0.02)]],
            [[(0.02, 35, 0.2, 0.4)], [(0.04, 79, -0.4, 0.8)]],
        )
        weights = np.array([[0.4, -0.6], [0.7, 0.2]])
        times = np.linspace(0, 0.14, 157)
        expected = weights @ response.trace(times, use_numpy=True)[1]
        np.testing.assert_allclose(
            response.velocity_trace(times, weights, chunk_samples=9), expected, atol=2e-15
        )
        with self.assertRaises(ValueError):
            response.velocity_trace(times, [[1]], chunk_samples=9)
        with self.assertRaises(ValueError):
            response.velocity_trace(times, weights, chunk_samples=False)

    def test_interval_errors_expose_response_hidden_by_strong_lower_resonance(self):
        frequencies = np.array([20, 25, 30, 35, 40])
        reference = np.array([1e6, 1e6, 1, 1, 1], dtype=complex)
        candidate = reference.copy()
        candidate[3:] *= 2
        cumulative = relative_response_error(reference, candidate, trapezoid_weights(frequencies))
        upper = relative_response_error(
            reference[3:], candidate[3:], trapezoid_weights(frequencies[3:])
        )
        self.assertLess(float(cumulative), 0.01)
        self.assertGreater(float(upper), 0.10)

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

    def test_high_degree_reference_boundary_and_origin(self):
        ritz = importlib.import_module("studies.plates.002_curved_shell_reference.ritz")
        basis = ritz.disk_polynomials(48)
        values, dx, dy, dxx, dyy, dxy = ritz.evaluate(basis, [0, 0.72], [0, 0], 0.72, 0.58)
        for result in (values, dx, dy, dxx, dyy, dxy):
            self.assertTrue(np.all(np.isfinite(result)))
        for column, (n, m, imaginary) in enumerate(basis.indices):
            scale = np.sqrt((n + 1) * (1 if m == 0 else 2))
            self.assertAlmostEqual(values[1, column], 0 if imaginary else scale, places=10)
            self.assertAlmostEqual(
                dx[1, column],
                0 if imaginary else scale * (n * (n + 2) - m * m) / (2 * 0.72),
                places=7,
            )

    def test_recurrence_matches_independent_low_degree_power_formula(self):
        from math import factorial

        ritz = importlib.import_module("studies.plates.002_curved_shell_reference.ritz")
        basis = ritz.disk_polynomials(12)
        theta = np.linspace(0.1, 5.9, 35)
        radius = np.linspace(0.01, 0.99, 35)
        actual = ritz.evaluate(
            basis, radius * np.cos(theta), radius * np.sin(theta), 1, 1, orders=((0, 0),)
        )[0]
        for i, (n, m, imaginary) in enumerate(basis.indices):
            radial = sum(
                (-1) ** s
                * factorial(n - s)
                / (factorial(s) * factorial((n + m) // 2 - s) * factorial((n - m) // 2 - s))
                * radius ** (n - 2 * s)
                for s in range((n - m) // 2 + 1)
            )
            angle = np.sin(m * theta) if imaginary else np.cos(m * theta)
            expected = radial * angle * np.sqrt((n + 1) * (1 if m == 0 else 2))
            np.testing.assert_allclose(actual[:, i], expected, atol=2e-11)

    def test_weighted_error_is_independent_of_sample_density(self):
        for grid in (np.linspace(0, 1, 15), np.r_[0, 0.001, 0.01, 0.1, 0.8, 1]):
            w = trapezoid_weights(grid)
            self.assertAlmostEqual(float(w.sum()), 1)
            self.assertAlmostEqual(float(w @ grid), 0.5)
            self.assertAlmostEqual(
                float(relative_response_error(np.ones_like(grid), np.ones_like(grid) * 1j, w)),
                np.sqrt(2),
            )
        with self.assertRaises(ValueError):
            trapezoid_weights([0, 1, 1])

    def test_resonance_sampling_converges_for_narrow_peak(self):
        frequencies, damping = [4.3, 44.4], 0.005
        errors = []
        for density in (4, 8, 16):
            grid = resonance_grid(
                [frequencies, np.array(frequencies) * 1.001],
                damping,
                100,
                0.05,
                samples_per_half_width=density,
            )
            self.assertTrue(np.all(np.diff(grid) > 0))
            for f in frequencies:
                self.assertTrue(np.any(grid == f))
            a = contact_transfer(frequencies, [1, 1], [[1, 0.3]], [[1, 0.7]], damping, grid)
            b = contact_transfer(
                np.array(frequencies) * 1.001, [1, 1], [[1, 0.3]], [[1, 0.7]], damping, grid
            )
            errors.append(float(relative_response_error(a, b, trapezoid_weights(grid))[0, 0]))
        self.assertLess(abs(errors[-1] - errors[-2]), 2e-5)

    def test_reference_cache_reuses_and_tracks_degree(self):
        import tempfile
        from pathlib import Path

        ritz = importlib.import_module("studies.plates.002_curved_shell_reference.ritz")
        config = importlib.import_module("prototypes.001_resonant_surface.dry.config").load_config()
        with tempfile.TemporaryDirectory() as folder:
            one, path, reused = ritz.get_modes(asdict(config), 6, 8, Path(folder))
            two, other, reused_again = ritz.get_modes(asdict(config), 6, 8, Path(folder))
            self.assertFalse(reused)
            self.assertTrue(reused_again)
            self.assertEqual(path, other)
            np.testing.assert_array_equal(one.coefficients, two.coefficients)
            _, changed, _ = ritz.get_modes(asdict(config), 7, 8, Path(folder))
            self.assertNotEqual(path, changed)

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
            bands=(5.0, 10.0, 30.0),
            signal_duration=0.05,
            interval_edges=(20.0, 25.0, 30.0),
        )
        json.dumps(result, allow_nan=False)
        self.assertEqual(result["parameters"]["water_depth_m"], 0)
        self.assertEqual(result["sampling"]["normalization"], "none; raw SI velocity per N s")
        for row in result["meshes"]:
            for case in row["retained_counts"]:
                band = case["bands"][-1]
                self.assertEqual(band["audible_interval_hz"], [20, 30])
                self.assertEqual(
                    [v["interval_hz"] for v in band["interval_checks"]], [[20, 25], [25, 30]]
                )
                if not all(v["passed"] for v in band["interval_checks"]):
                    self.assertFalse(band["individual_band_checks_passed"])
                if any(
                    v["maximum_relative_L2"] is None or v["maximum_relative_L2"] > v["tolerance"]
                    for v in band["audible_interval_checks"].values()
                ):
                    self.assertFalse(band["individual_band_checks_passed"])
        with self.assertRaises(ValueError):
            run_validation(config, meshes=(4, 4), degrees=(6, 8), counts=(8, 16), bands=(5.0, 10.0))
        with self.assertRaisesRegex(ValueError, "Interval edges"):
            run_validation(
                config,
                meshes=(4, 6),
                degrees=(6, 8),
                counts=(8, 16),
                bands=(5.0, 30.0),
                interval_edges=(20.0, 25.0),
            )

    def test_accuracy_gate_rejects_failed_or_unexamined_band(self):
        from tools.validate_dry_basin import required_band_passes

        report = {"default_supported_sampled_band_hz": 10, "evaluated_bands_hz": [5, 10, 20]}
        self.assertFalse(required_band_passes(report, 20))
        self.assertFalse(required_band_passes(report, 7))
        self.assertTrue(required_band_passes(report, 10))
        report["default_supported_sampled_band_hz"] = None
        self.assertFalse(required_band_passes(report, 10))

    def test_band_below_first_resonance_still_allows_response_checks(self):
        from tools.validate_dry_basin import bands_for

        comparison = {
            "groups": [
                {
                    "reference_frequencies_hz": [6.0],
                    "maximum_relative_frequency_difference": 0.2,
                    "minimum_subspace_MAC": 0.8,
                }
            ]
        }
        self.assertTrue(bands_for(comparison, 5))
        self.assertFalse(bands_for(comparison, 10))
        self.assertFalse(bands_for({"groups": []}, 5))

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
