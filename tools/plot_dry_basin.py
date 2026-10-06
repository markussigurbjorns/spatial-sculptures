"""Create publication figures from recorded dry-basin verification and run parameters."""

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "docs/research/dry_basin")
    args = parser.parse_args()
    verification = json.loads((args.data / "verification.json").read_text())
    results = json.loads((args.data / "results.json").read_text())
    for record in (verification, *results["reports"].values()):
        for name, digest in record["source_sha256"].items():
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Stale recorded source {name}; regenerate results first")
    config_module = importlib.import_module("prototypes.001_resonant_surface.dry.config")
    model = importlib.import_module("prototypes.001_resonant_surface.dry.model")
    baseline = results["reports"]["001_baseline"]
    config = config_module.from_dict(baseline["parameters"])
    if model.cache_identity(config)[0] != baseline["cache_key"]:
        raise ValueError("Stale recorded structure; regenerate results first")
    modes, _, _ = model.get_modes(config, ROOT / "data/fem/001_resonant_surface")
    output = args.data / "figures"
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

    def save(fig, name):
        for extension in ("png", "pdf"):
            fig.savefig(output / f"{name}.{extension}", dpi=180)
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), layout="constrained")
    plate = verification["plate"]["meshes"]
    axes[0].semilogy(
        [r["elements_per_axis"] for r in plate],
        [100 * max(map(abs, r["relative_frequency_errors"])) for r in plate],
        "o-",
    )
    axes[0].axhline(0.2, linestyle="--", color="grey", label="0.2% criterion")
    axes[0].set(title="Plate: first six analytical frequencies", ylabel="Maximum difference (%)")
    axes[0].legend()
    shell = verification["dry_basin"]["meshes"][:-1]
    for count in (10, 16):
        axes[1].semilogy(
            [r["elements_per_axis"] for r in shell],
            [100 * max(map(abs, r["relative_difference_from_10x10"][:count])) for r in shell],
            "o-",
            label=f"First {count} ordered frequencies",
        )
    axes[1].set(title="Dry basin: comparison with 10 × 10 cells", ylabel="Maximum difference (%)")
    axes[1].legend()
    for ax in axes:
        ax.set_xlabel("Elements per axis")
        ax.grid(alpha=0.2)
    save(fig, "convergence")

    radius, angle = np.meshgrid(np.linspace(0, 1, 61), np.linspace(0, 2 * np.pi, 181))
    x, y = (
        config.surface.radius_x * radius * np.cos(angle),
        config.surface.radius_y * radius * np.sin(angle),
    )
    shapes = modes.weights(x.ravel(), y.ravel())[:, 2, :].reshape(*x.shape, -1)
    fig, axes = plt.subplots(2, 3, figsize=(10, 5.8), layout="constrained")
    for ax, index in zip(axes.ravel(), (3, 5, 7, 9, 12, 15), strict=True):
        image = ax.contourf(
            x, y, shapes[:, :, index], np.linspace(-1, 1, 21), cmap="RdBu_r", extend="both"
        )
        ax.set(title=f"Mode {index + 1}: {modes.frequencies[index]:.2f} Hz", aspect="equal")
        ax.set(xlabel="x (m)", ylabel="y (m)")
        ax.plot(*np.array([(s.patch.x, s.patch.y) for s in config.supports]).T, "ks", ms=3)
    fig.colorbar(
        image, ax=axes.ravel().tolist(), label="Global vertical shape / sampled vector peak"
    )
    save(fig, "mode_shapes")

    fig, ax = plt.subplots(figsize=(8, 4.2), layout="constrained")
    for name, report in results["reports"].items():
        if name == "006_three_drives":
            continue  # Same structure as baseline; only the drive changes.
        ax.plot(
            np.arange(1, 17),
            report["mode_frequencies_hz"],
            "o-",
            ms=3,
            label=name[4:].replace("_", " "),
        )
    ax.set(
        xlabel="Ordered mode index (not tracked shape identity)",
        ylabel="Frequency (Hz)",
        title="Provisional dry-basin parameter variations",
    )
    ax.legend(ncol=2)
    ax.grid(alpha=0.2)
    save(fig, "parameter_comparison")

    simulation = model.DryBasinSimulation(config, modes)
    times = np.linspace(0, config.duration, 2501)
    q, v = simulation.trace(times)
    pickups = simulation.pickup_velocities(v)
    energy = np.sum(
        0.5 * modes.masses[:, None] * (v**2 + (2 * np.pi * modes.frequencies[:, None]) ** 2 * q**2),
        axis=0,
    )
    fig, axes = plt.subplots(2, 1, figsize=(8, 4.8), sharex=True, layout="constrained")
    for i, channel in enumerate(pickups, 1):
        axes[0].plot(times, channel * 1000, label=f"Contact {i}", linewidth=0.8)
    axes[0].set(
        ylabel="Vertical velocity (mm/s)", title="Default impulse: retained dry-shell response"
    )
    axes[0].legend()
    axes[1].plot(times, energy * 1e6)
    axes[1].set(xlabel="Physical time (s)", ylabel="Retained energy (µJ)")
    for ax in axes:
        ax.grid(alpha=0.2)
    save(fig, "impulse_response")
    print(f"Dry-basin figures: {output.resolve()}")


if __name__ == "__main__":
    main()
