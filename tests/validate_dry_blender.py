"""Verify the dry adapter's coordinates, playback timing and rebuild cleanup in Blender."""

import importlib
import sys
import tempfile
from pathlib import Path


def main():
    import bpy
    import numpy as np

    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root), str(root / "src")]
    from tools.run_dry_basin import export_run

    config = importlib.import_module("prototypes.001_resonant_surface.dry.config").load_config()
    config.elements, config.mode_count, config.duration = (4, 4), 8, 0.2
    entry = importlib.import_module("prototypes.001_resonant_surface.dry.build")
    with tempfile.TemporaryDirectory() as folder:
        # Fixture generation is offline; the Blender adapter itself only reads these arrays.
        _, bundle, parameters = export_run(config, Path(folder) / "normal", preview=True)
        obj = entry.build(bundle, parameters)
        names = sorted(o.name for o in bpy.context.scene.objects)
        entry = importlib.reload(entry)
        obj = entry.build(bundle, parameters)
        scene = bpy.context.scene
        assert names == sorted(o.name for o in scene.objects)
        callbacks = [
            f for f in bpy.app.handlers.frame_change_pre if f.__name__ == entry.HANDLER_NAME
        ]
        assert len(callbacks) == 1
        assert scene.sync_mode == "AUDIO_SYNC"
        strips = scene.sequence_editor.strips
        assert len(strips) == 1 and strips[0].frame_start == 1
        assert abs(strips[0].volume - 0.2) < 1e-6
        scene.frame_set(4)
        stored = entry._adapter[1]
        expected = stored["vertices"] + config.visual_gain * stored["displacements"][3]
        actual = np.empty(expected.size, dtype=np.float32)
        obj.data.vertices.foreach_get("co", actual)
        np.testing.assert_allclose(actual.reshape(-1, 3), expected, atol=1e-7)
        assert abs(scene["physical_time_s"] - 0.1) < 1e-12
        scene.frame_set(2)
        scene.frame_set(4)
        again = np.empty_like(actual)
        obj.data.vertices.foreach_get("co", again)
        np.testing.assert_array_equal(actual, again)
        _, slow_bundle, slow_parameters = export_run(
            config, Path(folder) / "slow", preview=True, inspection_speed=0.25
        )
        entry.build(slow_bundle, slow_parameters)
        assert scene.sequence_editor is None
        assert scene.sync_mode == "FRAME_DROP"
        scene.frame_set(13)
        assert abs(scene["physical_time_s"] - 0.1) < 1e-12
        assert scene["physical_seconds_per_visual_second"] == 0.25
        prototype = importlib.import_module("prototypes.001_resonant_surface.build")
        config = prototype.load_config(preview=True)
        config.osc["enabled"] = False
        prototype.build(config)
        assert scene.sequence_editor is None
        assert not any(f.__name__ == entry.HANDLER_NAME for f in bpy.app.handlers.frame_change_pre)
        entry.build(bundle, parameters)
        assert len(bpy.app.handlers.frame_change_pre) == 1
    print("Dry Blender validation passed: coordinates, audio clock, scrubbing, reload and cleanup.")


if __name__ == "__main__":
    main()
