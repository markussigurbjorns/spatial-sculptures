"""Physical configuration boundaries and reproducible, dependency-free parameter experiments."""

import csv
import importlib
import json
import math
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from tools.run_modal_experiments import run_experiments
from tools.run_modal_study import load_study, run_study

config_module = importlib.import_module("studies.plates.001_modal_reference.config")
simulation_module = importlib.import_module("studies.plates.001_modal_reference.simulation")


class ModalExperimentTests(unittest.TestCase):
    def test_complete_configuration_roundtrip(self) -> None:
        config, simulation_type = load_study(driven=True)
        config.impulses = (
            replace(
                config.impulses[0], mounting=config_module.Mounting(force_direction=(0, 0, -1))
            ),
        )
        payload = json.loads(json.dumps(asdict(config)))
        restored = config_module.config_from_dict(payload)
        self.assertEqual(config, restored)
        self.assertEqual(simulation_type(config).step(0.17), simulation_type(restored).step(0.17))

    def test_future_physics_rejected_individually_before_output(self) -> None:
        cases = {
            "profile": config_module.Profile(kind="curved_basin", rise_m=0.12),
            "thickness_map": "assumed_thickness.csv",
            "supports": config_module.Supports(
                kind="local_springs",
                contacts=(config_module.Support((0.4, 0.3, 0), 0.01, 10000),),
            ),
            "water": config_module.Water(depth_m=0.04),
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "unsupported"
            for key, value in cases.items():
                config, simulation_type = load_study()
                setattr(config, key, value)
                with (
                    self.subTest(setting=key),
                    self.assertRaisesRegex(ValueError, "does not support"),
                ):
                    run_study(config, simulation_type, output, audio=False)
                self.assertFalse(output.exists())
                restored = config_module.config_from_dict(json.loads(json.dumps(asdict(config))))
                self.assertEqual(config, restored)

    def test_mounting_changes_sign_but_preserves_energy(self) -> None:
        config, simulation_type = load_study()
        original = simulation_type(config).step(0.013)
        event = config.impulses[0]
        config.impulses = (
            replace(event, mounting=config_module.Mounting(force_direction=(0, 0, -1))),
        )
        opposite = simulation_type(config).step(0.013)
        self.assertEqual(original.displacements, tuple(-q for q in opposite.displacements))
        self.assertEqual(original.energy_joules, opposite.energy_joules)
        for mounting in (
            config_module.Mounting(added_mass_kg=0.1),
            config_module.Mounting(stiffness_n_per_m=10000),
            config_module.Mounting(force_direction=(1, 0, 0)),
        ):
            config.impulses = (replace(event, mounting=mounting),)
            with self.assertRaisesRegex(ValueError, "excitation 1"):
                simulation_type(config)

    def test_named_thickness_experiments_follow_analytical_scaling(self) -> None:
        baseline, simulation_type = load_study(experiment="001_baseline")
        reference = simulation_type(baseline).modes[0]
        for name, ratio in (("002_thin_3mm", 0.6), ("003_thick_7mm", 1.4)):
            config, _ = load_study(experiment=name)
            mode = simulation_type(config).modes[0]
            self.assertAlmostEqual(mode.frequency_hz / reference.frequency_hz, ratio)
            self.assertAlmostEqual(mode.mass_kg / reference.mass_kg, ratio)
        fresh, _ = load_study()
        self.assertEqual(fresh.plate.thickness, 0.005)

    def test_center_mount_suppresses_even_modes(self) -> None:
        config, simulation_type = load_study(experiment="004_center_excitation")
        simulation = simulation_type(config)
        state = simulation.step(0)
        for (m, n), velocity in zip(simulation.indices, state.velocities, strict=True):
            if m % 2 == 0 or n % 2 == 0:
                self.assertLess(abs(velocity), 1e-17)

    def test_pickup_location_changes_observations_not_motion(self) -> None:
        baseline, simulation_type = load_study()
        changed, _ = load_study(experiment="007_shifted_pickups")
        original, moved = simulation_type(baseline), simulation_type(changed)
        self.assertEqual(original.step(0.03), moved.step(0.03))
        self.assertNotEqual(
            original.sample_velocity(*baseline.pickups[0]),
            moved.sample_velocity(*changed.pickups[0]),
        )

    def test_saved_run_replays_data_without_blender_numpy_or_sockets(self) -> None:
        config, simulation_type = load_study(experiment="002_thin_3mm")
        config.duration = 0.015
        config.modes_per_axis = 2
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first", Path(directory) / "second"
            with (
                patch.dict("sys.modules", {"numpy": None, "bpy": None}),
                patch("socket.socket", side_effect=AssertionError("No network is required")),
            ):
                report = run_study(config, simulation_type, first)
                restored, _ = load_study(config_path=first / "configuration.json")
                replay = run_study(restored, simulation_type, second)
            self.assertEqual(
                report["provenance"]["config_sha256"], replay["provenance"]["config_sha256"]
            )
            for name in ("response.csv", "modes.csv", "coupling.csv", "contact_pickups.wav"):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
            self.assertEqual(load_study(config_path=first / "report.json")[0], restored)
            with (first / "response.csv").open() as handle:
                samples = [
                    float(v["contact_pickup_1_velocity_m_per_s"]) for v in csv.DictReader(handle)
                ]
            stats = report["pickup_statistics"][0]
            self.assertEqual(stats["sampled_peak_velocity_m_per_s"], max(abs(v) for v in samples))
            self.assertAlmostEqual(
                stats["sampled_rms_velocity_m_per_s"],
                math.sqrt(sum(v * v for v in samples) / len(samples)),
            )

    def test_suite_writes_independent_configs_and_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "suite"
            with patch.dict("sys.modules", {"numpy": None}):
                reports = run_experiments(
                    output,
                    names=("001_baseline", "002_thin_3mm", "003_thick_7mm"),
                    duration=0.02,
                    modes=2,
                )
            with (output / "comparison.csv").open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 3)
            self.assertEqual(
                [r["parameters"]["plate"]["thickness"] for r in reports], [0.005, 0.003, 0.007]
            )
            self.assertEqual(len({r["config_sha256"] for r in rows}), 3)
            for report in reports:
                path = output / report["experiment"]
                self.assertTrue((path / "configuration.json").is_file())
                self.assertFalse((path / "contact_pickups.wav").exists())
            self.assertTrue((output / "comparison.md").is_file())
            self.assertEqual(
                len(json.loads((output / "comparison.json").read_text())["reports"]), 3
            )

    def test_invalid_selection_and_snapshot_are_clear_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "suite"
            for names in ((), ("001_baseline", "001_baseline"), ("001_baseline", "../config")):
                with self.assertRaises(ValueError):
                    run_experiments(output, names=names, duration=0.01, modes=1)
                self.assertFalse(output.exists())
            path = Path(directory) / "invalid.json"
            for payload in ([1, 2], {"unrecognized_physical_setting": 1}):
                path.write_text(json.dumps(payload))
                with self.assertRaises(ValueError):
                    load_study(config_path=path)
            path.write_text(json.dumps(asdict(load_study()[0])))
            with self.assertRaisesRegex(ValueError, "cannot be combined"):
                load_study(config_path=path, experiment="001_baseline")


if __name__ == "__main__":
    unittest.main()
