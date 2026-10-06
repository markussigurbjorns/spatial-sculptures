"""Verify wall-clock scheduling and producer independence from visual refreshes."""

import importlib
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from spatial_sculptures.simulation.fields import FieldState
from spatial_sculptures.simulation.runtime import run_clock
from spatial_sculptures.transport.state_file import read_state, write_state

ROOT = Path(__file__).resolve().parents[1]


def snapshot(time: float) -> FieldState:
    return FieldState(time, (), (), 0.0, 0.0)


class RuntimeTests(unittest.TestCase):
    def test_slow_tick_skips_deadlines_without_catch_up_burst(self) -> None:
        now = 0.0
        published = []

        class ClockStop:
            def is_set(self) -> bool:
                return False

            def wait(self, seconds: float) -> None:
                nonlocal now
                self_delay = max(0.0, seconds)
                now += self_delay

        def publish(state: FieldState) -> None:
            nonlocal now
            published.append(state.time)
            now += 0.025  # Work takes longer than the 10 ms tick budget.

        with patch("spatial_sculptures.simulation.runtime.time.monotonic", lambda: now):
            run_clock(snapshot, publish, tick_rate=100.0, duration=0.1, stop=ClockStop())
        self.assertEqual(len(published), 3)
        for actual, expected in zip(published, (0.0, 0.035, 0.07), strict=True):
            self.assertAlmostEqual(actual, expected)

    def test_atomic_snapshot_round_trip_keeps_latest_state(self) -> None:
        config = importlib.import_module("prototypes.001_resonant_surface.config")
        simulation = importlib.import_module("prototypes.001_resonant_surface.simulation")
        field = simulation.ResonantField(config.default_config())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            write_state(path, field.step(1.0))
            latest = field.step(3.5)
            write_state(path, latest)
            self.assertEqual(read_state(path), latest)
            self.assertEqual([p.name for p in path.parent.iterdir()], ["state.json"])

    def test_worker_progresses_while_display_is_idle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            with subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / "tools" / "run_simulation.py"),
                    "001_resonant_surface",
                    "--no-osc",
                    "--duration",
                    "0.6",
                    "--state-file",
                    str(path),
                ],
                cwd=directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ) as worker:
                deadline = time.monotonic() + 10.0
                while not path.exists() and worker.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(path.exists(), "Worker produced no state")
                before = read_state(path)
                time.sleep(0.12)  # No Blender, callbacks, acknowledgements or state reads.
                after = read_state(path)
                self.assertGreater(after.time - before.time, 0.05)
                stdout, stderr = worker.communicate(timeout=10)
                self.assertEqual(worker.returncode, 0, stderr)
                self.assertIn("OSC disabled", stdout)
                self.assertLess(read_state(path).time, 0.6)


if __name__ == "__main__":
    unittest.main()
