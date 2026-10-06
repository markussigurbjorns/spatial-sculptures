"""Launch a prototype in Blender from any working directory, without installing the package."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def prototype_script(prototype: str) -> Path:
    """Resolve a direct child of prototypes, rejecting missing names and path traversal."""
    directory = (REPOSITORY_ROOT / "prototypes" / prototype).resolve()
    if directory.parent != (REPOSITORY_ROOT / "prototypes").resolve():
        raise ValueError("Prototype must be the name of one directory inside prototypes/")
    script = directory / "build.py"
    if not script.is_file():
        raise ValueError(f"Prototype has no build.py: {prototype}")
    return script


def build_command(
    prototype: str,
    *,
    background: bool = False,
    preview: bool = False,
    experiment: str | None = None,
    frame: int | None = None,
    render_output: Path | None = None,
    save_blend: Path | None = None,
) -> list[str]:
    """Build an argument list, keeping Blender options before script execution."""
    script = prototype_script(prototype)
    command = [os.environ.get("BLENDER_BIN", "blender"), "--factory-startup"]
    if background:
        command.append("--background")
    command.extend(["--python-exit-code", "1", "--python", str(script)])
    arguments: list[str] = []
    if preview:
        arguments.append("--preview")
    if experiment:
        arguments.extend(["--experiment", experiment])
    if frame is not None:
        arguments.extend(["--frame", str(frame)])
    if render_output is not None:
        arguments.extend(["--render-output", str(render_output.expanduser().resolve())])
    if save_blend is not None:
        arguments.extend(["--save-blend", str(save_blend.expanduser().resolve())])
    if arguments:
        command.extend(["--", *arguments])
    return command


def run(prototype: str, **options: object) -> int:
    """Run Blender, returning its exit status; missing executables return 127."""
    command = build_command(prototype, **options)
    try:
        return subprocess.run(command, check=False).returncode
    except FileNotFoundError:
        print(f"Blender executable not found: {command[0]}. Set BLENDER_BIN.", file=sys.stderr)
        return 127


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prototype", help="Directory name, for example 001_resonant_surface")
    parser.add_argument("--background", action="store_true", help="Build without opening a window")
    parser.add_argument("--preview", action="store_true", help="Use a lightweight solid preview")
    parser.add_argument("--experiment", help="Experiment filename stem")
    parser.add_argument("--frame", type=int, help="Frame to select after building")
    parser.add_argument("--save-blend", type=Path, help="Explicit scene output path")
    args = parser.parse_args()
    try:
        return run(
            args.prototype,
            background=args.background,
            preview=args.preview,
            experiment=args.experiment,
            frame=args.frame,
            save_blend=args.save_blend,
        )
    except ValueError as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
