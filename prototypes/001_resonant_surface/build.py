"""Blender entry point: compose configuration, geometry, simulation and presentation.

Works with `blender --python /absolute/path/to/build.py` from any working directory.
Prototype modules use relative imports so their names never shadow other prototypes.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import PrototypeConfig
    from .geometry import Sculpture


def _bootstrap_imports() -> None:
    root = Path(__file__).resolve().parents[2]
    for directory in (root, root / "src"):
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))


# Blender executes files as scripts; establish the namespace for relative imports.
if not __package__:
    _bootstrap_imports()
    __package__ = f"prototypes.{Path(__file__).resolve().parent.name}"


def load_config(experiment: str | None = None) -> PrototypeConfig:
    """Start from independent defaults and optionally apply one local experiment."""
    from .config import default_config

    config = default_config()
    if experiment:
        name = Path(experiment).stem
        directory = Path(__file__).resolve().parent / "experiments"
        if not name.replace("_", "").isalnum() or not (directory / f"{name}.py").is_file():
            raise ValueError(f"Unknown experiment: {experiment}")
        module = importlib.import_module(f"{__package__}.experiments.{name}")
        config = module.configure(config)
    config.validate()
    return config


def build(config: PrototypeConfig | None = None) -> Sculpture:
    """Rebuild the complete scene, returning its sculpture for interactive exploration."""
    from spatial_sculptures.blender.utils import clear_scene
    from spatial_sculptures.transport.osc import OSCTransport

    from .geometry import create_sculpture
    from .scene import configure_scene, create_materials, setup_scene
    from .simulation import ResonantField
    from .visualization import FRAME_HANDLER_NAME, setup_visualization

    config = load_config() if config is None else config
    config.validate()
    clear_scene(handler_names=(FRAME_HANDLER_NAME,))
    configure_scene(config)
    materials = create_materials()
    sculpture = create_sculpture(materials=materials, config=config)
    field = ResonantField(config)
    transport = OSCTransport(**config.osc)
    setup_visualization(sculpture=sculpture, field=field, transport=transport)
    setup_scene(materials=materials, config=config)
    print_summary(sculpture, config)
    return sculpture


def print_summary(sculpture: Sculpture, config: PrototypeConfig) -> None:
    import bpy

    scene = bpy.context.scene
    print(
        f"Built 001_resonant_surface: {len(sculpture.water_base):,} water vertices, "
        f"{len(sculpture.exciters)} exciters, {len(sculpture.hydrophones)} hydrophones; "
        f"frames {scene.frame_start}-{scene.frame_end} at {config.animation['fps']} FPS."
    )
    print("Artistic wave approximation. No CFD, FEM, calibrated acoustics or active feedback.")


def main() -> None:
    """Handle the small set of script arguments after Blender's `--` separator."""
    import bpy

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", help="Experiment filename stem")
    parser.add_argument("--frame", type=int, help="Frame to display/render after building")
    parser.add_argument("--render-output", type=Path, help="Render one PNG to this path")
    parser.add_argument(
        "--save-blend", type=Path, help="Save this scene to an explicit .blend path"
    )
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = parser.parse_args(arguments)
    build(load_config(args.experiment))
    if args.frame is not None:
        bpy.context.scene.frame_set(args.frame)
    if args.save_blend is not None:
        output = args.save_blend.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(output))
    if args.render_output is not None:
        output = args.render_output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        bpy.context.scene.render.filepath = str(output)
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
