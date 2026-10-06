"""Integration validation run inside Blender, independent of pytest.

blender --background --factory-startup --python-exit-code 1 --python tests/validate_blender.py
"""

import importlib
import math
import runpy
import sys
import tempfile
from pathlib import Path


def main() -> None:
    import bpy

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "src"))
    entry = root / "prototypes" / "001_resonant_surface" / "build.py"
    sys.argv = ["blender"]  # Keep validation script arguments out of build.py's CLI.

    def unrelated_handler(_scene: object) -> None:
        pass

    bpy.app.handlers.frame_change_pre.append(unrelated_handler)
    runpy.run_path(str(entry), run_name="__main__")
    first_names = sorted(obj.name for obj in bpy.context.scene.objects)
    first_counts = (len(bpy.data.meshes), len(bpy.data.materials))
    # Re-execute the actual entry script rather than only calling a cached build function.
    runpy.run_path(str(entry), run_name="__main__")
    assert sorted(obj.name for obj in bpy.context.scene.objects) == first_names
    assert (len(bpy.data.meshes), len(bpy.data.materials)) == first_counts
    handlers = [
        handler
        for collection in (bpy.app.handlers.frame_change_pre, bpy.app.handlers.frame_change_post)
        for handler in collection
        if handler.__name__ == "resonant_surface_frame_change"
    ]
    assert len(handlers) == 1, handlers
    assert unrelated_handler in bpy.app.handlers.frame_change_pre

    scene = bpy.context.scene
    water = bpy.data.objects["Water surface"]
    droplet = bpy.data.objects["Water droplet"]
    assert len(water.data.vertices) == 6913
    assert len(water["base_coordinates"]) == 3 * 6913
    assert not water.data.validate()
    assert any(mod.type == "SOLIDIFY" for mod in bpy.data.objects["Resonant basin"].modifiers)
    assert any(mod.type == "BEVEL" for mod in bpy.data.objects["Resonant basin"].modifiers)
    assert scene.frame_start == 1 and scene.frame_end == 600

    scene.frame_set(91)  # t=3.0 s: droplet is falling.
    assert not droplet.hide_render and not droplet.hide_viewport
    assert 0.785 < droplet.location.z < 1.45
    scene.frame_set(97)  # t=3.2 s: impact and the start of its ripple.
    assert droplet.hide_render and droplet.hide_viewport
    scene.frame_set(106)
    forward = [tuple(vertex.co) for vertex in water.data.vertices]
    scene.frame_set(12)
    scene.frame_set(106)
    backward = [tuple(vertex.co) for vertex in water.data.vertices]
    assert forward == backward, "Timeline scrubbing accumulated deformation"
    assert all(math.isfinite(axis) for vertex in forward for axis in vertex)
    base = water["base_coordinates"]
    assert all(abs(base[index] - 0.785) < 1e-6 for index in range(2, len(base), 3))
    assert max(abs(vertex[2] - 0.785) for vertex in forward) > 0.0001

    for frame in (97, 193, 289, 385, 481, 577):
        scene.frame_set(frame)
        assert droplet.hide_render, f"Droplet was visible at impact frame {frame}"

    export = importlib.import_module("tools.export_mesh")
    with tempfile.TemporaryDirectory(prefix="spatial-sculptures-export-") as directory:
        output = Path(directory) / "basin.stl"
        export.export_mesh("Resonant basin", output)
        content = output.read_text()
        assert content.startswith("solid spatial_sculptures\n")
        assert content.count("facet normal") > 1000

    prototype = importlib.import_module("prototypes.001_resonant_surface.build")
    sculpture = prototype.build(prototype.load_config("002_close_frequencies"))
    assert scene.render.fps == 240 and scene.frame_end == 14400
    assert [obj["frequency_hz"] for obj in sculpture.exciters] == [59, 59.08, 59.17]
    bpy.app.handlers.frame_change_pre.remove(unrelated_handler)
    print(
        "Blender integration passed: rebuilds, callbacks, scrubbing, dripping, export, experiments."
    )


if __name__ == "__main__":
    main()
