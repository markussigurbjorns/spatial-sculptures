"""Blender adapter: consume Python field state, deform meshes, and present droplet motion."""

import warnings
from dataclasses import dataclass
from typing import Any

from spatial_sculptures.blender.utils import HANDLER_TAG, remove_frame_handlers
from spatial_sculptures.simulation.fields import FieldState
from spatial_sculptures.transport.osc import OSCTransport

from .geometry import Sculpture
from .simulation import ResonantField, droplet_state

FRAME_HANDLER_NAME = "resonant_surface_frame_change"


@dataclass
class BlenderAdapter:
    """Presentation references only; the field owns controls, equations and sensor state."""

    sculpture: Sculpture
    field: ResonantField
    transport: OSCTransport

    def update(self, state: FieldState) -> None:
        """Display a snapshot by sampling the field at undeformed mesh coordinates."""
        sculpture = self.sculpture
        for vertex, (x, y, z) in zip(
            sculpture.water.data.vertices, sculpture.water_base, strict=True
        ):
            vertex.co = (x, y, z + self.field.sample(x, y, state.time))
        sculpture.water.data.update()
        visible, z = droplet_state(state.time, self.field.config)
        sculpture.droplet.location.z = z
        sculpture.droplet.hide_render = not visible
        sculpture.droplet.hide_viewport = not visible


_adapter: BlenderAdapter | None = None


def resonant_surface_frame_change(scene: Any, _depsgraph: Any = None) -> None:
    """Use Blender's timeline as one clock source; the field can also run independently."""
    if _adapter is None:
        return
    animation = _adapter.field.config.animation
    time = (scene.frame_current - animation["frame_start"]) / animation["fps"]
    state = _adapter.field.step(time)
    _adapter.update(state)
    try:
        _adapter.transport.send_state(state)
    except OSError as error:
        # Optional network failures should not interrupt an otherwise usable visualizer.
        warnings.warn(f"OSC output disabled after network error: {error}", stacklevel=2)
        _adapter.transport.close()
        _adapter.transport.enabled = False


def setup_visualization(
    sculpture: Sculpture, field: ResonantField, transport: OSCTransport
) -> BlenderAdapter:
    """Replace old callbacks/transport and initialize the first displayed state."""
    import bpy

    global _adapter
    remove_frame_handlers((FRAME_HANDLER_NAME,))
    if _adapter is not None:
        _adapter.transport.close()
    _adapter = BlenderAdapter(sculpture, field, transport)
    setattr(resonant_surface_frame_change, HANDLER_TAG, True)
    bpy.app.handlers.frame_change_pre.append(resonant_surface_frame_change)
    bpy.context.scene.render.use_lock_interface = True
    bpy.context.scene.frame_set(field.config.animation["frame_start"])
    return _adapter
