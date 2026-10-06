"""Generate standalone paper figures from the reference model (optional Matplotlib)."""

import argparse
import csv
import importlib
import json
from pathlib import Path

try:
    from .run_modal_study import ROOT, load_study
except ImportError:
    from run_modal_study import ROOT, load_study


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results", type=Path, default=ROOT / "studies/plates/001_modal_reference/results"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/research/modal_reference/figures"
    )
    args = parser.parse_args()
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        parser.error("Figure generation requires optional dependencies: pip install -e '.[paper]'")
    config, simulation_type = load_study()
    config_module = importlib.import_module(
        simulation_type.__module__.rsplit(".", 1)[0] + ".config"
    )
    report = json.loads((args.results / "report.json").read_text(encoding="utf-8"))
    parameters = report["parameters"]
    config = config_module.config_from_dict(parameters)
    args.output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    x = np.linspace(-config.plate.length_x / 2, config.plate.length_x / 2, 81)
    y = np.linspace(-config.plate.length_y / 2, config.plate.length_y / 2, 65)
    xx, yy = np.meshgrid(x, y)
    fig, axes = plt.subplots(2, 3, figsize=(10, 5.6), constrained_layout=True)
    image = None
    for ax, (m, n) in zip(
        axes.ravel(), ((1, 1), (2, 1), (1, 2), (2, 2), (3, 1), (1, 3)), strict=True
    ):
        values = np.sin(m * np.pi * (xx / config.plate.length_x + 0.5)) * np.sin(
            n * np.pi * (yy / config.plate.length_y + 0.5)
        )
        image = ax.pcolormesh(xx, yy, values, cmap="RdBu_r", vmin=-1, vmax=1, shading="auto")
        ax.set_aspect("equal")
        ax.set_title(
            f"({m}, {n}): {config.plate.mode(m, n, config.damping_ratio).frequency_hz:.2f} Hz"
        )
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
    fig.colorbar(
        image, ax=axes.ravel().tolist(), label="Unit-peak mode shape (dimensionless)", shrink=0.7
    )
    fig.suptitle("Dry simply supported reference plate — analytical mode shapes")
    for extension in ("png", "pdf"):
        fig.savefig(args.output / f"mode_shapes.{extension}", dpi=180)
    plt.close(fig)
    with (args.results / "response.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    time = np.array([float(row["time_s"]) for row in rows])
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), constrained_layout=True)
    for i in (1, 2):
        values = np.array([float(row[f"contact_pickup_{i}_velocity_m_per_s"]) for row in rows])
        axes[0].plot(time, values * 1000, label=f"Contact pickup {i}", linewidth=0.55)
    axes[0].set(xlim=(0, 0.35), xlabel="Physical time (s)", ylabel="Velocity (mm/s)")
    axes[0].legend()
    axes[1].semilogy(time, [float(row["retained_energy_j"]) for row in rows], color="#244a5c")
    axes[1].set(xlabel="Physical time (s)", ylabel="Retained mechanical energy (J)")
    fig.suptitle("Finite-patch impulse response; two point pickups and retained energy")
    for extension in ("png", "pdf"):
        fig.savefig(args.output / f"impulse_response.{extension}", dpi=180)
    plt.close(fig)
    # Quantify truncation rather than claiming the 36-mode broadband output has converged.
    table = []
    for count in (2, 4, 6, 8, 12, 16):
        config.modes_per_axis = count
        model = simulation_type(config)
        table.append(
            {
                "modes_per_axis": count,
                "mode_count": count**2,
                "initial_energy_j": model.step(0).energy_joules,
                "highest_frequency_hz": max(m.frequency_hz for m in model.modes),
            }
        )
    (args.output / "truncation.json").write_text(json.dumps(table, indent=2), encoding="utf-8")
    print(f"Figures and truncation data: {args.output.resolve()}")


if __name__ == "__main__":
    main()
