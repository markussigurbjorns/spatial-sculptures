"""Independent plate scaling, ODE residual, energy balance, and audio-unit checks."""

import importlib
import math
import tempfile
import unittest
import wave
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from spatial_sculptures.audio.synthesis import write_pickup_wav
from spatial_sculptures.simulation.modal import Mode, free_response, harmonic_response, modal_energy
from spatial_sculptures.simulation.plates import RectangularPlate

config_module = importlib.import_module("studies.plates.001_modal_reference.config")
simulation_module = importlib.import_module("studies.plates.001_modal_reference.simulation")


class ModalPhysicsTests(unittest.TestCase):
    def test_square_reference_and_scaling(self) -> None:
        plate = RectangularPlate(1, 1, 0.001, 200e9, 7800, 0.3)
        mode = plate.mode(1, 1, 0)
        nondimensional = mode.omega * math.sqrt(plate.density * plate.thickness / plate.rigidity)
        self.assertAlmostEqual(nondimensional, 2 * math.pi**2, places=12)
        self.assertAlmostEqual(
            replace(plate, thickness=0.002).mode(1, 1, 0).frequency_hz, 2 * mode.frequency_hz
        )
        self.assertAlmostEqual(
            replace(plate, length_x=2, length_y=2).mode(1, 1, 0).frequency_hz, mode.frequency_hz / 4
        )

    def test_boundary_and_mass_by_quadrature(self) -> None:
        plate = config_module.default_config().plate
        for x in (-plate.length_x / 2, plate.length_x / 2):
            self.assertAlmostEqual(plate.shape(2, 3, x, 0.1), 0.0)
        count = 64
        integral = (
            sum(
                plate.shape(
                    2,
                    3,
                    plate.length_x * ((i + 0.5) / count - 0.5),
                    plate.length_y * ((j + 0.5) / count - 0.5),
                )
                ** 2
                for i in range(count)
                for j in range(count)
            )
            * plate.length_x
            * plate.length_y
            / count**2
        )
        self.assertAlmostEqual(integral * plate.density * plate.thickness, plate.modal_mass)

    def test_free_response_and_energy_law(self) -> None:
        mode = Mode("test", 40, 2, 0.02)
        self.assertAlmostEqual(free_response(mode, 0, 0.001, 0.03)[0], 0.001)
        self.assertAlmostEqual(free_response(mode, 0, 0.001, 0.03)[1], 0.03)
        time, dt = 0.013, 1e-7
        q, v = free_response(mode, time, 0.001, 0.03)
        qp, vp = free_response(mode, time + dt, 0.001, 0.03)
        qm, vm = free_response(mode, time - dt, 0.001, 0.03)
        self.assertAlmostEqual((qp - qm) / (2 * dt), v, places=7)
        self.assertAlmostEqual(
            (vp - vm) / (2 * dt) + 2 * mode.decay * v + mode.omega**2 * q, 0, places=5
        )
        derivative = (modal_energy(mode, qp, vp) - modal_energy(mode, qm, vm)) / (2 * dt)
        self.assertAlmostEqual(derivative, -2 * mode.decay * mode.mass_kg * v**2, places=6)
        undamped = replace(mode, damping_ratio=0)
        expected = modal_energy(undamped, 0.001, 0.03)
        for time in (0, 0.01, 0.3, 4):
            q, v = free_response(undamped, time, 0.001, 0.03)
            self.assertAlmostEqual(modal_energy(undamped, q, v), expected, places=12)

    def test_forced_equation_including_undamped_resonance(self) -> None:
        for damping, frequency in ((0.01, 37.0), (0.0, 40.0), (0.0, 0.0)):
            mode = Mode("test", 40, 2, damping)
            self.assertAlmostEqual(harmonic_response(mode, 0, 1.2, frequency, 0.7)[0], 0)
            self.assertAlmostEqual(harmonic_response(mode, 0, 1.2, frequency, 0.7)[1], 0)
            time, dt = 0.017, 1e-7
            q, v = harmonic_response(mode, time, 1.2, frequency, 0.7)
            _, vp = harmonic_response(mode, time + dt, 1.2, frequency, 0.7)
            _, vm = harmonic_response(mode, time - dt, 1.2, frequency, 0.7)
            actual = (vp - vm) / (2 * dt) + 2 * mode.decay * v + mode.omega**2 * q
            expected = 1.2 / mode.mass_kg * math.cos(math.tau * frequency * time + 0.7)
            self.assertAlmostEqual(actual, expected, places=7)

    def test_center_patch_and_patch_bounds(self) -> None:
        plate = config_module.default_config().plate
        for m, n in ((2, 1), (1, 2), (2, 2), (4, 3)):
            self.assertAlmostEqual(plate.patch_projection(m, n, 0, 0, 0.05), 0, places=14)
        with self.assertRaises(ValueError):
            plate.patch_projection(1, 1, 0.71, 0, 0.05)

    def test_ringdown_and_scrubbing(self) -> None:
        simulation = simulation_module.PlateSimulation(config_module.default_config())
        first = simulation.step(0.1)
        simulation.step(3)
        self.assertEqual(first, simulation.step(0.1))
        previous = simulation.step(0).energy_joules
        for i in range(1, 400):
            state = simulation.step(i / 100)
            self.assertLessEqual(state.energy_joules, previous + 1e-15)
            previous = state.energy_joules

    def test_numpy_matches_scalar_with_switched_drives(self) -> None:
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("Optional NumPy is unavailable")
        for damping in (0, 0.005):
            config = config_module.default_config(driven=True)
            config.damping_ratio = damping
            fundamental = config.plate.mode(1, 1, damping).frequency_hz
            config.drives += (config_module.Drive(0.1, 0.1, fundamental, 0.25, start=0.2),)
            simulation = simulation_module.PlateSimulation(config)
            times = (0, 0.01, 0.1, 0.2, 0.25, 2)
            q, v = simulation.trace(times, use_numpy=True)
            for j, time in enumerate(times):
                state = simulation.step(time)
                for i in range(len(simulation.modes)):
                    self.assertAlmostEqual(q[i][j], state.displacements[i], places=12)
                    self.assertAlmostEqual(v[i][j], state.velocities[i], places=12)

    def test_invalid_physical_inputs_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Mode("bad", 40, 2, 1.0)
        for invalid in (float("nan"), -1.0):
            config = config_module.default_config()
            config.duration = invalid
            with self.assertRaises(ValueError):
                simulation_module.PlateSimulation(config)
        config = config_module.default_config()
        config.drives = (config_module.Drive(0, 0, -10, 1),)
        with self.assertRaises(ValueError):
            simulation_module.PlateSimulation(config)

    def test_one_mode_export_and_provenance(self) -> None:
        from tools.run_modal_study import load_study, run_study

        config, simulation_type = load_study()
        config.modes_per_axis = 1
        config.duration = 0.01
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("sys.modules", {"numpy": None}):
                report = run_study(config, simulation_type, Path(directory))
            self.assertEqual(report["mode_count"], 1)
            self.assertEqual(report["provenance"]["sampling_backend"], "stdlib")
            self.assertEqual(len(report["provenance"]["config_sha256"]), 64)
            self.assertTrue((Path(directory) / "contact_pickups.wav").is_file())

    def test_dependency_free_trace_and_wav(self) -> None:
        config = config_module.default_config()
        config.modes_per_axis = 2
        simulation = simulation_module.PlateSimulation(config)
        with patch.dict("sys.modules", {"numpy": None}):
            q, v = simulation.trace([0, 0.01, 0.02])
            self.assertEqual(v[0][1], simulation.step(0.01).velocities[0])
            channels = simulation.pickup_velocities(v)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pickups.wav"
            self.assertGreater(write_pickup_wav(path, channels, 48000), 0)
            with wave.open(str(path), "rb") as audio:
                self.assertEqual(
                    (audio.getnchannels(), audio.getframerate(), audio.getnframes()), (2, 48000, 3)
                )
            self.assertEqual(write_pickup_wav(path, [[0, 0], [0, 0]], 48000), 0)


if __name__ == "__main__":
    unittest.main()
