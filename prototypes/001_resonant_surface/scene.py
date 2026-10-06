"""Studio presentation, deliberately separate from sculpture geometry and field math."""

from pathlib import Path
from typing import Any

from spatial_sculptures.blender.camera import create_camera
from spatial_sculptures.blender.lighting import area_light
from spatial_sculptures.blender.materials import (
    black_sensor,
    brushed_steel,
    concrete,
    dark_metal,
    water,
)

from .config import PrototypeConfig


def configure_scene(config: PrototypeConfig) -> None:
    """Set timing, renderer and output defaults; creating no sculpture objects."""
    import bpy

    scene = bpy.context.scene
    animation, rendering = config.animation, config.rendering
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = animation["fps"]
    scene.render.fps_base = 1.0
    scene.frame_start = animation["frame_start"]
    scene.frame_end = scene.frame_start + round(animation["fps"] * animation["seconds"]) - 1
    scene.render.engine = rendering["engine"]
    scene.render.resolution_x = rendering["resolution_x"]
    scene.render.resolution_y = rendering["resolution_y"]
    scene.render.resolution_percentage = rendering["resolution_percentage"]
    scene.render.film_transparent = rendering["transparent"]
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(Path(__file__).resolve().parent / "renders" / "frame_")
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = rendering["samples"]
    elif hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = rendering["samples"]
    elif hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_samples"):
        scene.eevee.taa_samples = rendering["samples"]


def create_materials() -> dict[str, Any]:
    """Choose this prototype's palette using reusable material factories."""
    return {
        "steel": brushed_steel(),
        "dark": dark_metal(),
        "sensor": black_sensor(),
        "floor": concrete(),
        "water": water(),
    }


def setup_scene(materials: dict[str, Any], config: PrototypeConfig) -> None:
    """Create the floor, camera, lights and background around the sculpture."""
    import bpy

    scene = bpy.context.scene
    bpy.ops.mesh.primitive_plane_add(size=200.0, location=(0.0, 0.0, -0.003))
    floor = bpy.context.object
    floor.name = "Studio floor"
    floor.data.materials.append(materials["floor"])
    rendering = config.rendering
    create_camera(
        "Sculpture camera",
        rendering["camera_position"],
        rendering["camera_target"],
        lens=rendering["camera_lens"],
    )
    target = (0.0, 0.0, config.water["z"])
    area_light("Key softbox", (0.4, -1.6, 3.3), target, energy=850, size=2.5)
    area_light("Cool rim", (-1.7, 1.2, 2.2), target, energy=650, size=1.8, color=(0.70, 0.83, 1.0))
    area_light("Warm fill", (2.0, 0.5, 1.6), target, energy=450, size=1.6, color=(1.0, 0.83, 0.65))
    area_light("Underside fill", (0.4, -1.8, 0.35), (0.0, 0.0, 0.70), energy=80, size=1.0)
    world = scene.world or bpy.data.worlds.new("Studio world")
    scene.world = world
    world.use_nodes = True
    background = next(node for node in world.node_tree.nodes if node.type == "BACKGROUND")
    background.inputs["Color"].default_value = (0.07, 0.09, 0.12, 1.0)
    background.inputs["Strength"].default_value = rendering["world_strength"]
    # Start in camera view when launched interactively; users can orbit freely.
    if bpy.context.screen is not None:
        for area in bpy.context.screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
                area.spaces.active.shading.type = "MATERIAL"
