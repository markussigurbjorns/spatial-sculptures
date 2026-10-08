"""Wet evidence gates, resting-volume visualization and portable pressure playback."""

import importlib
import json
import tempfile
import unittest
import wave
from dataclasses import asdict
from pathlib import Path

try:
    import numpy as np

    from spatial_sculptures.simulation.fluid_loading import ColumnWater
    from spatial_sculptures.simulation.fluid_potential import PotentialSettings, make_basis
    from spatial_sculptures.simulation.structures import GraphSurface
except ImportError:
    np = None


@unittest.skipIf(np is None, "Optional NumPy wet backend unavailable")
class WetToolTests(unittest.TestCase):
    def test_water_mesh_follows_actual_asymmetric_resting_shoreline(self):
        from tools.run_wet_basin import water_mesh

        surface = GraphSurface(0.72, 0.58, 0.12, 0.006, 0.72)
        basis = make_basis(surface, ColumnWater(0.065), PotentialSettings(2, 0))
        vertices, faces = water_mesh(surface, basis, 4, 24)
        self.assertEqual(vertices.shape, (97, 3))
        self.assertEqual(len(faces), 96)
        np.testing.assert_array_equal(vertices[:, 2], basis.level)
        self.assertTrue(np.all(surface.contains(*vertices[:, :2].T)))
        floor = surface.geometry(*vertices[:, :2].T)[0]
        self.assertTrue(np.all(floor <= basis.level + 1e-12))
        np.testing.assert_allclose(floor[-24:], basis.level, atol=1e-12)
        self.assertGreater(abs(vertices[73, 0] + vertices[85, 0]), 0.001)

    def test_failed_and_stale_evidence_cannot_enable_export(self):
        from tools.run_wet_basin import load_verified_model
        from tools.validate_wet_basin import source_hashes

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "validation.json"
            path.write_text(json.dumps({"source_sha256": source_hashes(), "passed": False}))
            with self.assertRaisesRegex(ValueError, "gates failed"):
                load_verified_model(path)
            path.write_text(json.dumps({"source_sha256": {}, "passed": True}))
            with self.assertRaisesRegex(ValueError, "sources changed"):
                load_verified_model(path)

    def test_changed_portable_artifact_is_rejected_before_playback(self):
        from tools.run_wet_basin import load_verified_model
        from tools.validate_wet_basin import BASELINE, source_hashes

        config = importlib.import_module("prototypes.001_resonant_surface.dry.config")
        wet = importlib.import_module("prototypes.001_resonant_surface.wet.config").WetConfig()
        report = {
            "source_sha256": source_hashes(),
            "passed": True,
            "physical_parameters": asdict(config.load_config(BASELINE)),
            "wet_parameters": asdict(wet),
            "tested_stop_hz": wet.output_stop_hz,
            "playback_artifacts": {"modes": {"filename": "modes.npz", "sha256": "changed"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "validation.json"
            path.write_text(json.dumps(report))
            (path.parent / "modes.npz").write_bytes(b"changed archive")
            with self.assertRaisesRegex(ValueError, "artifact changed"):
                load_verified_model(path)

    def test_curated_model_exports_same_clock_pressure_and_surface_without_solver(self):
        from unittest.mock import patch

        from tools.run_wet_basin import export_run, load_verified_model
        from tools.validate_wet_basin import REPORT

        if not REPORT.exists():
            self.skipTest("Curated wet evidence not available")
        module = importlib.import_module("prototypes.001_resonant_surface.wet.model")
        physical, settings, modes, basis, potentials, pressure, _ = load_verified_model(REPORT)
        simulation = module.WetSimulation(physical, settings, modes, pressure)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                module, "build_model", side_effect=AssertionError("Solver in playback")
            ):
                report, bundle, _ = export_run(REPORT, Path(directory), duration=0.1, preview=True)
            with wave.open(str(Path(directory) / "hydrophones.wav"), "rb") as recording:
                self.assertEqual(recording.getnchannels(), 2)
                self.assertEqual(recording.getnframes(), 4800)
            with np.load(bundle, allow_pickle=False) as frames:
                times = frames["times"]
                np.testing.assert_allclose(times, np.arange(3) / 30)
                q, v = simulation.response.trace(times, use_numpy=True)
                expected_pressure = (pressure @ simulation.accelerations(times, q, v)).T
                np.testing.assert_allclose(frames["hydrophone_pressure_pa"], expected_pressure)
                metadata = json.loads(str(frames["metadata"]))
                n = metadata["exposure_samples"]
                offsets = (np.arange(n) + 0.5) * physical.exposure_fraction / physical.fps / n
                averaged_q = (
                    simulation.response.trace((times[:, None] + offsets).ravel(), use_numpy=True)[0]
                    .reshape(64, 3, n)
                    .mean(axis=2)
                )
                water_weights = basis.evaluate(*frames["water_vertices"].T)[1][2] @ potentials
                np.testing.assert_allclose(
                    frames["water_displacements"], (water_weights @ averaged_q).T, atol=1e-11
                )
                self.assertTrue(np.all(frames["marker_displacements"][:, -2:] == 0))
            self.assertEqual(report["output_filter"]["stopband_hz"], 80)
            self.assertGreater(report["wav_common_gain_per_pa"], 0)


if __name__ == "__main__":
    unittest.main()
