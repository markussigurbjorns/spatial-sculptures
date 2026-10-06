"""Reproduce the dry-plate study: SI data, derived modes, and offline contact-pickup audio."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_study(
    *, driven: bool = False, experiment: str | None = None, config_path: Path | None = None
):
    for directory in (ROOT, ROOT / "src"):
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    config = importlib.import_module("studies.plates.001_modal_reference.config")
    simulation = importlib.import_module("studies.plates.001_modal_reference.simulation")
    return (
        config.load_config(driven=driven, experiment=experiment, config_path=config_path),
        simulation.PlateSimulation,
    )


def validate_audio_sampling(config, simulation) -> None:
    """Check Nyquist and nonempty output before generating offline audio."""
    if max(mode.frequency_hz for mode in simulation.modes) >= config.sample_rate / 2:
        raise ValueError("Audio sample rate must exceed twice every retained modal frequency")
    if any(drive.frequency_hz >= config.sample_rate / 2 for drive in config.drives):
        raise ValueError("Audio sample rate must exceed twice every drive frequency")
    if round(config.duration * config.sample_rate) < 1:
        raise ValueError("Audio duration must contain at least one sample")


def run_study(
    config, simulation_type, output: Path, *, audio: bool = True, experiment: str | None = None
) -> dict:
    """Write data and provenance from one parameter set, without Blender or SuperCollider."""
    from spatial_sculptures.audio.synthesis import write_pickup_wav

    simulation = simulation_type(config)
    if not math.isfinite(config.duration) or config.duration <= 0:
        raise ValueError("Duration must be finite and positive")
    if audio:
        validate_audio_sampling(config, simulation)
    output.mkdir(parents=True, exist_ok=True)
    (output / "configuration.json").write_text(
        json.dumps(asdict(config), indent=2, allow_nan=False), encoding="utf-8"
    )
    with (output / "modes.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["m", "n", "frequency_hz", "modal_mass_kg", "damping_ratio"])
        for (m, n), mode in zip(simulation.indices, simulation.modes, strict=True):
            writer.writerow([m, n, mode.frequency_hz, mode.mass_kg, mode.damping_ratio])
    observation_frequency = max(
        [m.frequency_hz for m in simulation.modes] + [drive.frequency_hz for drive in config.drives]
    )
    count = max(2, math.ceil(config.duration * 16 * observation_frequency))
    times = [index * config.duration / count for index in range(count + 1)]
    positions, velocities = simulation.trace(times)
    weights = [simulation.weights(x, y) for x, y in config.pickups]
    pickups = simulation.pickup_velocities(velocities)
    with (output / "coupling.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        events = (*config.impulses, *config.drives)
        writer.writerow(
            ["m", "n"]
            + [f"impulse_{i}_projection" for i in range(1, len(config.impulses) + 1)]
            + [f"drive_{i}_projection" for i in range(1, len(config.drives) + 1)]
            + [f"pickup_{i}_mode_shape" for i in range(1, len(config.pickups) + 1)]
        )
        for index, (m, n) in enumerate(simulation.indices):
            projections = [
                config.plate.patch_projection(m, n, event.x, event.y, event.patch_width)
                * event.mounting.force_direction[2]
                for event in events
            ]
            writer.writerow([m, n, *projections, *(row[index] for row in weights)])
    energies = [
        sum(
            0.5 * mode.mass_kg * (velocities[i][j] ** 2 + mode.omega**2 * positions[i][j] ** 2)
            for i, mode in enumerate(simulation.modes)
        )
        for j in range(len(times))
    ]
    with (output / "response.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["time_s", "retained_energy_j"]
            + [f"contact_pickup_{i}_velocity_m_per_s" for i in range(1, len(weights) + 1)]
        )
        writer.writerows(
            (t, float(e), *(float(channel[j]) for channel in pickups))
            for j, (t, e) in enumerate(zip(times, energies, strict=True))
        )
    initial, final = simulation.step(0.0), simulation.step(config.duration)
    report = {
        "model": "linear simply supported Kirchhoff-Love reference plate; dry",
        "parameters": asdict(config),
        "model_capabilities": importlib.import_module(
            simulation_type.__module__
        ).MODEL_CAPABILITIES,
        "experiment": experiment,
        "plate_mass_kg": config.plate.density
        * config.plate.thickness
        * config.plate.length_x
        * config.plate.length_y,
        "mode_count": len(simulation.modes),
        "fundamental_frequency_hz": min(mode.frequency_hz for mode in simulation.modes),
        "highest_retained_frequency_hz": max(mode.frequency_hz for mode in simulation.modes),
        "initial_retained_energy_j": initial.energy_joules,
        "final_retained_energy_j": final.energy_joules,
        "maximum_energy_increase_j": float(
            max(b - a for a, b in zip(energies[:-1], energies[1:], strict=True))
        ),
        "pickup_units": "m/s; virtual contact velocity, not hydrophone pressure",
        "response_sampling_hz": count / config.duration,
        "pickup_statistics": [
            {
                "index": i,
                "position_m": config.pickups[i - 1],
                "sampled_peak_velocity_m_per_s": max(abs(float(v)) for v in channel),
                "sampled_rms_velocity_m_per_s": math.sqrt(
                    sum(float(v) ** 2 for v in channel) / len(channel)
                ),
            }
            for i, channel in enumerate(pickups, 1)
        ],
        "measurements": "none; material properties and damping are provisional",
        "provenance": {
            "python_version": sys.version.split()[0],
            "sampling_backend": "numpy" if hasattr(velocities, "shape") else "stdlib",
            "config_sha256": hashlib.sha256(
                json.dumps(asdict(config), sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "source_sha256": {
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in (
                    "src/spatial_sculptures/simulation/modal.py",
                    "src/spatial_sculptures/simulation/mode_bank.py",
                    "src/spatial_sculptures/simulation/plates.py",
                    "src/spatial_sculptures/audio/synthesis.py",
                    "studies/plates/001_modal_reference/config.py",
                    "studies/plates/001_modal_reference/simulation.py",
                    "tools/run_modal_study.py",
                )
                + (
                    (
                        f"studies/plates/001_modal_reference/experiments/{experiment}.py",
                        "studies/plates/001_modal_reference/experiments/__init__.py",
                    )
                    if experiment is not None
                    else ()
                )
            },
        },
    }
    if audio:
        audio_times = [
            i / config.sample_rate for i in range(round(config.duration * config.sample_rate))
        ]
        _, audio_velocities = simulation.trace(audio_times)
        channels = simulation.pickup_velocities(audio_velocities)
        report["audio_gain_per_m_per_s"] = write_pickup_wav(
            output / "contact_pickups.wav", channels, config.sample_rate
        )
        report["audio_note"] = "Channel 1/2 are pickups, not binaural or loudspeaker spatialization"
    else:
        (output / "contact_pickups.wav").unlink(missing_ok=True)
    (output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, help="Default: study results, or results/<experiment>"
    )
    parser.add_argument(
        "--driven", action="store_true", help="Add the three 1 N-scale harmonic forces"
    )
    parser.add_argument("--duration", type=float)
    parser.add_argument("--modes", type=int, help="Modes per axis; total is its square")
    parser.add_argument("--no-audio", action="store_true")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--experiment", help="Numbered experiment name; see --list-experiments")
    source.add_argument("--config", type=Path, help="Saved configuration.json or report.json")
    parser.add_argument("--list-experiments", action="store_true")
    args = parser.parse_args()
    if args.list_experiments:
        load_study()
        experiments = importlib.import_module("studies.plates.001_modal_reference.experiments")
        print("\n".join(experiments.experiment_names()))
        return 0
    try:
        config, simulation_type = load_study(
            driven=args.driven, experiment=args.experiment, config_path=args.config
        )
        if args.duration is not None:
            config.duration = args.duration
        if args.modes is not None:
            config.modes_per_axis = args.modes
        output = args.output or ROOT / "studies/plates/001_modal_reference/results"
        if args.output is None and args.experiment:
            output = output / args.experiment
        report = run_study(
            config,
            simulation_type,
            output.resolve(),
            audio=not args.no_audio,
            experiment=args.experiment,
        )
    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))
    print(f"{report['mode_count']} modes, fundamental {report['fundamental_frequency_hz']:.3f} Hz.")
    print(f"Dry reference results: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
