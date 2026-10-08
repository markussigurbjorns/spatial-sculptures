"""Curate water-loading study data and make a scientific comparison figure."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def curate(result: Path, output: Path):
    """Check source/data identities before retaining modes and plotting a completed study."""
    import matplotlib
    import numpy as np

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    report = json.loads((result / "report.json").read_text())
    if report.get("status") not in ("passed", "failed"):
        raise ValueError("A completed numerical study is required")
    for name, expected in report["source_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"Stale water-loading source: {name}")
    if digest(ROOT / report["baseline_path"]) != report["baseline_sha256"]:
        raise ValueError("Baseline configuration changed")
    for name, expected in report["modal_artifacts_sha256"].items():
        if digest(result / name) != expected:
            raise ValueError(f"Modal archive changed: {name}")
    if result.resolve() == output.resolve():
        raise ValueError("Choose a separate curation directory")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(result / "report.json", output / "report.json")
    shutil.copyfile(result / "summary.md", output / "summary.md")
    for name in report["modal_artifacts_sha256"]:
        shutil.copyfile(result / name, output / name)

    figure, axes = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)
    surface = report["baseline_configuration"]["surface"]
    x = np.linspace(-surface["radius_x"], surface["radius_x"], 501)
    xx = x / surface["radius_x"]
    z = surface["center_z"] + surface["rise"] * xx**2 + surface["asymmetry"] * xx * (1 - xx**2)
    axes[0].plot(x, z, color="#444444", label="Metal mid-surface")
    for i, row in enumerate(report["depth_cases"]):
        depth = row["water"]["depth_m"]
        if depth == 0:
            continue
        color = plt.get_cmap("viridis")((i + 1) / (len(report["depth_cases"]) + 1))
        level = row["surface_level_m"]
        label = f"{1000 * depth:g} mm"
        wet = z <= level
        axes[0].plot(x[wet], np.full(np.count_nonzero(wet), level), color=color, label=label)
        axes[0].fill_between(x, z, level, where=wet, color=color, alpha=0.12)
        ratios = row["ordered_frequency_ratios_to_dry"][:16]
        axes[1].plot(np.arange(1, len(ratios) + 1), ratios, ".-", color=color, label=label)
    axes[0].set(title="Resting fill, section y=0", xlabel="x (m)", ylabel="z (m)")
    axes[0].legend(fontsize=8)
    axes[1].axhline(1, color="#888888", linestyle="--", label="Dry")
    axes[1].set(
        title="Provisional loading effect",
        xlabel="Sorted frequency rank",
        ylabel="Frequency / dry frequency",
    )
    axes[1].legend(fontsize=8)
    reference = report["finite_depth_analytical_reference"]
    depths = [1000 * row["depth_m"] for row in reference]
    for i, mode in enumerate(reference[0]["modes"]):
        errors = [
            100 * row["modes"][i]["relative_frequency_approximation_error"] for row in reference
        ]
        m, n = mode["indices"]
        axes[2].plot(depths, errors, ".-", label=f"({m},{n})")
    axes[2].set(
        title="Flat-cell approximation error",
        xlabel="Water depth (mm)",
        ylabel="Frequency difference from finite-depth solution (%)",
    )
    axes[2].legend(fontsize=8, title="Plate mode", ncols=2)
    for axis in axes:
        axis.grid(alpha=0.2)
    figure.suptitle("Shallow-column loading: integration checks do not certify basin fluid physics")
    images = {}
    for suffix in ("png", "pdf"):
        path = output / f"water_loading.{suffix}"
        figure.savefig(path, dpi=180)
        images[path.name] = digest(path)
    plt.close(figure)
    manifest = {
        "schema": 1,
        "report_sha256": digest(output / "report.json"),
        "summary_sha256": digest(output / "summary.md"),
        "modal_artifacts_sha256": report["modal_artifacts_sha256"],
        "figures_sha256": images,
        "plot_source_sha256": digest(Path(__file__)),
        "matplotlib_version": matplotlib.__version__,
        "presentation": "Sorted frequency ranks; no mode tracking across depths or fitted gains.",
    }
    (output / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--result", type=Path, default=ROOT / "data/fem/001_resonant_surface/water_loading"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "docs/research/water_loading")
    args = parser.parse_args()
    try:
        path = curate(args.result, args.output)
    except (ValueError, OSError, ImportError, KeyError) as error:
        parser.error(str(error))
    print(f"Curated water-loading results and figure: {path}")


if __name__ == "__main__":
    main()
