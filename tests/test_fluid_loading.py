"""Water-volume, inertia, dry-limit and independent finite-depth reference checks."""

import importlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

try:
    import numpy as np

    from spatial_sculptures.simulation.fluid_loading import (
        ColumnWater,
        column_loading,
        floor_minimum,
        pressure_release_mass_per_area,
        with_column_water,
    )
    from spatial_sculptures.simulation.structures import GraphSurface, Material, assemble_shell
except ImportError:
    np = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(np is None, "Optional NumPy water-loading backend unavailable")
class FluidLoadingTests(unittest.TestCase):
    def test_study_configuration_rejects_invalid_integration_or_depths(self):
        config = importlib.import_module(
            "prototypes.001_resonant_surface.water_loading.config"
        ).LoadingStudyConfig
        for kwargs in (
            {"depths_m": ()},
            {"depths_m": (0.01, 0.01)},
            {"depths_m": (-0.01,)},
            {"integration_order": 3},
            {"integration_refinement": True},
            {"density_kg_m3": float("nan")},
        ):
            with self.assertRaises(ValueError):
                config(**kwargs)

    def test_flat_inertia_is_vertical_and_matches_areal_mass(self):
        surface = GraphSurface(0.72, 0.58, domain="rectangle")
        system = assemble_shell(surface, Material(), 0.005, elements=(3, 3))
        water = ColumnWater(0.02)
        loading = column_loading(system, water)
        count = len(system.space.active)
        np.testing.assert_array_equal(loading.matrix[: 2 * count], 0)
        ratio = water.density_kg_m3 * water.depth_m / (Material().density * 0.005)
        np.testing.assert_allclose(
            loading.matrix[2 * count :, 2 * count :],
            ratio * system.mass[2 * count :, 2 * count :],
            rtol=1e-12,
            atol=1e-12,
        )
        self.assertAlmostEqual(loading.volume_m3, 4 * 0.72 * 0.58 * 0.02, places=12)

    def test_zero_depth_preserves_dry_mass_stiffness_and_input(self):
        system = assemble_shell(
            GraphSurface(0.72, 0.58, 0.12, 0.006), Material(), 0.005, elements=(3, 3)
        )
        original = system.mass.copy()
        wet, loading = with_column_water(system, ColumnWater(0))
        np.testing.assert_array_equal(wet.mass, original)
        np.testing.assert_array_equal(system.mass, original)
        np.testing.assert_array_equal(wet.stiffness, system.stiffness)
        np.testing.assert_array_equal(loading.matrix, 0)
        self.assertEqual(loading.water_mass_kg, 0)

    def test_parabolic_volume_and_rigid_translation_inertia(self):
        surface = GraphSurface(0.72, 0.58, 0.12)
        system = assemble_shell(surface, Material(), 0.005, elements=(3, 3))
        water = ColumnWater(0.065)
        loading = column_loading(system, water, order=8, refinement=3)
        rx, ry, rise, depth = surface.radius_x, surface.radius_y, surface.rise, water.depth_m
        expected_volume = np.pi * rx * ry * depth**2 / (2 * rise)
        self.assertAlmostEqual(loading.volume_m3 / expected_volume, 1, places=6)
        # Independent ellipse integrals: X/Y column-flux inertia is not total water mass.
        expected_inertia = water.density_kg_m3 * np.array(
            [
                np.pi * ry / rx * depth**3 / 3,
                np.pi * rx / ry * depth**3 / 3,
                expected_volume,
            ]
        )
        vectors = np.kron(np.eye(3), np.ones((len(system.space.active), 1)))
        inertia = vectors.T @ loading.matrix @ vectors
        np.testing.assert_allclose(inertia, np.diag(expected_inertia), rtol=2e-6, atol=1e-7)
        self.assertGreater(loading.wetted_projected_area_m2, 0)
        self.assertLess(loading.wetted_projected_area_m2, np.pi * rx * ry)

    def test_tangential_wall_motion_has_no_column_inertia(self):
        surface = GraphSurface(0.72, 0.58, 0.12)
        system = assemble_shell(surface, Material(), 0.005, elements=(3, 3))
        loading = column_loading(system, ColumnWater(0.065))
        xy = np.linspace(-0.5, 0.5, 21)
        x, y = np.meshgrid(xy, xy)
        basis = system.space.evaluate(x.ravel(), y.ravel())[0]
        values = np.zeros((3, len(system.space.active)))
        values[0] = 1
        values[2] = np.linalg.lstsq(
            basis, 2 * surface.rise * x.ravel() / surface.radius_x**2, rcond=None
        )[0]
        vector = values.ravel()
        self.assertLess(abs(float(vector @ loading.matrix @ vector)), 1e-10)

    def test_inertia_is_symmetric_positive_and_scales_with_density(self):
        system = assemble_shell(
            GraphSurface(0.72, 0.58, 0.12, 0.006), Material(), 0.005, elements=(3, 3)
        )
        a = column_loading(system, ColumnWater(0.03, 500)).matrix
        b = column_loading(system, ColumnWater(0.03, 1000)).matrix
        np.testing.assert_array_equal(a, a.T)
        self.assertGreater(float(np.linalg.eigvalsh(a)[0]), -1e-10)
        np.testing.assert_allclose(b, 2 * a, atol=1e-12)

    def test_depth_is_above_lowest_point_and_asymmetric_footprint_refines(self):
        surface = GraphSurface(0.72, 0.58, 0.12, 0.006, 0.72)
        self.assertLess(floor_minimum(surface), surface.center_z)
        x = np.linspace(-surface.radius_x, surface.radius_x, 10001)
        self.assertLess(abs(floor_minimum(surface) - surface.geometry(x, 0)[0].min()), 1e-8)
        system = assemble_shell(surface, Material(), 0.005, elements=(3, 3))
        a = column_loading(system, ColumnWater(0.065), order=5, refinement=2)
        b = column_loading(system, ColumnWater(0.065), order=8, refinement=3)
        self.assertLess(np.linalg.norm(a.matrix - b.matrix) / np.linalg.norm(b.matrix), 0.001)
        self.assertAlmostEqual(a.surface_level_m - floor_minimum(surface), 0.065)

    def test_invalid_water_or_unsupported_geometry_is_rejected(self):
        for depth in (-1, np.inf, np.nan):
            with self.assertRaises(ValueError):
                ColumnWater(depth)
        for density in (0, -1, np.inf, np.nan):
            with self.assertRaises(ValueError):
                ColumnWater(0.02, density)
        for surface in (GraphSurface(1, 1, -0.1), GraphSurface(1, 1, 0.1, 0.05)):
            with self.assertRaisesRegex(ValueError, "convex"):
                floor_minimum(surface)
        system = assemble_shell(GraphSurface(0.72, 0.58, 0.12), Material(), 0.005, elements=(3, 3))
        with self.assertRaisesRegex(ValueError, "overflow"):
            column_loading(system, ColumnWater(0.13))
        for value in (True, 0, 1.5):
            with self.assertRaises(ValueError):
                column_loading(system, ColumnWater(0.02), refinement=value)

    def test_finite_depth_reference_matches_independent_potential_energy(self):
        water = ColumnWater(0.065)
        nodes, weights = np.polynomial.legendre.leggauss(40)
        z = (nodes + 1) * water.depth_m / 2
        for k in (0.1, 4.0, 12.0):
            # Integrate horizontal and vertical kinetic energy of the separated
            # Laplace solution; unit mean-square bottom velocity normalization.
            phi = np.sinh(k * (z - water.depth_m)) / (k * np.cosh(k * water.depth_m))
            vertical = np.cosh(k * (z - water.depth_m)) / np.cosh(k * water.depth_m)
            mass = (
                water.density_kg_m3 * water.depth_m / 2 * (weights @ (k**2 * phi**2 + vertical**2))
            )
            self.assertAlmostEqual(mass / pressure_release_mass_per_area(k, water), 1, places=12)
        self.assertEqual(pressure_release_mass_per_area(0, water), 65)
        self.assertEqual(pressure_release_mass_per_area(4, ColumnWater(0)), 0)

    def test_analytical_reference_reports_approximation_breakdown(self):
        reference = importlib.import_module("studies.water.001_column_loading.reference")
        rows = reference.analytical_cases()
        shallow = max(m["relative_frequency_approximation_error"] for m in rows[2]["modes"])
        deep = max(m["relative_frequency_approximation_error"] for m in rows[-1]["modes"])
        self.assertLess(shallow, 0.001)
        self.assertGreater(deep, 0.02)
        self.assertTrue(reference.check_plate_assembly()["passed"])

    @unittest.skipUnless(
        importlib.util.find_spec("ngsolve"), "Optional NGSolve reference unavailable"
    )
    def test_external_potential_cell_matches_analytic_masses(self):
        reference = importlib.import_module("studies.water.001_column_loading.reference")
        report = reference.check_potential_cell(mesh_sizes=(0.25, 0.18))
        self.assertTrue(report["passed"])
        self.assertLess(
            report["meshes"][-1]["maximum_relative_added_mass_error"],
            report["meshes"][0]["maximum_relative_added_mass_error"],
        )

    def test_cli_without_blender_or_external_solver_and_with_spaces(self):
        config = importlib.import_module(
            "prototypes.001_resonant_surface.dry.config"
        ).DryBasinConfig()
        config.elements, config.mode_count = (3, 3), 6
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            baseline = path / "baseline.json"
            baseline.write_text(json.dumps(asdict(config)))
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/study_water_loading.py"),
                    "--baseline",
                    str(baseline),
                    "--depths",
                    "0",
                    "0.02",
                    "--output",
                    str(path / "results with spaces"),
                ],
                cwd=path,
                capture_output=True,
                text=True,
                env={**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((path / "results with spaces/report.json").read_text())
            self.assertFalse(report["hydrophone_pressure_available"])
            self.assertFalse(report["wet_contact_band_validated"])
            self.assertEqual(report["external_potential_cell"]["status"], "not_requested")
            self.assertTrue(report["depth_cases"][0]["checks"]["zero_depth_recovers_dry_passed"])
