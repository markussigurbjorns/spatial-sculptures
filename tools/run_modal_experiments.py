"""Run explicit dry-plate experiments and compare physical-unit results without Blender."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
from pathlib import Path

try:
    from .run_modal_study import ROOT, load_study, run_study, validate_audio_sampling
except ImportError:
    from run_modal_study import ROOT, load_study, run_study, validate_audio_sampling


def write_comparison(reports: list[dict], output: Path) -> None:
    """Compare sampled SI observables; individually normalized WAV loudness is not a metric."""
    rows = []
    pickup_count = max(len(report["pickup_statistics"]) for report in reports)
    for report in reports:
        initial = report["initial_retained_energy_j"]
        row = {
            "experiment": report["experiment"],
            "config_sha256": report["provenance"]["config_sha256"],
            "thickness_m": report["parameters"]["plate"]["thickness"],
            "plate_mass_kg": report["plate_mass_kg"],
            "fundamental_frequency_hz": report["fundamental_frequency_hz"],
            "highest_retained_frequency_hz": report["highest_retained_frequency_hz"],
            "mode_count": report["mode_count"],
            "duration_s": report["parameters"]["duration"],
            "damping_ratio": report["parameters"]["damping_ratio"],
            "initial_retained_energy_j": initial,
            "final_retained_energy_j": report["final_retained_energy_j"],
            "final_to_initial_energy_ratio": report["final_retained_energy_j"] / initial
            if initial
            else None,
        }
        for i in range(1, pickup_count + 1):
            stats = next((v for v in report["pickup_statistics"] if v["index"] == i), None)
            for metric in ("sampled_peak_velocity_m_per_s", "sampled_rms_velocity_m_per_s"):
                row[f"pickup_{i}_{metric}"] = stats[metric] if stats else None
        rows.append(row)
    with (output / "comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "scope": "dry analytical reference; not basin/water predictions or measurements",
        "metric_note": "Sampled peak/RMS from each dense response grid, before WAV normalization",
        "audio_note": "Optional WAV files use individual normalization; compare SI data for levels",
        "comparison_source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("tools/run_modal_experiments.py", "tools/plot_modal_experiments.py")
        },
        "reports": reports,
    }
    (output / "comparison.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
    )
    lines = [
        "# Dry reference parameter comparison",
        "",
        "Computed reference-plate results with provisional material/damping, not measurements.",
        "Each case saves its full configuration, source hashes, modal coupling and SI response.",
        "",
        "| Experiment | Thickness (mm) | Mass (kg) | f₁ (Hz) | Initial energy (J) "
        "| Final energy (J) | Largest sampled pickup peak (mm/s) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row, report in zip(rows, reports, strict=True):
        peak = max(v["sampled_peak_velocity_m_per_s"] for v in report["pickup_statistics"])
        lines.append(
            f"| [{row['experiment']}]({row['experiment']}/report.json) "
            f"| {row['thickness_m'] * 1000:g} | {row['plate_mass_kg']:.3f} "
            f"| {row['fundamental_frequency_hz']:.3f} "
            f"| {row['initial_retained_energy_j']:.6g} "
            f"| {row['final_retained_energy_j']:.6g} | {peak * 1000:.4f} |"
        )
    lines.extend(
        [
            "",
            "Peak/RMS values are sampled estimates on the response grids, not exact extrema.",
            "The CSV includes per-pickup peak/RMS values and each observation duration.",
            "Driven cases receive energy; their final/initial ratio is not a decay measurement.",
            "WAVs are individually normalized; perceived loudness cannot compare SI levels.",
            "The retained broadband impulse response is not declared converged.",
            "",
        ]
    )
    (output / "comparison.md").write_text("\n".join(lines), encoding="utf-8")


def run_experiments(
    output: Path,
    *,
    names: tuple[str, ...] | None = None,
    duration: float | None = None,
    modes: int | None = None,
    audio: bool = False,
) -> list[dict]:
    """Prepare every case first, then export independent runs and a comparison table."""
    _, simulation_type = load_study()
    experiments = importlib.import_module("studies.plates.001_modal_reference.experiments")
    selected = experiments.experiment_names() if names is None else names
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("Select at least one experiment, with no duplicate names")
    prepared = []
    for name in selected:
        config, _ = load_study(experiment=name)
        if duration is not None:
            config.duration = duration
        if modes is not None:
            config.modes_per_axis = modes
        simulation = simulation_type(config)  # Reject unsupported requests before writing runs.
        if audio:
            validate_audio_sampling(config, simulation)
        prepared.append((name, config))
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    for name, config in prepared:
        print(f"Running {name}...", flush=True)
        reports.append(
            run_study(config, simulation_type, output / name, audio=audio, experiment=name)
        )
    write_comparison(reports, output)
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "studies/plates/001_modal_reference/results/experiments",
    )
    parser.add_argument("--experiments", nargs="+", help="Default: all numbered experiments")
    parser.add_argument("--duration", type=float, help="Override duration for every case")
    parser.add_argument("--modes", type=int, help="Modes per axis for every case")
    parser.add_argument(
        "--audio", action="store_true", help="Also generate individually normalized WAVs"
    )
    args = parser.parse_args()
    try:
        run_experiments(
            args.output.resolve(),
            names=tuple(args.experiments) if args.experiments is not None else None,
            duration=args.duration,
            modes=args.modes,
            audio=args.audio,
        )
    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))
    print(f"Comparison and reproducible cases: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
