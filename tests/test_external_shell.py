"""External-shell contracts and analytic response; solver checks require optional NGSolve."""

import ast
import importlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

STUDY_NAME = "studies.plates.003_external_shell.model"
study = importlib.import_module(STUDY_NAME)
ROOT = Path(__file__).resolve().parents[1]
try:
    import numpy as np
except ImportError:
    np = None


def parameters():
    """Read a plain shared physical request; no production solver objects."""
    return json.loads(
        (ROOT / "prototypes/001_resonant_surface/dry/profiles/contact_200hz.json").read_text()
    )["parameters"]


class ExternalContractsTests(unittest.TestCase):
    def test_external_assembly_has_no_production_imports(self):
        tree = ast.parse(Path(study.__file__).read_text())
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
        self.assertFalse(
            any(name.startswith(("spatial_sculptures", "tools", "prototypes")) for name in names)
        )

    def test_parameter_boundary_is_explicit_and_does_not_mutate_request(self):
        base = parameters()
        unchanged = deepcopy(base)
        study.check_parameters(base)
        self.assertEqual(base, unchanged)
        for value, message in ((0.01, "dry"), (-0.01, "dry")):
            changed = deepcopy(base)
            changed["water_depth_m"] = value
            with self.assertRaisesRegex(ValueError, message):
                study.check_parameters(changed)
        changed = deepcopy(base)
        changed["exciters"][0]["patch"] = deepcopy(base["supports"][0]["patch"])
        with self.assertRaisesRegex(ValueError, "overlapping"):
            study.check_parameters(changed)
        changed = deepcopy(base)
        changed["exciters"][0]["direction"] = [0, 0, 2]
        with self.assertRaisesRegex(ValueError, "unit"):
            study.check_parameters(changed)

    def test_polygon_is_counterclockwise_and_refines_area(self):
        from math import pi

        surface = parameters()["surface"]
        areas = []
        for count in (32, 64, 128):
            points = study.outline(surface, count)
            area = (
                sum(
                    x * y2 - y * x2
                    for (x, y), (x2, y2) in zip(points, points[1:] + points[:1], strict=True)
                )
                / 2
            )
            self.assertGreater(area, 0)
            areas.append(area)
        exact = pi * surface["radius_x"] * surface["radius_y"]
        self.assertTrue(areas[0] < areas[1] < areas[2] < exact)
        self.assertLess((exact - areas[2]) / (exact - areas[1]), 0.26)

    def test_invalid_solver_settings_rejected(self):
        for option in (
            {"maxh": -1},
            {"rim_segments": 8},
            {"mode_count": 0},
            {"order": 2},
            {"bonus_intorder": -1},
            {"eigen_tolerance": float("nan")},
        ):
            with self.assertRaises(ValueError):
                study.Settings(**option)

    def test_unresolved_refinement_never_passes_on_agreement_alone(self):
        from tools.validate_external_dry_basin import REQUIRED_GATES, final_status

        self.assertEqual(
            final_status(
                {"passed": True}, {}, {"sampled_agreement_passed": True}, {"passed": True}
            ),
            "failed",
        )
        self.assertEqual(
            final_status(
                {"passed": True},
                {"mesh": {"passed": False}},
                {"sampled_agreement_passed": True},
                {"passed": True},
            ),
            "failed",
        )
        complete = {name: {"passed": True} for name in REQUIRED_GATES}
        self.assertEqual(
            final_status(
                {"passed": True}, complete, {"sampled_agreement_passed": True}, {"passed": True}
            ),
            "passed",
        )
        for missing in REQUIRED_GATES:
            partial = {key: value for key, value in complete.items() if key != missing}
            self.assertEqual(
                final_status(
                    {"passed": True}, partial, {"sampled_agreement_passed": True}, {"passed": True}
                ),
                "failed",
            )

    def test_runtime_missing_writes_explicit_failure_and_returns_two(self):
        # -S omits installed optional packages; it also verifies the CLI can start without NumPy.
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    str(ROOT / "tools/validate_external_dry_basin.py"),
                    "--output",
                    folder,
                ],
                cwd="/tmp",
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            report = json.loads((Path(folder) / "report.json").read_text())
            self.assertEqual(report["status"], "runtime_unavailable")
            self.assertFalse(report["solver_result_available"])


