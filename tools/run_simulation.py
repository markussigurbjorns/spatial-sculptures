"""Run a sculpture simulation and optional OSC with no Blender window."""

from __future__ import annotations

import argparse
import importlib
import json
import signal
import sys
from pathlib import Path
from threading import Event


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    for directory in (root, root / "src"):
        sys.path.insert(0, str(directory))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prototype")
    parser.add_argument("--experiment")
    parser.add_argument("--preview", action="store_true")
    osc = parser.add_mutually_exclusive_group()
    osc.add_argument("--osc", dest="osc", action="store_true", help="Enable OSC for this run")
    osc.add_argument("--no-osc", dest="osc", action="store_false", help="Disable OSC for this run")
    parser.set_defaults(osc=None)
    parser.add_argument("--duration", type=float, help="Run for a limited number of seconds")
    parser.add_argument("--state-file", type=Path, help="Publish the latest state for a display")
    parser.add_argument("--config-file", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.prototype.replace("_", "").isalnum():
        parser.error("Prototype must be a directory name")
    if not (root / "prototypes" / args.prototype / "runtime.py").is_file():
        parser.error("Prototype has no independent runtime.py")
    config_module = importlib.import_module(f"prototypes.{args.prototype}.config")
    if args.config_file:
        config = config_module.PrototypeConfig(
            **json.loads(args.config_file.read_text(encoding="utf-8"))
        )
    else:
        config = config_module.load_config(args.experiment, preview=args.preview)
    if args.osc is not None:
        config.osc["enabled"] = args.osc
    config.validate()
    runtime = importlib.import_module(f"prototypes.{args.prototype}.runtime")
    stop = Event()
    signal.signal(signal.SIGTERM, lambda _signal, _frame: stop.set())
    try:
        runtime.run(config, state_file=args.state_file, duration=args.duration, stop=stop)
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
