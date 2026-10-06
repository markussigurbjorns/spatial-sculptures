"""Check export clocks, physical pickup units, configuration replay and presentation."""

import importlib
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

try:
    import numpy as np
except ImportError:
    np = None


@unittest.skipIf(np is None, "Optional numerical NumPy backend unavailable")
class DryBasinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config_module = importlib.import_module("prototypes.001_resonant_surface.dry.config")
        cls.model = importlib.import_module("prototypes.001_resonant_surface.dry.model")
        from tools import run_dry_basin

        cls.tool = run_dry_basin
        cls.folder = tempfile.TemporaryDirectory(dir=cls.tool.ROOT / "data/fem")
        cls.config = cls.config_module.load_config()
        cls.config.elements = (4, 4)
        cls.config.duration = 0.2
        cls.modes, cls.path, _ = cls.model.get_modes(cls.config, Path(cls.folder.name))

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def export(self, output, **options):
        with patch.object(self.model, "get_modes", return_value=(self.modes, self.path, True)):
            return self.tool.export_run(self.config, output, **options)

    def test_audio_and_visuals_share_physical_response(self):
        with tempfile.TemporaryDirectory() as folder:
            report, bundle_path, _ = self.export(Path(folder) / "output", preview=True)
            simulation = self.model.DryBasinSimulation(self.config, self.modes)
            with wave.open(str(Path(folder) / "output/contact_pickups.wav"), "rb") as wav:
                self.assertEqual(wav.getnchannels(), 2)
                self.assertEqual(wav.getframerate(), 48000)
                self.assertEqual(wav.getnframes(), 9600)
                pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").reshape(-1, 2)
            for sample in (0, 37, 3000, 9599):
                state = simulation.step(sample / 48000)
                actual = simulation.pickup_velocities(np.asarray(state.velocities))
                expected = np.rint(actual * report["audio_gain_per_m_per_s"] * 32767)
                np.testing.assert_array_equal(pcm[sample], expected)
            with np.load(bundle_path, allow_pickle=False) as bundle:
                np.testing.assert_allclose(bundle["times"], np.arange(6) / 30)
                self.assertEqual(bundle["displacements"].shape, (6, 385, 3))
                self.assertAlmostEqual(report["physical_duration_s"], 9600 / 48000)
                self.assertAlmostEqual(report["visual_duration_s"], 6 / 30)
                np.testing.assert_allclose(
                    bundle["energies"],
                    [simulation.step(float(t)).energy_joules for t in bundle["times"]],
                )

    def test_exposure_average_and_slow_inspection_do_not_retime_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            report, bundle_path, _ = self.export(output, preview=True, inspection_speed=0.25)
            self.assertEqual(report["audio_samples"], 9600)
            self.assertEqual(report["frame_count"], 24)
            self.assertAlmostEqual(report["physical_duration_s"], 0.2)
            self.assertAlmostEqual(report["visual_duration_s"], 0.8)
            simulation = self.model.DryBasinSimulation(self.config, self.modes)
            with np.load(bundle_path, allow_pickle=False) as bundle:
                metadata = json.loads(str(bundle["metadata"]))
                frame = 7
                start = bundle["times"][frame]
                span = self.config.exposure_fraction * 0.25 / self.config.fps
                times = start + (np.arange(2000) + 0.5) * span / 2000
                q = simulation.trace(times)[0].mean(axis=1)
                vertices = bundle["vertices"]
                expected = np.einsum("pcm,m->pc", self.modes.weights(*vertices[:, :2].T), q)
                np.testing.assert_allclose(
                    bundle["displacements"][frame],
                    expected,
                    rtol=0,
                    atol=np.max(np.abs(expected)) * 0.01,
                )
                self.assertEqual(metadata["physical_seconds_per_visual_second"], 0.25)

    def test_saved_configuration_and_cached_modes_replay(self):
        from dataclasses import asdict

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps(asdict(self.config)))
            replay = self.config_module.load_config(path)
            self.assertEqual(replay, self.config)
            modes, cache_path, reused = self.model.get_modes(replay, Path(self.folder.name))
            self.assertTrue(reused)
            self.assertEqual(cache_path, self.path)
            one = self.model.DryBasinSimulation(self.config, self.modes).step(0.127)
            two = self.model.DryBasinSimulation(replay, modes).step(0.127)
            self.assertEqual(one, two)

    def test_invalid_settings_fail_before_cache_written(self):
        from copy import deepcopy
        from dataclasses import replace

        for change in (
            {"water_depth_m": 0.04},
            {"damping_ratio": 1.0},
            {"duration": float("nan")},
            {"exciters": (replace(self.config.exciters[0], direction=(0, 0, 2)),)},
        ):
            config = deepcopy(self.config)
            for key, value in change.items():
                setattr(config, key, value)
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):
                    self.model.get_modes(config, Path(folder))
                self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
