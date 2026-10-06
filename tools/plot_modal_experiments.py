"""Export scientific PNG/PDF figures from a saved dry-plate experiment comparison."""

import argparse
import csv
import json
from pathlib import Path

try:
    from .run_modal_study import ROOT
except ImportError:
    from run_modal_study import ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        type=Path,
        default=ROOT / "studies/plates/001_modal_reference/results/experiments",
    )
    parser.add_argument("--output", type=Path, help="Default: results directory")
    args = parser.parse_args()
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        parser.error("Plotting requires optional dependencies: pip install -e '.[paper]'")
    reports = json.loads((args.results / "comparison.json").read_text(encoding="utf-8"))["reports"]
    names = [report["experiment"] for report in reports]
    for report in reports:
        path = args.results / report["experiment"] / "report.json"
        current = json.loads(path.read_text(encoding="utf-8"))
        if current != report:
            parser.error(
                f"Case {report['experiment']} changed after the comparison was saved; "
                "rerun the experiment suite before plotting"
            )
    labels = [name.split("_", 1)[1].replace("_", " ") for name in names]
    indices = range(len(reports))
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    axes[0, 0].barh(
        list(indices), [r["fundamental_frequency_hz"] for r in reports], color="#286177"
    )
    axes[0, 0].set(yticks=list(indices), yticklabels=labels, xlabel="Fundamental frequency (Hz)")
    axes[0, 0].invert_yaxis()
    for i in range(max(len(r["pickup_statistics"]) for r in reports)):
        values = [
            r["pickup_statistics"][i]["sampled_peak_velocity_m_per_s"] * 1000
            if i < len(r["pickup_statistics"])
            else float("nan")
            for r in reports
        ]
        axes[0, 1].plot(values, list(indices), "o", label=f"Pickup {i + 1}")
    axes[0, 1].set(
        yticks=list(indices), yticklabels=labels, xlabel="Sampled peak contact velocity (mm/s)"
    )
    axes[0, 1].invert_yaxis()
    axes[0, 1].legend()
    for metric, label in (
        ("initial_retained_energy_j", "Initial"),
        ("final_retained_energy_j", "Final"),
    ):
        axes[1, 0].plot([r[metric] for r in reports], list(indices), "o", label=label)
    axes[1, 0].set(
        yticks=list(indices), yticklabels=labels, xlabel="Retained mechanical energy (J)"
    )
    if all(
        r[metric] > 0
        for r in reports
        for metric in ("initial_retained_energy_j", "final_retained_energy_j")
    ):
        axes[1, 0].set_xscale("log")
    else:
        axes[1, 0].set_xscale("symlog", linthresh=1e-8)
        axes[1, 0].set_xlim(left=0)
    axes[1, 0].invert_yaxis()
    axes[1, 0].legend()
    # These cases isolate placement/patch changes; read their exported coefficients.
    for name in ("001_baseline", "004_center_excitation", "005_wide_contact"):
        if name not in names:
            continue
        with (args.results / name / "coupling.csv").open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows or "impulse_1_projection" not in rows[0]:
            continue
        selected = rows[:12]
        axes[1, 1].plot(
            [abs(float(row["impulse_1_projection"])) for row in selected],
            "o-",
            label=name.split("_", 1)[1].replace("_", " "),
        )
        axes[1, 1].set_xticks(
            range(len(selected)), [f"({row['m']},{row['n']})" for row in selected], rotation=45
        )
    axes[1, 1].set(xlabel="Retained mode index", ylabel="Absolute impulse patch projection")
    if axes[1, 1].lines:
        axes[1, 1].legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=3, fontsize=8)
    fig.suptitle("Dry reference parameter experiments — computed, provisional, not measurements")
    output = args.output or args.results
    output.mkdir(parents=True, exist_ok=True)
    for extension in ("png", "pdf"):
        fig.savefig(output / f"parameter_comparison.{extension}", dpi=180)
    plt.close(fig)
    print(f"Comparison figures: {output.resolve()}")


if __name__ == "__main__":
    main()
