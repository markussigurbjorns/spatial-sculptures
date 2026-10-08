"""Blender adapter for cached gravity/capillary states; no numerical solve in Blender."""

import argparse
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
_adapter = None


def free_surface_frame_change(scene, _depsgraph=None):
    """Apply the precomputed metal, elevation and pressure frame on their shared clock."""
    if _adapter is None:
        return
    _adapter.wet_basin_frame_change(scene, _depsgraph)
    dry, _ = _adapter._adapter
    _, bundle, _, label = dry._adapter
    label.data.body = (
        f"GRAVITY / CAPILLARY WATER   t={scene['physical_time_s']:.3f} s\n"
        f"Frozen-shell reference / displacement x{bundle['metadata']['visual_gain']:g}"
    )


def build(bundle_path, config_path):
    """Reuse existing geometry/presentation with a new model label and one tagged handler."""
    import bpy

    from spatial_sculptures.blender.utils import HANDLER_TAG, remove_frame_handlers

    global _adapter
    _adapter = importlib.import_module("prototypes.001_resonant_surface.wet.build")
    basin, water = _adapter.build(bundle_path, config_path)
    basin.name = "Coupled free-surface basin"
    water.name = "Gravity capillary surface"
    remove_frame_handlers(("wet_basin_frame_change", "free_surface_frame_change"))
    setattr(free_surface_frame_change, HANDLER_TAG, True)
    bpy.app.handlers.frame_change_pre.append(free_surface_frame_change)
    scene = bpy.context.scene
    scene["model"] = "Linear shell + dynamic gravity/capillary water; frozen equilibrium"
    scene.frame_set(1)
    print(
        "Free-surface presentation ready. Space plays shared-clock hydrophone pressure and motion."
    )
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
