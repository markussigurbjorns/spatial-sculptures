"""Run the resonant field and OSC independently of Blender or any display refresh."""

import warnings
from pathlib import Path
from threading import Event

from spatial_sculptures.simulation.fields import FieldState
from spatial_sculptures.simulation.runtime import run_clock
from spatial_sculptures.transport.osc import OSCTransport
from spatial_sculptures.transport.state_file import write_state

from .config import PrototypeConfig
from .simulation import ResonantField


def run(
    config: PrototypeConfig,
    *,
    state_file: Path | None = None,
    duration: float | None = None,
    stop: Event | None = None,
) -> None:
    """Publish small snapshots and optional OSC on a dedicated wall clock."""
    field = ResonantField(config)
    transport = OSCTransport(**config.osc)
    if state_file is not None:
        state_file.parent.mkdir(parents=True, exist_ok=True)

    def publish(state: FieldState) -> None:
        # OSC goes out before local display exchange; Blender never acknowledges it.
        try:
            transport.send_state(state)
        except OSError as error:
            warnings.warn(f"OSC output disabled after network error: {error}", stacklevel=2)
            transport.close()
            transport.enabled = False
        if state_file is not None:
            write_state(state_file, state)

    print(
        f"Python simulation running at {config.runtime['tick_rate']:g} Hz; "
        f"OSC {'enabled' if config.osc['enabled'] else 'disabled'}.",
        flush=True,
    )
    try:
        run_clock(
            field.step, publish, tick_rate=config.runtime["tick_rate"], duration=duration, stop=stop
        )
    finally:
        transport.close()
