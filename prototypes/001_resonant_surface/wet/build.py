"""Blender presentation adapter for precomputed wet metal, elevation and pressure frames."""

import argparse
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
_adapter = None


def wet_basin_frame_change(scene, _depsgraph=None):
    """Present supplied states only; no fluid/structural equations or audio synthesis."""
    if _adapter is None:
        return
    import numpy as np

    dry, water = _adapter
    dry.dry_basin_frame_change(scene, _depsgraph)
    _, bundle, _, label = dry._adapter
    index = max(0, min(scene.frame_current - 1, len(bundle["times"]) - 1))
    coordinates = bundle["water_vertices"].copy()
    coordinates[:, 2] += bundle["metadata"]["visual_gain"] * bundle["water_displacements"][index]
    water.data.vertices.foreach_set("co", np.asarray(coordinates, dtype=np.float32).ravel())
    water.data.update()
    scene["hydrophone_pressure_pa"] = bundle["hydrophone_pressure_pa"][index].tolist()
    label.data.body = (
        f"WET BASIN   t={scene['physical_time_s']:.3f} s\n"
        f"Pressure-release model / displacement x{bundle['metadata']['visual_gain']:g}"
    )


def build(bundle_path, config_path):
    """Reuse the dry prototype's presentation while substituting actual wet observations."""
    import bpy
    import numpy as np

    from spatial_sculptures.blender.geometry import create_mesh
    from spatial_sculptures.blender.materials import principled_material
    from spatial_sculptures.blender.utils import (
        HANDLER_TAG,
        cylinder_between,
        remove_frame_handlers,
        set_smooth,
    )

    global _adapter
    dry = importlib.import_module("prototypes.001_resonant_surface.dry.build")
    basin = dry.build(bundle_path, config_path)
    basin.name = "Numerical wet basin"
    _, bundle, markers, _ = dry._adapter
    cuts = np.r_[0, np.cumsum(bundle["water_face_sizes"])]
    faces = [
        bundle["water_face_indices"][a:b].tolist() for a, b in zip(cuts[:-1], cuts[1:], strict=True)
    ]
    material = principled_material(
        "Kinematic water", base_color=(0.07, 0.33, 0.48, 1), metallic=0.15, roughness=0.25
    )
    water = create_mesh(
        "Pressure-release water surface", bundle["water_vertices"].tolist(), faces, material
    )
    set_smooth(water)
    first_hydrophone = len(markers) - len(bundle["hydrophone_pressure_pa"][0])
    for i, (marker, _) in enumerate(markers):
        if marker.name.startswith("Virtual contact pickup"):
            marker.name = f"Virtual hydrophone {i - first_hydrophone + 1}"
            markers[i] = (marker, np.zeros(3))
            position = bundle["marker_reference"][i]
            # The probe remains submerged at its physical coordinate; this symbolic lead
            # makes its location visible through the opaque low-cost Workbench surface.
            cylinder_between(
                f"Hydrophone lead {i - first_hydrophone + 1}",
                position,
                (position[0], position[1], bundle["metadata"]["water_level_m"] + 0.065),
                0.002,
                marker.data.materials[0],
                vertices=12,
            )
    remove_frame_handlers((dry.HANDLER_NAME, "wet_basin_frame_change"))
    _adapter = (dry, water)
    setattr(wet_basin_frame_change, HANDLER_TAG, True)
    bpy.app.handlers.frame_change_pre.append(wet_basin_frame_change)
    scene = bpy.context.scene
    scene["model"] = (
        "Linear shell + 3D pressure-release potential fluid; no gravity/capillary waves"
    )
    scene["wet_observation_stop_hz"] = bundle["metadata"]["stop_hz"]
    if scene.sequence_editor:
        strips = (
            scene.sequence_editor.strips
            if hasattr(scene.sequence_editor, "strips")
            else scene.sequence_editor.sequences
        )
        for strip in strips:
            strip.name = "Model hydrophone-pressure audio"
    scene.frame_set(1)
    print("Wet basin presentation ready. Press Space for shared-clock hydrophone audio and motion.")
    return basin, water


def main():
    import bpy

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--render-directory", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    build(args.bundle, args.config)
    if args.render_directory:
        args.render_directory.mkdir(parents=True, exist_ok=True)
        scene = bpy.context.scene
        scene.render.filepath = str(args.render_directory / "frame_")
        scene.render.use_sequencer = False
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
