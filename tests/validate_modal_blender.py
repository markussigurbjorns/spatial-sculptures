"""Check that Blender displays solver coordinates and rebuilds without duplicate callbacks."""

import importlib
import sys
from pathlib import Path


def main() -> None:
    import bpy

    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root), str(root / "src")]
    entry = importlib.import_module("studies.plates.001_modal_reference.build")
    obj = entry.build()
    names = sorted(obj.name for obj in bpy.context.scene.objects)
    entry.build()
    assert names == sorted(obj.name for obj in bpy.context.scene.objects)
    callbacks = [f for f in bpy.app.handlers.frame_change_pre if f.__name__ == entry._HANDLER_NAME]
    assert len(callbacks) == 1
    bpy.context.scene.frame_set(151)  # 5 visual seconds => 0.1 physical seconds.
    simulation, obj, base, _weights, _coordinates = entry._adapter
    assert abs(simulation.state.time - 0.1) < 1e-12
    assert bpy.context.scene["visual_displacement_gain"] == 2000
    assert len(obj.data.vertices) == 1089
    for index in (0, 10, 240, 544, 710, 1088):
        x, y, z = base[index]
        expected = z + simulation.config.visual_gain * simulation.sample(x, y)
        assert abs(obj.data.vertices[index].co.z - expected) < 1e-7
    first = [tuple(v.co) for v in obj.data.vertices]
    bpy.context.scene.frame_set(51)
    bpy.context.scene.frame_set(151)
    assert first == [tuple(v.co) for v in obj.data.vertices]
    for _x, _y, z in (tuple(obj.data.vertices[i].co) for i in range(33)):
        assert abs(z - 0.72) < 1e-7
    # Switching back to the sculpture removes the study's tagged callback as well.
    prototype = importlib.import_module("prototypes.001_resonant_surface.build")
    config = prototype.load_config(preview=True)
    config.osc["enabled"] = False
    prototype.build(config)
    assert not any(f.__name__ == entry._HANDLER_NAME for f in bpy.app.handlers.frame_change_pre)
    print(
        "Modal Blender validation passed: physical coordinates, units, scrubbing, clean rebuilds."
    )


if __name__ == "__main__":
    main()
