"""Build a prototype and render one PNG. This is deliberately not an animation pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

# Both direct script execution and `python -m tools.render` work.
if __package__:
    from .run_blender import run
else:
    from run_blender import run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prototype")
    parser.add_argument(
        "output", type=Path, help="Output PNG path, relative to your current directory"
    )
    parser.add_argument("--frame", type=int, default=1)
    parser.add_argument("--experiment")
    args = parser.parse_args()
    if args.output.suffix.lower() != ".png":
        parser.error("Output must have a .png extension")
    try:
        return run(
            args.prototype,
            background=True,
            experiment=args.experiment,
            frame=args.frame,
            render_output=args.output,
        )
    except ValueError as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
