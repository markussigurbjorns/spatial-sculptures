"""Plot recorded curved-shell correspondence and unnormalized contact convergence."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", type=Path, default=ROOT / "docs/research/dry_basin/convergence.json"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "docs/research/dry_basin/figures")
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    for name, digest in report["source_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            parser.error(f"Stale source {name}; regenerate convergence data first")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    args.output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

    def save(fig, name):
        for extension in ("png", "pdf"):
            fig.savefig(args.output / f"{name}.{extension}", dpi=180)
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for row in report["meshes"]:
        indices, errors, shape_errors = [], [], []
        for group in row["independent_mode_comparison"]["groups"]:
            for index in group["reference_indices"]:
                if index >= 16:
                    continue
                indices.append(index + 1)
                errors.append(100 * group["maximum_relative_frequency_difference"])
                shape_errors.append(100 * (1 - group["minimum_subspace_MAC"]))
        axes[0].plot(
            indices,
            errors,
            "o-",
            ms=3,
            label=f"{row['elements_per_axis']} × {row['elements_per_axis']}",
        )
        axes[1].semilogy(indices, np.maximum(shape_errors, 1e-8), "o-", ms=3)
    axes[0].axhline(100 * report["policy"]["frequency_relative"], color="grey", linestyle="--")
    axes[0].set(
        title="Frequency versus independent Ritz reference", ylabel="Maximum group difference (%)"
    )
    axes[1].set(title="Vector-mode/subspace agreement", ylabel="1 − minimum subspace MAC (%)")
    for ax in axes:
        ax.set_xlabel("Reference mode index")
        ax.grid(alpha=0.2)
    axes[0].legend()
    save(fig, "independent_mode_comparison")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for row in report["meshes"]:
        bands = row["retained_counts"][-1]["bands"]
        axes[0].semilogx(
            [b["band_hz"] for b in bands],
            [100 * b["independent_response"]["maximum_relative_L2"] for b in bands],
            "o-",
            ms=3,
            label=f"{row['elements_per_axis']} × {row['elements_per_axis']}",
        )
    axes[0].axhline(
        100 * report["policy"]["independent_transfer_relative_L2"],
        color="grey",
        linestyle="--",
        label="10% tolerance",
    )
    axes[0].set(
        title="All retained modes: six contact/force paths",
        ylabel="Maximum complex relative L2 (%)",
    )
    for key, label in (
        ("reference_refinement", "Ritz: last two degrees"),
        ("reference_truncation", "Ritz: last two mode counts"),
        ("finest_mesh_refinement", "Spline: last two meshes"),
    ):
        axes[1].semilogx(
            [b["band_hz"] for b in bands],
            [100 * b[key]["maximum_relative_L2"] for b in bands],
            "o-",
            ms=3,
            label=label,
        )
    axes[1].axhline(5, color="grey", linestyle="--", label="5% tolerance")
    axes[1].set(
        title="Reference and spatial refinement limits", ylabel="Maximum complex relative L2 (%)"
    )
    for ax in axes:
        ax.set_xlabel("Sampled cumulative upper frequency (Hz)")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.2)
    save(fig, "contact_transfer_convergence")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for row in report["meshes"]:
        cases = row["retained_counts"]
        for ax, key in zip(axes, ("vs_independent_reference", "vs_full_modal_bank"), strict=True):
            ax.plot(
                [c["count"] for c in cases],
                [100 * c["unfiltered_impulse"][key]["maximum_relative_L2"] for c in cases],
                "o-",
                ms=3,
                label=f"{row['elements_per_axis']} × {row['elements_per_axis']}",
            )
    axes[0].set_title("Unfiltered impulses versus independent reference")
    axes[1].set_title("Truncation versus full bank on the same mesh")
    for ax in axes:
        ax.set(xlabel="Retained mode count", ylabel="Worst contact/path relative signal L2 (%)")
        ax.legend()
        ax.grid(alpha=0.2)
    save(fig, "impulse_convergence")

    if all("filtered_impulse" in c for row in report["meshes"] for c in row["retained_counts"]):
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
        for row in report["meshes"]:
            cases = row["retained_counts"]
            for ax, key in zip(
                axes, ("vs_independent_reference", "vs_full_modal_bank"), strict=True
            ):
                ax.plot(
                    [c["count"] for c in cases],
                    [100 * c["filtered_impulse"][key]["maximum_relative_L2"] for c in cases],
                    "o-",
                    ms=3,
                    label=f"{row['elements_per_axis']} × {row['elements_per_axis']}",
                )
        axes[0].axhline(10, color="grey", linestyle="--")
        axes[1].axhline(5, color="grey", linestyle="--")
        filtering = report["sampling"]["filtered_impulse"]
        axes[0].set_title(
            "Filtered impulses versus reference\n"
            f"pass {filtering['passband_hz']:g} / stop {filtering['stopband_hz']:g} Hz"
        )
        axes[1].set_title("Filtered truncation versus full bank")
        for ax in axes:
            ax.set(xlabel="Retained mode count", ylabel="Worst contact/path relative signal L2 (%)")
            ax.legend()
            ax.grid(alpha=0.2)
        save(fig, "filtered_impulse_convergence")
    (args.output / "convergence_provenance.json").write_text(
        json.dumps(
            {
                "report_sha256": hashlib.sha256(args.report.read_bytes()).hexdigest(),
                "plot_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            indent=2,
        )
    )
    print(f"Convergence figures: {args.output.resolve()}")


if __name__ == "__main__":
    main()
