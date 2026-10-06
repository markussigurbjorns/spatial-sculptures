"""Small local latest-state exchange for independent processes, with atomic replacement.

Readers never block the producer and may skip snapshots. This is not a recording
format or an event queue. The single writer keeps its temporary file beside the
destination so replacement occurs on the same filesystem.
"""

import json
from dataclasses import asdict
from pathlib import Path

from spatial_sculptures.simulation.fields import ExciterState, FieldState, SensorState


def write_state(path: Path, state: FieldState) -> None:
    """Publish a complete JSON snapshot without exposing a partially written frame."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(asdict(state), allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def read_state(path: Path) -> FieldState:
    """Read one immutable snapshot; callers decide how to handle a missing producer."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sensor_states"] = tuple(SensorState(**sensor) for sensor in data["sensor_states"])
    data["exciter_states"] = tuple(ExciterState(**exciter) for exciter in data["exciter_states"])
    return FieldState(**data)
