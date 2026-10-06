"""Launch a prototype in Blender from any working directory, without installing the package."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
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
    osc: bool | None = None,
    state_file: Path | None = None,
    config_file: Path | None = None,
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
    if osc is not None:
        arguments.append("--osc" if osc else "--no-osc")
    if state_file is not None:
        arguments.extend(["--state-file", str(state_file.resolve())])
    if config_file is not None:
        arguments.extend(["--config-file", str(config_file.resolve())])
    if frame is not None:
        arguments.extend(["--frame", str(frame)])
    if render_output is not None:
        arguments.extend(["--render-output", str(render_output.expanduser().resolve())])
    if save_blend is not None:
        arguments.extend(["--save-blend", str(save_blend.expanduser().resolve())])
    if arguments:
        command.extend(["--", *arguments])
    return command


def _stop_process(process: subprocess.Popen | None) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def run_live(prototype: str, **options: object) -> int:
    """Own a simulation worker and Blender viewer; share one config and latest state."""
    prototype_script(prototype)
    if options.get("frame") is not None or options.get("render_output") is not None:
        raise ValueError("Use timeline mode (without --live) for frame selection and rendering")
    if not (REPOSITORY_ROOT / "prototypes" / prototype / "runtime.py").is_file():
        raise ValueError(f"Prototype has no independent runtime.py: {prototype}")
    sys.path.insert(0, str(REPOSITORY_ROOT))
    config_module = importlib.import_module(f"prototypes.{prototype}.config")
    config = config_module.load_config(
        options.get("experiment"), preview=bool(options.get("preview"))
    )
    if options.get("osc") is not None:
        config.osc["enabled"] = options["osc"]
    worker = viewer = None
    with tempfile.TemporaryDirectory(prefix="spatial-sculptures-live-") as directory:
        config_file = Path(directory) / "config.json"
        state_file = Path(directory) / "state.json"
        config_file.write_text(json.dumps(asdict(config), allow_nan=False), encoding="utf-8")
        try:
            worker = subprocess.Popen(
                [
                    sys.executable,
                    str(REPOSITORY_ROOT / "tools" / "run_simulation.py"),
                    prototype,
                    "--config-file",
                    str(config_file),
                    "--state-file",
                    str(state_file),
                ]
            )
            deadline = time.monotonic() + 10.0
            while not state_file.is_file():
                if worker.poll() is not None:
                    print("Simulation worker exited before producing state.", file=sys.stderr)
                    return worker.returncode or 1
                if time.monotonic() >= deadline:
                    print(
                        "Simulation worker did not produce state within 10 seconds.",
                        file=sys.stderr,
                    )
                    return 1
                time.sleep(0.02)
            command = build_command(
                prototype, **options, state_file=state_file, config_file=config_file
            )
            try:
                viewer = subprocess.Popen(command)
            except FileNotFoundError:
                print(
                    f"Blender executable not found: {command[0]}. Set BLENDER_BIN.", file=sys.stderr
                )
                return 127
            while viewer.poll() is None:
                if worker.poll() is not None:
                    print("Simulation worker stopped; closing its live viewer.", file=sys.stderr)
                    return worker.returncode or 1
                time.sleep(0.05)
            return viewer.returncode
        except KeyboardInterrupt:
            return 130
        finally:
            _stop_process(viewer)
            _stop_process(worker)


def run(prototype: str, *, live: bool = False, **options: object) -> int:
    """Run Blender, returning its exit status; missing executables return 127."""
    if live:
        return run_live(prototype, **options)
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
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run Python simulation independently of Blender playback",
    )
    osc = parser.add_mutually_exclusive_group()
    osc.add_argument("--osc", dest="osc", action="store_true", help="Enable OSC for this run")
    osc.add_argument("--no-osc", dest="osc", action="store_false", help="Disable OSC for this run")
    parser.set_defaults(osc=None)
    parser.add_argument("--experiment", help="Experiment filename stem")
    parser.add_argument("--frame", type=int, help="Frame to select after building")
    parser.add_argument("--save-blend", type=Path, help="Explicit scene output path")
    args = parser.parse_args()
    try:
        return run(
            args.prototype,
            background=args.background,
            preview=args.preview,
            live=args.live,
            osc=args.osc,
            experiment=args.experiment,
            frame=args.frame,
            save_blend=args.save_blend,
        )
    except ValueError as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
