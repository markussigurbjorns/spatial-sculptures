"""Publish wet observable-convergence figures from saved validation evidence."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def plot(report_path, output):
    import matplotlib.pyplot as plt

    report = json.loads(report_path.read_text())
    count = str(report["wet_parameters"]["playback_count"])
    rows = report["intervals"]
    centers = [sum(row["range_hz"]) / 2 for row in rows]
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.3), constrained_layout=True)
    for name, label in (
        ("horizontal_8_to_10", "Fluid degree 8 → 10"),
        ("horizontal_10_to_12", "Fluid degree 10 → 12"),
        ("vertical_2_to_3", "Vertical degree 2 → 3"),
    ):
        errors = [
            100 * row["comparisons"][name]["errors"]["hydrophone_pressure"]["maximum_relative_L2"]
            for row in rows
        ]
        axes[0].plot(centers, errors, "o-", label=label)
    for name, label in (
        ("contact_velocity", "Metal contact velocity"),
        ("hydrophone_pressure", "Hydrophone pressure"),
        ("surface_elevation", "Kinematic surface elevation"),
    ):
        errors = [
            100 * row["retained_counts"][count]["errors"][name]["maximum_relative_L2"]
            for row in rows
        ]
        axes[1].plot(centers, errors, "o-", label=label)
    for ax, limit, title in zip(
        axes,
        [2.0, 5.0],
        ["Fluid pressure refinement", f"{count}-mode playback vs 512-mode reference"],
        strict=True,
    ):
        ax.axhline(limit, color="black", linestyle="--", linewidth=1, label=f"Criterion {limit:g}%")
        ax.axvspan(0, report["tested_stop_hz"], color="#dbeedd", alpha=0.6)
        ax.set(
            xlabel="Frequency-interval midpoint (Hz)",
            ylabel="Worst of six paths: complex L2 difference (%)",
            yscale="log",
            title=title,
            xlim=(0, 200),
        )
        ax.set_xticks(centers, [f"{a}–{b}" for a, b in [r["range_hz"] for r in rows]])
        ax.set_xlabel("Frequency interval (Hz)")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, loc="upper left")
    fig.suptitle(
        f"Pressure-release basin: numerical agreement through {report['tested_stop_hz']:g} Hz; "
        "green = selected band"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".pdf"):
        fig.savefig(output.with_suffix(suffix), dpi=180)
    plt.close(fig)
    provenance = {
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "plot_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "artifact_sha256": {
            s: hashlib.sha256(output.with_suffix(s).read_bytes()).hexdigest()
            for s in (".png", ".pdf")
        },
        "scope": report["scope"],
    }
    output.with_suffix(".json").write_text(json.dumps(provenance, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", type=Path, default=ROOT / "docs/research/wet_basin/validation.json"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "docs/research/wet_basin/convergence")
    args = parser.parse_args()
    try:
        plot(args.report, args.output)
    except (OSError, ImportError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
