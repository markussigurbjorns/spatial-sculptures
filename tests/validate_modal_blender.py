"""Check that Blender displays solver coordinates and rebuilds without duplicate callbacks."""

import importlib
import json
import sys
import tempfile
from dataclasses import asdict, replace
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
    # Named experiments and saved configurations feed the same visualization adapter.
    obj = entry.build(experiment="002_thin_3mm")
    simulation = entry._adapter[0]
    assert simulation.config.plate.thickness == 0.003
    assert abs(obj.modifiers["Reference thickness"].thickness - 0.003) < 1e-8
    assert bpy.context.scene["experiment"] == "002_thin_3mm"
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "configuration.json"
        config = simulation.config
        config.plate = replace(config.plate, thickness=0.007)
        config.impulses = tuple(replace(event, x=0.0, y=0.0) for event in config.impulses)
        path.write_text(json.dumps(asdict(config)))
        obj = entry.build(config_path=path)
        assert entry._adapter[0].config == config
        assert json.loads(bpy.context.scene["physical_configuration_json"]) == json.loads(
            json.dumps(asdict(config))
        )
        bpy.context.scene.frame_set(151)
        simulation, obj, base, _weights, _coordinates = entry._adapter
        for index in (240, 544, 710):
            x, y, z = base[index]
            expected = z + config.visual_gain * simulation.sample(x, y)
            assert abs(obj.data.vertices[index].co.z - expected) < 1e-7
        objects_before = sorted(obj.name for obj in bpy.context.scene.objects)
        parameters = json.loads(path.read_text())
        parameters["water"]["depth_m"] = 0.04
        path.write_text(json.dumps(parameters))
        try:
            entry.build(config_path=path)
        except ValueError as error:
            assert "water.depth_m" in str(error)
        else:
            raise AssertionError("Dry model silently accepted water loading")
        assert objects_before == sorted(obj.name for obj in bpy.context.scene.objects)
        assert (
            len([f for f in bpy.app.handlers.frame_change_pre if f.__name__ == entry._HANDLER_NAME])
            == 1
        )
    # Switching back to the sculpture removes the study's tagged callback as well.
    prototype = importlib.import_module("prototypes.001_resonant_surface.build")
    config = prototype.load_config(preview=True)
    config.osc["enabled"] = False
    prototype.build(config)
    assert not any(f.__name__ == entry._HANDLER_NAME for f in bpy.app.handlers.frame_change_pre)
    print(
        "Modal Blender validation passed: physical coordinates, experiment/config replay, "
        "unsupported-setting rejection, scrubbing, clean rebuilds."
    )


if __name__ == "__main__":
    main()