@unittest.skipIf(np is None, "Optional NumPy unavailable")
class ExternalResponseTests(unittest.TestCase):
    def test_mass_normalized_mobility_has_correct_force_scale_and_phase(self):
        from math import pi

        frequency, damping = 40.0, 0.005
        # Modal mass = 1, pickup residue 2, force residue 3. At resonance mobility is real.
        bank = study.ExternalModes(
            np.array([frequency]), np.array([[2.0]]), np.array([[3.0]]), None, None, None, None, {}
        )
        values = bank.mobility(np.array([0.0, frequency]), damping)
        self.assertEqual(values.shape, (1, 1, 2))
        self.assertEqual(values[0, 0, 0], 0j)
        self.assertAlmostEqual(values[0, 0, 1].real, 6 / (2 * damping * 2 * pi * frequency))
        self.assertAlmostEqual(values[0, 0, 1].imag, 0)
        opposite = study.ExternalModes(
            bank.frequencies, bank.pickup_weights, -bank.force_weights, None, None, None, None, {}
        )
        np.testing.assert_allclose(
            opposite.mobility([10.0, 40.0], damping), -bank.mobility([10.0, 40.0], damping)
        )

    def test_separate_response_intervals_expose_masked_error(self):
        from tools.validate_external_dry_basin import response_checks

        frequencies = np.array([20.0, 30.0, 40.0, 60.0, 80.0, 120.0, 160.0, 180.0, 200.0])
        reference = np.array([1e5, 1e5, 1e5, 100.0, 100.0, 100.0, 1.0, 1.0, 1.0])[None, None, :]
        candidate = reference.copy()
        candidate[..., frequencies >= 160] *= 2
        checks = response_checks(reference, candidate, frequencies, 0.10)
        self.assertTrue(checks["intervals"][0]["passed"])
        self.assertFalse(checks["passed"])
        self.assertFalse(checks["intervals"][-1]["passed"])

    def test_shape_grid_resolves_ellipse_area_and_rigid_translation(self):
        from math import pi

        from tools.validate_external_dry_basin import probe_grid, shape_check

        surface = parameters()["surface"]
        surface["rise"], surface["asymmetry"] = 0.0, 0.0
        x, _, area = probe_grid(surface)
        self.assertAlmostEqual(area.sum(), pi * surface["radius_x"] * surface["radius_y"])
        shapes = np.tile(np.eye(3)[None, :, :], (len(x), 1, 1))
        reference = {"frequencies": np.array([1.0, 2.0, 3.0]), "shapes": shapes}
        candidate = {"frequencies": reference["frequencies"], "shapes": -2 * shapes}
        self.assertTrue(shape_check(reference, candidate, area, 3)["passed"])


@unittest.skipUnless(
    importlib.util.find_spec("ngsolve") and importlib.util.find_spec("scipy"),
    "NGSolve/SciPy external runtime unavailable",
)
class ExternalRuntimeTests(unittest.TestCase):
    def test_analytical_plate_prerequisite(self):
        report = study.plate_check()
        self.assertTrue(report["passed"], report)

    def test_curved_geometry_preserves_graph_height_normal_and_improves_boundary(self):
        import ngsolve as ng

        from tools.validate_external_dry_basin import probe_grid

        request = parameters()
        graph = request["surface"]
        areas = []
        for order in (1, 2):
            mesh, deformation = study.make_mesh(
                request,
                study.Settings(maxh=0.18, rim_segments=32, geometry_order=order, mode_count=4),
            )
            xx, yy = ng.x / graph["radius_x"], ng.y / graph["radius_y"]
            zx = (
                2 * graph["rise"] * xx + graph["asymmetry"] * (1 - 3 * xx * xx - yy * yy)
            ) / graph["radius_x"]
            zy = (2 * graph["rise"] * yy - 2 * graph["asymmetry"] * xx * yy) / graph["radius_y"]
            exact_normal = ng.CF((-zx, -zy, 1)) / ng.sqrt(1 + zx * zx + zy * zy)
            difference = exact_normal - ng.specialcf.normal(3)
            height_error = ng.Integrate(
                (ng.z - study.height(graph, ng.x, ng.y)) ** 2, mesh, ng.BND, order=16
            )
            normal_error = ng.Integrate(
                ng.InnerProduct(difference, difference), mesh, ng.BND, order=16
            )
            self.assertLess(height_error, 1e-18)
            self.assertLess(normal_error, 1e-18)
            areas.append(ng.Integrate(1, mesh, ng.BND, order=16))
            self.assertIsNotNone(deformation)
        exact_area = probe_grid(graph)[2].sum()
        self.assertLess(abs(areas[1] - exact_area), abs(areas[0] - exact_area) / 100)


if __name__ == "__main__":
    unittest.main()
