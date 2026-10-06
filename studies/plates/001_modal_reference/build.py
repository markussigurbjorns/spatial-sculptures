"""Blender inspection of the physical reference plate, with explicit slow motion and gain.

blender --python /absolute/path/to/studies/plates/001_modal_reference/build.py
This is an inspection view; it does not synchronize playback of the offline WAV.
"""

from __future__ import annotations

import argparse
import sys
from array import array
from pathlib import Path

if not __package__:
    root = Path(__file__).resolve().parents[3]
    sys.path[:0] = [str(root), str(root / "src")]
    __package__ = "studies.plates.001_modal_reference"

_HANDLER_NAME = "modal_reference_frame_change"
_adapter = None


def modal_reference_frame_change(scene, _depsgraph=None) -> None:
    if _adapter is None:
        return
    simulation, obj, base, weights, coordinates = _adapter
    config = simulation.config
    physical_time = (scene.frame_current - 1) / config.display_fps * config.visual_time_scale
    state = simulation.step(max(0.0, physical_time))
    for index, row in enumerate(weights):
        z = sum(w * q for w, q in zip(row, state.displacements, strict=True))
        coordinates[3 * index + 2] = base[index][2] + config.visual_gain * z
    obj.data.vertices.foreach_set("co", coordinates)
    obj.data.update()
    scene["physical_time_s"] = physical_time
    scene["retained_energy_j"] = state.energy_joules


def build(*, driven: bool = False):
    import bpy

    from spatial_sculptures.blender.camera import create_camera
    from spatial_sculptures.blender.materials import brushed_steel
    from spatial_sculptures.blender.utils import HANDLER_TAG, clear_scene

    from .config import default_config
    from .simulation import PlateSimulation

    global _adapter
    clear_scene((_HANDLER_NAME,))
    config = default_config(driven=driven)
    simulation = PlateSimulation(config)
    plate = config.plate
    count = 32
    base = tuple(
        (plate.length_x * (i / count - 0.5), plate.length_y * (j / count - 0.5), 0.72)
        for j in range(count + 1)
        for i in range(count + 1)
    )
    faces = []
    for j in range(count):
        for i in range(count):
            index = j * (count + 1) + i
            faces.append((index, index + 1, index + count + 2, index + count + 1))
    mesh = bpy.data.meshes.new("Reference plate mesh")
    mesh.from_pydata(base, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("Dry simply supported reference plate", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(brushed_steel())
    solidify = obj.modifiers.new("Reference thickness", "SOLIDIFY")
    solidify.thickness = plate.thickness
    solidify.offset = -1.0
    _adapter = (
        simulation,
        obj,
        base,
        [simulation.weights(x, y) for x, y, _z in base],
        array("f", (axis for point in base for axis in point)),
    )
    create_camera("Reference camera", (1.8, -2.4, 1.9), (0, 0, 0.72), lens=50)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.fps = config.display_fps
    scene.frame_start = 1
    scene.frame_end = round(config.duration / config.visual_time_scale * config.display_fps)
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 750
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene["model"] = "Dry reference plate; all edges simply supported; not the curved basin"
    scene["visual_displacement_gain"] = config.visual_gain
    scene["physical_seconds_per_visual_second"] = config.visual_time_scale
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.shading.type = "SOLID"
                area.spaces.active.region_3d.view_perspective = "CAMERA"
    setattr(modal_reference_frame_change, HANDLER_TAG, True)
    bpy.app.handlers.frame_change_pre.append(modal_reference_frame_change)
    scene.frame_set(1)
    print(
        f"Dry reference: {len(simulation.modes)} physical modes; "
        f"displacement x{config.visual_gain:g}, time x{config.visual_time_scale:g}."
    )
    return obj


def main() -> None:
    import bpy

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driven", action="store_true")
    parser.add_argument("--frame", type=int, default=1)
    parser.add_argument("--render-output", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    build(driven=args.driven)
    bpy.context.scene.frame_set(args.frame)
    if args.render_output:
        path = args.render_output.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        bpy.context.scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
