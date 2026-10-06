"""Blender presentation of field snapshots, using a timeline or independent live clock."""

import warnings
from array import array
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any

from spatial_sculptures.blender.utils import (
    HANDLER_TAG,
    register_timer,
    remove_frame_handlers,
    remove_timers,
)
from spatial_sculptures.simulation.fields import FieldState
from spatial_sculptures.transport.osc import OSCTransport
from spatial_sculptures.transport.state_file import read_state

from .geometry import Sculpture
from .sampling import FieldSampler
from .simulation import ResonantField, droplet_state

FRAME_HANDLER_NAME = "resonant_surface_frame_change"
LIVE_TIMER_NAME = "resonant_surface_live_update"


@dataclass
class BlenderAdapter:
    """Presentation references; the independent runtime owns live sensors and OSC."""

    sculpture: Sculpture
    field: ResonantField
    transport: OSCTransport
    state_file: Path | None = None
    state: FieldState | None = None
    sampler: FieldSampler = dataclass_field(init=False)
    coordinates: Any = dataclass_field(init=False)
    base_z: Any = dataclass_field(init=False)

    def __post_init__(self) -> None:
        base = self.sculpture.water_base
        self.sampler = self.field.prepare([(x, y) for x, y, _z in base])
        if self.sampler.np is not None:
            self.coordinates = self.sampler.np.asarray(base, dtype="float32").copy()
            self.base_z = self.coordinates[:, 2].copy()
        else:
            self.coordinates = array("f", (axis for point in base for axis in point))
            self.base_z = tuple(z for _x, _y, z in base)

    def update(self, state: FieldState) -> None:
        """Sample a snapshot in one batch, then write the whole Blender mesh at once."""
        values = self.sampler.sample(state.time, exciters=state.exciter_states)
        if self.sampler.np is not None:
            self.coordinates[:, 2] = self.base_z + values
            coordinates = self.coordinates.ravel()
        else:
            for index, (z, displacement) in enumerate(zip(self.base_z, values, strict=True)):
                self.coordinates[3 * index + 2] = z + displacement
            coordinates = self.coordinates
        self.sculpture.water.data.vertices.foreach_set("co", coordinates)
        self.sculpture.water.data.update()
        visible, z = droplet_state(state.time, self.field.config)
        self.sculpture.droplet.location.z = z
        self.sculpture.droplet.hide_render = not visible
        self.sculpture.droplet.hide_viewport = not visible
        self.state = state


_adapter: BlenderAdapter | None = None


def resonant_surface_frame_change(scene: Any, _depsgraph: Any = None) -> None:
    """Deterministic timeline mode for scrubbing and rendering individual frames."""
    if _adapter is None or _adapter.state_file is not None:
        return
    animation = _adapter.field.config.animation
    time = (scene.frame_current - animation["frame_start"]) / animation["fps"]
    state = _adapter.field.step(time)
    _adapter.update(state)
    try:
        _adapter.transport.send_state(state)
    except OSError as error:
        warnings.warn(f"OSC output disabled after network error: {error}", stacklevel=2)
        _adapter.transport.close()
        _adapter.transport.enabled = False


def resonant_surface_live_update() -> float | None:
    """Consume the newest snapshot on Blender's main thread; never hold up its producer."""
    import bpy

    if _adapter is None or _adapter.state_file is None:
        return None
    try:
        state = read_state(_adapter.state_file)
    except FileNotFoundError:
        warnings.warn("Simulation state file disappeared; live display stopped.", stacklevel=2)
        return None
    if state != _adapter.state:
        _adapter.update(state)
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    config = _adapter.field.config
    return 1.0 / min(config.runtime["display_rate"], config.animation["fps"])


def setup_visualization(
    sculpture: Sculpture,
    field: ResonantField,
    transport: OSCTransport,
    *,
    state_file: Path | None = None,
) -> BlenderAdapter:
    """Replace callbacks and initialize either a live viewer or timeline playback."""
    import bpy

    global _adapter
    remove_frame_handlers((FRAME_HANDLER_NAME,))
    remove_timers((LIVE_TIMER_NAME,))
    if _adapter is not None:
        _adapter.transport.close()
    _adapter = BlenderAdapter(sculpture, field, transport, state_file=state_file)
    bpy.context.scene.render.use_lock_interface = True
    if state_file is not None:
        transport.close()
        transport.enabled = False  # Only the independent worker sends OSC in live mode.
        _adapter.update(read_state(state_file))
        register_timer(resonant_surface_live_update)
        print("Live display connected. Python owns the clock; timeline playback is unnecessary.")
    else:
        setattr(resonant_surface_frame_change, HANDLER_TAG, True)
        bpy.app.handlers.frame_change_pre.append(resonant_surface_frame_change)
        bpy.context.scene.frame_set(field.config.animation["frame_start"])
    print(f"Water sampling backend: {_adapter.sampler.backend} (cached and batched).")
    return _adapter
