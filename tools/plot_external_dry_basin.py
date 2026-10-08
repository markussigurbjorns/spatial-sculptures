"""Curate completed external-shell evidence and plot unnormalized SI contact responses."""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def curate(result, output, request=None):
    """Preserve modes, raw complex curves and report hashes before making figures."""
    import matplotlib
    import numpy as np

    from tools.check_dry_response import digest, read_csv

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    request = result / "request/request.json" if request is None else request
    report_path = result / "report.json"
    report = json.loads(report_path.read_text())
    source = json.loads((result / "external_source.json").read_text())
    if not report.get("solver_result_available") or report.get("status") not in (
        "passed",
        "failed",
    ):
        raise ValueError("A completed external solve is required; unavailable runtime is not data")
    if digest(request) != report["request_sha256"] or digest(request) != source["request_sha256"]:
        raise ValueError("Comparison request changed")
    for filename, expected in report["solver_source_sha256"].items():
        if digest(ROOT / filename) != expected:
            raise ValueError(f"Stale external source: {filename}")
    if (
        source.get("kind") != "external_solver"
        or digest(result / "external_mobility.csv") != source["data_sha256"]
        or source != report["production_response_comparison"]["source"]
    ):
        raise ValueError("External dataset provenance changed")
    problem = json.loads(request.read_text())
    if digest(request.parent / "model_mobility.csv") != problem["model_mobility_sha256"]:
        raise ValueError("Production dataset changed")
    pickups, exciters = (
        len(problem["parameters"]["pickups"]),
        len(problem["parameters"]["exciters"]),
    )
    frequencies, predicted = read_csv(request.parent / "model_mobility.csv", pickups, exciters)
    external_frequencies, external = read_csv(result / "external_mobility.csv", pickups, exciters)
    if not np.array_equal(frequencies, external_frequencies):
        raise ValueError("Common frequency grid required")
    output.mkdir(parents=True, exist_ok=True)
    for name, expected in report["modal_artifacts_sha256"].items():
        if digest(result / name) != expected:
            raise ValueError(f"Modal archive changed: {name}")
        shutil.copyfile(result / name, output / name)
    shutil.copyfile(report_path, output / "report.json")
    shutil.copyfile(request, output / "request.json")
    curves = output / "contact_responses.npz"
    np.savez_compressed(
        curves,
        frequencies_hz=frequencies,
        production_mobility=predicted,
        external_mobility=external,
    )
    images = {}
    external_count = report["external_meshes"][-1]["settings"]["mode_count"]
    production_count = report["parameters"]["mode_count"]
    for quantity in ("magnitude", "phase"):
        figure, axes = plt.subplots(
            pickups, exciters, figsize=(12, 6), squeeze=False, sharex=True, constrained_layout=True
        )
        for p in range(pickups):
            for e in range(exciters):
                axis = axes[p, e]
                for values, label, color, style in (
                    (external, f"NGSolve ({external_count} modes)", "#252525", "-"),
                    (predicted, f"Production ({production_count} modes)", "#1976aa", "--"),
                ):
                    observation = values[p, e]
                    y = (
                        20 * np.log10(np.maximum(np.abs(observation), 1e-15))
                        if quantity == "magnitude"
                        else np.rad2deg(np.unwrap(np.angle(observation)))
                    )
                    axis.plot(
                        frequencies, y, label=label, color=color, linestyle=style, linewidth=1.1
                    )
                axis.set_title(f"Exciter {e + 1} → pickup {p + 1}")
                axis.grid(alpha=0.2)
                axis.set_xlim(frequencies[0], frequencies[-1])
                if p == pickups - 1:
                    axis.set_xlabel("Frequency (Hz)")
                if e == 0:
                    axis.set_ylabel(
                        "Mobility dB re 1 (m/s)/N"
                        if quantity == "magnitude"
                        else "Unwrapped phase (degrees)"
                    )
        axes[0, 0].legend(fontsize=8)
        figure.suptitle(f"Dry basin: independent contact response ({report['status']})")
        for suffix in ("png", "pdf"):
            path = output / f"contact_{quantity}.{suffix}"
            figure.savefig(path, dpi=180)
            images[path.name] = digest(path)
        plt.close(figure)
    names = ["mesh_1_to_2", "mesh_2_to_3", "rim", "quadrature", "truncation", "frequency_grid"]
    errors = [
        max(v["maximum_relative_L2"] for v in report["external_checks"][n]["intervals"]) * 100
        for n in names
    ]
    tolerances = [report["external_checks"][n]["tolerance"] * 100 for n in names]
    figure, axis = plt.subplots(figsize=(9, 4), constrained_layout=True)
    positions = np.arange(len(names))
    axis.bar(positions, np.maximum(errors, 1e-8), color="#1976aa", label="Worst path / interval")
    axis.plot(
        positions,
        tolerances,
        "_",
        color="#a13e29",
        markersize=24,
        markeredgewidth=2,
        label="Declared limit",
    )
    axis.set_yscale("log")
    lower_count = max(int(n) for n in report["truncation_banks"])
    axis.set_xticks(
        positions,
        [
            "Mesh 1→2",
            "Mesh 2→3",
            "Rim",
            "Quadrature",
            f"{lower_count}→{external_count} modes",
            "Frequency grid",
        ],
    )
    axis.set_ylabel("Complex response difference (%)")
    axis.set_title("Independent NGSolve refinement; numerical differences, not specimen accuracy")
    axis.grid(axis="y", alpha=0.2)
    axis.legend()
    for suffix in ("png", "pdf"):
        path = output / f"refinement.{suffix}"
        figure.savefig(path, dpi=180)
        images[path.name] = digest(path)
    plt.close(figure)
    manifest = {
        "schema": 1,
        "report_sha256": digest(output / "report.json"),
        "request_sha256": digest(request),
        "curves_sha256": digest(curves),
        "modal_artifacts_sha256": report["modal_artifacts_sha256"],
        "original_production_csv_sha256": problem["model_mobility_sha256"],
        "original_external_source": source,
        "plot_source_sha256": digest(Path(__file__)),
        "matplotlib_version": matplotlib.__version__,
        "figures_sha256": images,
        "units": "(m/s)/N",
        "harmonic_convention": "exp(+i*2*pi*f*t)",
        "presentation": "No gain/phase fit. Magnitude floor 1e-15 (m/s)/N; phase unwrapped.",
    }
    (output / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--result", type=Path, default=ROOT / "data/fem/001_resonant_surface/external_solver"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "docs/research/dry_basin/external")
    parser.add_argument("--request", type=Path)
    args = parser.parse_args()
    try:
        path = curate(args.result, args.output, args.request)
    except (OSError, ValueError, KeyError, ImportError) as error:
        parser.error(str(error))
    print(f"External evidence and figures: {path}")


if __name__ == "__main__":
    main()
