"""Shared-clock pressure/elevation export and portable free-surface bank checks."""

import importlib
import json
import tempfile
import unittest
import wave
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

try:
    import numpy as np
except ImportError:
    np = None


@unittest.skipIf(np is None, "Optional NumPy free-surface backend unavailable")
class FreeSurfaceToolTests(unittest.TestCase):
    def test_failed_stale_and_changed_artifacts_are_rejected(self):
        from tools.run_free_surface import load_verified_model
        from tools.validate_free_surface import BASELINE, POLICY, source_hashes

        config = importlib.import_module("prototypes.001_resonant_surface.dry.config")
        free = importlib.import_module("prototypes.001_resonant_surface.free_surface.config")
        settings = free.FreeSurfaceConfig()
        report = {"source_sha256": source_hashes(), "policy": POLICY, "passed": False}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "validation.json"
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "gates failed"):
                load_verified_model(path)
            report.update(passed=True, source_sha256={})
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "sources changed"):
                load_verified_model(path)
            report.update(
                source_sha256=source_hashes(),
                physical_parameters=asdict(config.load_config(BASELINE)),
                free_surface_parameters=asdict(settings),
                tested_stop_hz=settings.output_stop_hz,
                playback_artifacts={"modes": {"filename": "modes.npz", "sha256": "changed"}},
            )
            (path.parent / "modes.npz").write_bytes(b"changed")
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "artifact changed"):
                load_verified_model(path)

    def test_portable_joint_shapes_and_chunked_pressure_keep_both_pressure_terms(self):
        from tools.validate_free_surface import BASELINE

        config = importlib.import_module("prototypes.001_resonant_surface.dry.config")
        free = importlib.import_module("prototypes.001_resonant_surface.free_surface.config")
        model = importlib.import_module("prototypes.001_resonant_surface.free_surface.model")
        physical = replace(config.load_config(BASELINE), elements=(4, 4))
        settings = free.FreeSurfaceConfig(
            horizontal_degree=4,
            vertical_degree=2,
            surface_degree=2,
            dry_basis_count=8,
            playback_count=10,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bank = model.build_model(physical, settings, root)[0]
            mpath, fpath = root / "modes.npz", root / "fluid.npz"
            model.save_bank(mpath, fpath, bank)
            loaded = model.load_bank(mpath, fpath)
            xy = np.asarray(physical.pickups)
            np.testing.assert_allclose(loaded.surface_weights(xy), bank.surface_weights(xy))
            np.testing.assert_array_equal(loaded.pressure_q, bank.pressure_q)
            simulation = model.FreeSurfaceSimulation(physical, settings, loaded)
            times = np.array([0, 0.001, 0.01, 0.04, 0.3])
            q, v = simulation.response.trace(times, use_numpy=True)
            a = simulation.engine.accelerations(times, q, v)
            expected = bank.pressure_a @ a + bank.pressure_q @ q
            np.testing.assert_allclose(simulation.pressure_trace(times, chunk_samples=2), expected)
            self.assertGreater(np.max(abs(bank.pressure_q @ q)), 0)
            with self.assertRaises(ValueError):
                model.retained_bank(bank, 11)

    def test_curated_export_uses_one_clock_and_no_solver(self):
        from tools.run_free_surface import export_run, load_verified_model
        from tools.validate_free_surface import REPORT

        if not REPORT.exists():
            self.skipTest("Curated free-surface evidence unavailable")
        physical, settings, bank, _ = load_verified_model(REPORT)
        model = importlib.import_module("prototypes.001_resonant_surface.free_surface.model")
        simulation = model.FreeSurfaceSimulation(physical, settings, bank)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(
                model, "build_model", side_effect=AssertionError("Solver in playback")
            ):
                report, bundle, _ = export_run(REPORT, root, duration=0.1, preview=True)
            with wave.open(str(root / "hydrophones.wav"), "rb") as recording:
                self.assertEqual(recording.getnchannels(), 2)
                self.assertEqual(recording.getnframes(), 4800)
            with np.load(bundle, allow_pickle=False) as frames:
                times = frames["times"]
                q, v = simulation.response.trace(times, use_numpy=True)
                a = simulation.engine.accelerations(times, q, v)
                np.testing.assert_allclose(
                    frames["hydrophone_pressure_pa"], (bank.pressure_a @ a + bank.pressure_q @ q).T
                )
                weights = bank.surface_weights(frames["water_vertices"][:, :2])
                np.testing.assert_allclose(frames["surface_displacements_m"], (weights @ q).T)
                metadata = json.loads(str(frames["metadata"]))
                n = metadata["exposure_samples"]
                offsets = (np.arange(n) + 0.5) * physical.exposure_fraction / physical.fps / n
                average = (
                    simulation.response.trace((times[:, None] + offsets).ravel(), use_numpy=True)[0]
                    .reshape(settings.playback_count, 3, n)
                    .mean(axis=2)
                )
                np.testing.assert_allclose(
                    frames["water_displacements"], (weights @ average).T, atol=1e-11
                )
                self.assertTrue(np.all(frames["marker_displacements"][:, -2:] == 0))
            self.assertEqual(report["physical_duration_s"], 0.1)
            self.assertEqual(report["output_filter"]["stopband_hz"], 80)


if __name__ == "__main__":
    unittest.main()
