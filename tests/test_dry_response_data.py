"""SI mobility exchange preserves phase, units, path coverage and provenance."""

import importlib
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None


@unittest.skipIf(np is None, "Optional numerical NumPy backend unavailable")
class ResponseDataTests(unittest.TestCase):
    def test_one_factor_variations_preserve_mass_material_and_original_config(self):
        config = importlib.import_module("prototypes.001_resonant_surface.dry.config").load_config()
        study = importlib.import_module("prototypes.001_resonant_surface.dry.sensitivity")
        original = asdict(config)
        for name in study.CASES:
            varied = study.configure(config, name)
            self.assertEqual(varied.material, config.material)
            self.assertEqual(varied.surface, config.surface)
            self.assertEqual(varied.thickness, config.thickness)
            self.assertEqual(varied.pickups, config.pickups)
            self.assertEqual(varied.damping_ratio, config.damping_ratio)
            self.assertEqual(
                [e.added_mass_kg for e in varied.exciters],
                [e.added_mass_kg for e in config.exciters],
            )
            self.assertEqual(asdict(config), original)
        with self.assertRaises(ValueError):
            study.configure(config, "unknown")

    def test_csv_roundtrip_and_missing_path_rejection(self):
        from tools.check_dry_response import read_csv, write_csv

        frequencies = np.array([20.0, 35.17, 80.0])
        values = np.arange(18).reshape(2, 3, 3) * (0.03 - 0.017j)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "response.csv"
            write_csv(path, frequencies, values)
            actual_f, actual = read_csv(path, 2, 3)
            np.testing.assert_array_equal(actual_f, frequencies)
            np.testing.assert_array_equal(actual, values)
            lines = path.read_text().splitlines()
            path.write_text("\n".join(lines[:-3]) + "\n")
            with self.assertRaisesRegex(ValueError, "Every pickup"):
                read_csv(path, 2, 3)

    def test_comparison_detects_gain_phase_hash_and_units_errors(self):
        from tools.check_dry_response import compare, digest, prepare, read_csv, write_csv

        config = importlib.import_module("prototypes.001_resonant_surface.dry.config").load_config()
        config.elements, config.mode_count = (4, 4), 8
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            config_path = folder / "configuration.json"
            config_path.write_text(json.dumps(asdict(config)))
            request = prepare(config_path, folder / "request", lower_hz=20, upper_hz=80, step_hz=2)
            model_data = request.parent / "model_mobility.csv"
            source_path = request.parent / "model_source.json"
            report = compare(request, model_data, source_path, folder / "self_check.json")
            self.assertTrue(report["sampled_agreement_passed"])
            self.assertEqual(report["source"]["kind"], "model_prediction")
            source = json.loads(source_path.read_text())
            source["kind"], source["source"] = (
                "synthetic_test",
                "Unit test: deliberate phase/gain changes",
            )
            frequencies, values = read_csv(model_data, 2, 3)
            supplied = folder / "supplied.csv"
            for factor, error in ((1.5, 0.5), (1j, np.sqrt(2))):
                write_csv(supplied, frequencies, values * factor)
                source["data_sha256"] = digest(supplied)
                source_path.write_text(json.dumps(source))
                report = compare(request, supplied, source_path, folder / "comparison.json")
                self.assertFalse(report["sampled_agreement_passed"])
                self.assertAlmostEqual(
                    report["intervals"][0]["maximum_relative_L2"], error / abs(factor)
                )
            source["units"] = "normalized WAV"
            source_path.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError, "Source metadata"):
                compare(request, supplied, source_path, folder / "wrong_units.json")
            source["units"] = "(m/s)/N"
            source["data_sha256"] = "wrong"
            source_path.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError, "Source metadata"):
                compare(request, supplied, source_path, folder / "wrong_hash.json")


if __name__ == "__main__":
    unittest.main()
