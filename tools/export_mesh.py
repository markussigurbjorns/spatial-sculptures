"""Export one named scene mesh as STL, including evaluated Blender modifiers.

Run inside Blender after building a scene, or use --python after loading a .blend.
This is an inspection/fabrication starting point, not a certified fabrication mesh.
No exporter add-on or external Python dependency is needed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def export_mesh(object_name: str, output: Path) -> None:
    """Write triangulated, world-space geometry as an ASCII STL in metre coordinates."""
    import bpy

    obj = bpy.data.objects.get(object_name)
    if obj is None or obj.type != "MESH":
        raise ValueError(f"No mesh object named {object_name!r}")
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        output = output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="ascii") as stream:
            stream.write("solid spatial_sculptures\n")
            for triangle in mesh.loop_triangles:
                points = [evaluated.matrix_world @ mesh.vertices[i].co for i in triangle.vertices]
                normal = (points[1] - points[0]).cross(points[2] - points[0]).normalized()
                stream.write(f"  facet normal {normal.x:.9g} {normal.y:.9g} {normal.z:.9g}\n")
                stream.write("    outer loop\n")
                for point in points:
                    stream.write(f"      vertex {point.x:.9g} {point.y:.9g} {point.z:.9g}\n")
                stream.write("    endloop\n  endfacet\n")
            stream.write("endsolid spatial_sculptures\n")
    finally:
        evaluated.to_mesh_clear()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("object_name")
    parser.add_argument("output", type=Path)
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = parser.parse_args(arguments)
    export_mesh(args.object_name, args.output)


if __name__ == "__main__":
    main()
