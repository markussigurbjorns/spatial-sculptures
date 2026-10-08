"""Create standalone figures from the verified free-surface bank and reference evidence."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def make_figure(evidence, output):
    """Plot three low water modes and the separate rigid-cell convergence checks."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri
    import numpy as np

    from tools.run_free_surface import load_verified_model
    from tools.run_wet_basin import water_mesh

    _, _, bank, report = load_verified_model(evidence)
    vertices, faces = water_mesh(bank.metal.surface, bank.potential_basis, 20, 96)
    triangles = []
    for face in faces:
        triangles.append((face[0], face[1], face[2]))
        if len(face) == 4:
            triangles.append((face[0], face[2], face[3]))
    mesh = mtri.Triangulation(*vertices[:, :2].T, np.asarray(triangles))
    weights = bank.surface_weights(vertices[:, :2])
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), layout="constrained")
    for index, ax in enumerate(axes.ravel()[:3]):
        shape = weights[:, index] / np.max(abs(weights[:, index]))
        artist = ax.tripcolor(mesh, shape, shading="gouraud", cmap="RdBu_r", vmin=-1, vmax=1)
        fig.colorbar(artist, ax=ax, label="relative elevation / peak")
        ax.set(
            title=f"Water mode {index + 1}: {bank.metal.frequencies[index]:.4f} Hz",
            xlabel="x (m)",
            ylabel="y (m)",
            aspect="equal",
        )
    ax = axes.ravel()[3]
    labels = ("gravity", "gravity + capillary", "capillary only")
    for name, case in zip(labels, report["references"]["analytical_cells"]["cases"], strict=True):
        refinements = case["refinements"]
        ax.semilogy(
            [r["degree"] for r in refinements],
            [r["frequency_maximum_relative_difference"] for r in refinements],
            marker="o",
            label=name,
        )
    ax.set(
        title="Rigid-cell frequency convergence",
        xlabel="potential horizontal degree",
        ylabel="maximum relative difference",
    )
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.suptitle("Linear gravity/capillary water — frozen dry-shell equilibrium")
    output.parent.mkdir(parents=True, exist_ok=True)
    paths = (output.with_suffix(".png"), output.with_suffix(".pdf"))
    for path in paths:
        fig.savefig(path, dpi=180)
    plt.close(fig)
    provenance = {
        "validation_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
        "plot_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "artifacts": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "notes": "Mode shapes independently normalized for display; no physical amplitude implied",
    }
    output.with_suffix(".json").write_text(json.dumps(provenance, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence", type=Path, default=ROOT / "docs/research/free_surface/validation.json"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "docs/research/free_surface/modes")
    args = parser.parse_args()
    make_figure(args.evidence, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
