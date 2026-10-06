"""Check Blender-free sensors/state, deterministic sampling, and visual preservation."""

import importlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from spatial_sculptures.simulation.sensors import VirtualSensor

prototype = importlib.import_module("prototypes.001_resonant_surface.build")
simulation = importlib.import_module("prototypes.001_resonant_surface.simulation")


class FieldStateTests(unittest.TestCase):
    def test_generic_sensor_samples_position_time_and_gain(self) -> None:
        sensor = VirtualSensor("probe", 0.2, -0.1, gain=2)
        self.assertAlmostEqual(sensor.sample(lambda x, y, time: x + 2 * y + time, 3), 6)

    def test_sensors_sample_the_actual_hydrophone_positions(self) -> None:
        config = prototype.load_config()
        field = simulation.ResonantField(config)
        state = field.step(3.5)
        self.assertEqual(
            [sensor.name for sensor in state.sensor_states], ["hydrophone_1", "hydrophone_2"]
        )
        for sensor, (x, y) in zip(state.sensor_states, config.hydrophones, strict=True):
            self.assertEqual(sensor.amplitude, field.sample(x, y))
        self.assertEqual(len(state.exciter_states), 3)
        self.assertEqual(state.exciter_states[1].frequency, 61.3)
        self.assertGreaterEqual(state.total_energy, 0)
        self.assertLessEqual(state.total_energy, state.max_displacement**2)

    def test_original_displacement_samples_are_preserved(self) -> None:
        # Recorded before refactoring the Blender-owned update loop.
        field = simulation.ResonantField(prototype.load_config())
        for x, y, time, expected in (
            (0, 0, 0, 0.0008427879084275031),
            (-0.2, -0.04, 3.5, -0.00409904007892307),
            (0.25, -0.1, 9.6, 0.000564035279193688),
            (0.1, 0.05, 3.5, -0.007444521091034382),
        ):
            field.step(time)
            self.assertAlmostEqual(field.sample(x, y), expected, places=14)

    def test_scrubbing_and_snapshot_independence(self) -> None:
        config = prototype.load_config()
        field = simulation.ResonantField(config)
        first = field.step(3.5)
        config.exciters[0]["frequency"] = 100
        field.step(1)
        self.assertEqual(field.step(3.5), first)
        self.assertEqual(first.exciter_states[0].frequency, 59)

    def test_metrics_are_independent_of_blender_resolution(self) -> None:
        fine = prototype.load_config()
        coarse = prototype.load_config()
        coarse.water["rings"] = 2
        coarse.water["segments"] = 8
        self.assertEqual(
            simulation.ResonantField(fine).step(3.5), simulation.ResonantField(coarse).step(3.5)
        )

    def test_silent_field_and_drop_envelope(self) -> None:
        config = prototype.load_config()
        for exciter in config.exciters:
            exciter["amplitude"] = 0
        config.water["irregularity"] = 0
        config.drip["ripple_amplitude"] = 0
        field = simulation.ResonantField(config)
        for time, expected_impact in ((3.1, 0), (3.2, 1), (3.26, 0.5), (3.4, 0), (9.6, 1)):
            state = field.step(time)
            self.assertEqual(state.total_energy, 0)
            self.assertEqual(state.max_displacement, 0)
            self.assertTrue(all(sensor.amplitude == 0 for sensor in state.sensor_states))
            self.assertAlmostEqual(state.drop_impact, expected_impact)

    def test_simulation_imports_with_blender_and_osc_dependencies_blocked(self) -> None:
        root = Path(__file__).resolve().parents[1]
        code = """
import importlib
import importlib.abc
import sys
class BlockConsumerImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('bpy', 'mathutils', 'pythonosc'):
            raise ImportError(fullname)
        if fullname.startswith('spatial_sculptures.blender') or fullname.endswith('.geometry'):
            raise ImportError(fullname)
sys.meta_path.insert(0, BlockConsumerImports())
for name in ('waves', 'fields', 'sensors', 'feedback', 'modal'):
    importlib.import_module('spatial_sculptures.simulation.' + name)
prototype = importlib.import_module('prototypes.001_resonant_surface.simulation')
config = importlib.import_module('prototypes.001_resonant_surface.config').default_config()
assert len(prototype.ResonantField(config).step(3.5).sensor_states) == 2
assert 'bpy' not in sys.modules
"""
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(root), str(root / "src"))))
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=directory,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
