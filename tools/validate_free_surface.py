"""Validate coupled gravity/capillary water, metal and hydrophone observations."""

import argparse
import hashlib
import importlib
import json
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
BASELINE = ROOT / "prototypes/001_resonant_surface/dry/profiles/contact_200hz.json"
REPORT = ROOT / "docs/research/free_surface/validation.json"

# Numerical acceptance for this explicit resolution family, not specimen accuracy.
# Surface truncation and solid resolution: 5%; potential solve: 2%; integration: 1%.
# Exploratory degree-6/8 results motivated degree 10; they are not an acceptance run.
POLICY = {
    "surface_response": 0.05,
    "potential_response": 0.02,
    "integration_response": 0.01,
    "dry_subspace_response": 0.05,
    "structural_mesh_response": 0.05,
    "retained_response": 0.05,
    "filtered_pulse_response": 0.05,
    "frequency_grid_response": 0.01,
    "frequency_relative": 0.01,
    "minimum_subspace_MAC": 0.99,
    "equation_residual": 1e-7,
    "mass_symmetry": 1e-10,
    "volume_compatibility": 1e-10,
}
SOURCES = (
    "src/spatial_sculptures/simulation/free_surface.py",
    "src/spatial_sculptures/simulation/fluid_potential.py",
    "src/spatial_sculptures/simulation/fluid_loading.py",
    "src/spatial_sculptures/simulation/structures.py",
    "src/spatial_sculptures/simulation/splines.py",
    "src/spatial_sculptures/simulation/mode_cache.py",
    "src/spatial_sculptures/simulation/modal.py",
    "src/spatial_sculptures/simulation/mode_bank.py",
    "src/spatial_sculptures/simulation/convergence.py",
    "src/spatial_sculptures/audio/filtering.py",
    "src/spatial_sculptures/audio/synthesis.py",
    "prototypes/001_resonant_surface/dry/config.py",
    "prototypes/001_resonant_surface/dry/model.py",
    "prototypes/001_resonant_surface/dry/build.py",
    "prototypes/001_resonant_surface/wet/model.py",
    "prototypes/001_resonant_surface/wet/build.py",
    "prototypes/001_resonant_surface/free_surface/config.py",
    "prototypes/001_resonant_surface/free_surface/model.py",
    "prototypes/001_resonant_surface/free_surface/build.py",
    "studies/water/003_free_surface/reference.py",
    "tools/validate_free_surface.py",
    "tools/run_free_surface.py",
    "tools/run_wet_basin.py",
    "tools/run_dry_basin.py",
)


def source_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def check_sources(report):
    """Reject stale source or a changed numerical policy before claiming verified playback."""
    if report["source_sha256"] != source_hashes() or report["policy"] != POLICY:
        raise ValueError("Free-surface sources changed; rerun tools/validate_free_surface.py")


def observations(bank, physical, sample_hz, count=None):
    """Complex SI transfer functions; pressure includes its acceleration and gravity terms."""
    import numpy as np

    n = len(bank.metal.frequencies) if count is None else count
    forces = np.asarray(
        [bank.metal.patch_weights(e.patch, e.direction)[:n] for e in physical.exciters]
    )
    xy = np.asarray(physical.pickups)
    contact = bank.metal.weights(*xy.T)[:, 2, :n]
    elevation = bank.surface_weights(xy)[:, :n]
    omega = 2 * np.pi * np.asarray(sample_hz)
    natural = 2 * np.pi * bank.metal.frequencies[:n]
    compliance = 1 / (
        bank.metal.masses[:n, None]
        * (
            natural[:, None] ** 2
            - omega**2
            + 2j * bank.damping[:n, None] * natural[:, None] * omega
        )
    )
    pressure = np.einsum(
        "pm,em,mf->pef", bank.pressure_q[:, :n], forces, compliance, optimize=True
    ) - np.einsum(
        "pm,em,mf->pef", bank.pressure_a[:, :n], forces, compliance * omega**2, optimize=True
    )
    return {
        "hydrophone_pressure": pressure,
        "surface_elevation": np.einsum(
            "pm,em,mf->pef", elevation, forces, compliance, optimize=True
        ),
        "contact_velocity": np.einsum(
            "pm,em,mf->pef", contact, forces, compliance * (1j * omega), optimize=True
        ),
    }


def filtered_pulses(bank, physical, settings, counts, *, rate=48000, duration=1.0):
    """All six pressure paths for finite unit-area pulses and the playback output filter."""
    import numpy as np

    from spatial_sculptures.audio.filtering import filter_zero_phase, lowpass_kernel
    from spatial_sculptures.simulation.modal import Mode
    from spatial_sculptures.simulation.mode_bank import ModalResponse

    if bank.metal.frequencies[-1] >= rate / 2:
        raise ValueError("Pulse reference sample rate below modal Nyquist limit")
    kernel = lowpass_kernel(rate, settings.output_stop_hz)
    n, guard = round(rate * duration), len(kernel) // 2
    times = np.arange(n + guard) / rate
    parameters = tuple(
        Mode(str(i), float(f), float(m), float(d))
        for i, (f, m, d) in enumerate(
            zip(bank.metal.frequencies, bank.metal.masses, bank.damping, strict=True)
        )
    )
    force = 1 / settings.pulse_seconds
    response = ModalResponse(
        parameters,
        [()] * len(parameters),
        [[(0.0, 0.0, 0.0, force), (settings.pulse_seconds, 0.0, 0.0, -force)]] * len(parameters),
    )
    drive = np.asarray([bank.metal.patch_weights(e.patch, e.direction) for e in physical.exciters])
    results = {c: np.empty((len(bank.pressure_a), len(drive), len(times))) for c in counts}
    mass = bank.metal.masses[:, None]
    omega = 2 * np.pi * bank.metal.frequencies[:, None]
    for start in range(0, len(times), 2048):
        part = slice(start, start + 2048)
        q, v = response.trace(times[part], use_numpy=True)
        a = (
            force * (times[part] < settings.pulse_seconds) / mass
            - 2 * bank.damping[:, None] * omega * v
            - omega**2 * q
        )
        for c in counts:
            results[c][..., part] = np.einsum(
                "pm,em,mt->pet", bank.pressure_a[:, :c], drive[:, :c], a[:c], optimize=True
            ) + np.einsum(
                "pm,em,mt->pet", bank.pressure_q[:, :c], drive[:, :c], q[:c], optimize=True
            )
    return {c: filter_zero_phase(value, kernel, output_samples=n) for c, value in results.items()}


def run_validation(physical, settings, *, external=False):
    """References and separate refinement axes; preserve every failing band in the evidence."""
    import numpy as np

    from spatial_sculptures.simulation.convergence import (
        compare_modes,
        resonance_grid,
        trapezoid_weights,
    )
    from spatial_sculptures.simulation.fluid_loading import water_quadrature
    from spatial_sculptures.simulation.structures import quadrature
    from tools.validate_wet_basin import error_record, passes

    if (
        settings.horizontal_degree,
        settings.vertical_degree,
        settings.surface_degree,
        settings.dry_basis_count,
        settings.playback_count,
        settings.output_stop_hz,
    ) != (12, 3, 10, 256, 128, 80.0):
        raise ValueError("This validation family is 12/3 potential, surface 10, dry 256/128, 80 Hz")
    reference = importlib.import_module("studies.water.003_free_surface.reference")
    model = importlib.import_module("prototypes.001_resonant_surface.free_surface.model")
    print("Analytical gravity, gravity/capillary and capillary-only cells", flush=True)
    checks = {"analytical_cells": reference.check_cells()}
    if external:
        print("Independent NGSolve Neumann free-surface cell", flush=True)
        checks["ngsolve_cell"] = reference.ngsolve_cell()
    # Compare successive surface refinements and independent potential/solid refinements.
    cases = (
        ("surface_8", 18, 12, 3, 8, 256, 7, 2),
        ("production", 18, 12, 3, 10, 256, 7, 2),
        ("surface_12", 18, 12, 3, 12, 256, 7, 2),
        ("potential_10", 18, 10, 3, 10, 256, 7, 2),
        ("potential_14", 18, 14, 3, 10, 256, 7, 2),
        ("vertical_4", 18, 12, 4, 10, 256, 7, 2),
        ("integration", 18, 12, 3, 10, 256, 9, 3),
        ("subspace_512", 18, 12, 3, 10, 512, 7, 2),
        ("mesh_22", 22, 12, 3, 10, 512, 7, 2),
        ("mesh_26", 26, 12, 3, 10, 512, 7, 2),
    )
    models, rows = {}, {}
    for name, cells, h, v, s, dry, order, refinement in cases:
        print(
            f"Coupled case {name}: shell {cells}x{cells}/{dry}, potential {h}/{v}, surface {s}",
            flush=True,
        )
        started = time.perf_counter()
        count = dry + (s + 1) * (s + 2) // 2 - 1
        case = replace(
            settings,
            horizontal_degree=h,
            vertical_degree=v,
            surface_degree=s,
            dry_basis_count=dry,
            playback_count=count,
        )
        bank, system, diagnostics = model.build_model(
            replace(physical, elements=(cells, cells)),
            case,
            ROOT / "data/fem/001_resonant_surface",
            integration_order=order,
            refinement=refinement,
        )
        models[name] = bank
        rows[name] = {
            "settings": asdict(case),
            "elements": [cells, cells],
            "integration_order": order,
            "integration_refinement": refinement,
            "diagnostics": diagnostics,
            "frequencies_hz": bank.metal.frequencies.tolist(),
            "elapsed_seconds": time.perf_counter() - started,
        }
    comparisons = (
        ("surface_8_to_10", "production", "surface_8", "surface_response"),
        ("surface_10_to_12", "surface_12", "production", "surface_response"),
        ("potential_10_to_12", "production", "potential_10", "potential_response"),
        ("potential_12_to_14", "potential_14", "production", "potential_response"),
        ("vertical_3_to_4", "vertical_4", "production", "potential_response"),
        ("integration", "integration", "production", "integration_response"),
        ("dry_subspace_256_to_512", "subspace_512", "production", "dry_subspace_response"),
        ("mesh_18_to_22", "mesh_22", "subspace_512", "structural_mesh_response"),
        ("mesh_22_to_26", "mesh_26", "mesh_22", "structural_mesh_response"),
    )
    banks = [b.metal.frequencies for b in models.values()]
    grid = resonance_grid(banks, physical.damping_ratio, 80.0, 0.01)
    responses = {name: observations(bank, physical, grid) for name, bank in models.items()}
    counts = (96, 128, 192, 256)
    retained = {c: observations(models["production"], physical, grid, c) for c in counts}
    intervals = []
    for lower, upper in ((0, 1), (1, 3), (3, 20), (20, 40), (40, 80)):
        use = (grid >= lower) & (grid <= upper)
        weights = trapezoid_weights(grid[use])
        records = {}
        for label, fine, coarse, policy in comparisons:
            error = error_record(
                {k: a[..., use] for k, a in responses[fine].items()},
                {k: a[..., use] for k, a in responses[coarse].items()},
                weights,
            )
            records[label] = {
                "errors": error,
                "tolerance": POLICY[policy],
                "passed": passes(error, POLICY[policy]),
            }
        truncation = {}
        for c in counts:
            error = error_record(
                {k: a[..., use] for k, a in responses["subspace_512"].items()},
                {k: a[..., use] for k, a in retained[c].items()},
                weights,
            )
            truncation[c] = {"errors": error, "passed": passes(error, POLICY["retained_response"])}
        intervals.append(
            {"range_hz": [lower, upper], "comparisons": records, "retained_counts": truncation}
        )
    # Lowest six water shapes on a common area grid; metal shapes above 3 Hz separately.
    x, y, w = quadrature(physical.surface, 12, 12, 6)
    sx, sy, sw, _ = water_quadrature(
        physical.surface,
        system.water,
        np.linspace(-physical.surface.radius_x, physical.surface.radius_x, 13),
        np.linspace(-physical.surface.radius_y, physical.surface.radius_y, 13),
        order=6,
    )
    wet_positive = sw > 0
    water_xy = np.column_stack((sx[wet_positive], sy[wet_positive]))
    sw = sw[wet_positive]
    positive = w > 0
    x, y, w = x[positive], y[positive], w[positive]
    modes_checked = {}
    for label, fine, coarse, _ in comparisons:
        a, b = models[fine], models[coarse]
        water_match = compare_modes(
            a.metal.frequencies[:6],
            a.surface_weights(water_xy)[:, None, :6],
            b.metal.frequencies[:6],
            b.surface_weights(water_xy)[:, None, :6],
            sw,
        )
        # Do not mistake the extra high-order surface modes in a finer bank for metal modes.
        am = (a.metal.frequencies <= 80) & (
            np.asarray(rows[fine]["diagnostics"]["surface_energy_fraction"]) < 0.5
        )
        bm = np.asarray(rows[coarse]["diagnostics"]["surface_energy_fraction"]) < 0.5
        metal_match = compare_modes(
            a.metal.frequencies[am],
            a.metal.weights(x, y)[..., am],
            b.metal.frequencies[bm],
            b.metal.weights(x, y)[..., bm],
            w,
        )
        groups = water_match["groups"] + metal_match["groups"]
        modes_checked[label] = {
            "water_first_six": water_match,
            "metal_above_3hz": metal_match,
            "passed": all(
                g["maximum_relative_frequency_difference"] <= POLICY["frequency_relative"]
                and g["minimum_subspace_MAC"] >= POLICY["minimum_subspace_MAC"]
                for g in groups
            ),
        }
    fine_grid = resonance_grid(
        banks, physical.damping_ratio, 80.0, 0.005, samples_per_half_width=16
    )
    fine = observations(models["production"], physical, fine_grid, settings.playback_count)
    coarse = retained[settings.playback_count]
    grid_errors = {}
    for name in fine:
        fn = np.sqrt(np.sum(trapezoid_weights(fine_grid) * abs(fine[name]) ** 2, axis=-1))
        cn = np.sqrt(np.sum(trapezoid_weights(grid) * abs(coarse[name]) ** 2, axis=-1))
        grid_errors[name] = float(np.max(abs(cn / fn - 1)))
    print("Filtered finite-pulse pressure and retained-mode checks", flush=True)
    pulses = filtered_pulses(models["production"], physical, settings, counts)
    reference_count = len(models["subspace_512"].metal.frequencies)
    pulse_reference = filtered_pulses(
        models["subspace_512"], physical, settings, (reference_count,)
    )[reference_count]
    pulse_errors = {
        c: error_record(
            {"pressure": pulse_reference}, {"pressure": pulses[c]}, np.ones(pulses[c].shape[-1])
        )
        for c in counts
    }
    passed = (
        all(row["passed"] for row in checks.values())
        and all(row["passed"] for row in modes_checked.values())
        and all(error <= POLICY["frequency_grid_response"] for error in grid_errors.values())
        and all(
            all(c["passed"] for c in row["comparisons"].values())
            and row["retained_counts"][settings.playback_count]["passed"]
            for row in intervals
        )
        and passes(pulse_errors[settings.playback_count], POLICY["filtered_pulse_response"])
        and all(
            row["diagnostics"]["fluid"]["fluid_equation_relative_residual"]
            <= POLICY["equation_residual"]
            and row["diagnostics"]["fluid"]["fluid_mass_symmetry_relative"]
            <= POLICY["mass_symmetry"]
            and row["diagnostics"]["fluid"]["flux_compatibility_relative"]
            <= POLICY["volume_compatibility"]
            and row["diagnostics"]["modal"]["eigen_relative_residual"]
            <= POLICY["equation_residual"]
            for row in rows.values()
        )
    )
    return {
        "schema": 1,
        "passed": passed,
        "policy": POLICY,
        "scope": "Linear frozen-shell gravity/capillary system; sampled observation convergence",
        "tested_stop_hz": settings.output_stop_hz,
        "physical_parameters": asdict(physical),
        "free_surface_parameters": asdict(settings),
        "references": checks,
        "cases": rows,
        "intervals": intervals,
        "mode_correspondence": modes_checked,
        "frequency_grid_norm_differences": grid_errors,
        "filtered_unit_pulse_pressure": {"rate": 48000, "duration_s": 1.0, "counts": pulse_errors},
        "source_sha256": source_hashes(),
        "numpy_version": np.__version__,
        "limitations": rows["production"]["diagnostics"]["limitations"]
        + [
            "Lowest six water modes checked; high-order surface spectrum is not uniformly verified",
            "Independent fluid validation is a rectangular cell, not a coupled curved vessel",
            "No measured calibration, acoustic radiation, microphone model or wider audio band",
        ],
    }, models["production"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--external", action="store_true", help="Also check independent NGSolve cell"
    )
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()
    try:
        config = importlib.import_module("prototypes.001_resonant_surface.dry.config")
        free = importlib.import_module("prototypes.001_resonant_surface.free_surface.config")
        model = importlib.import_module("prototypes.001_resonant_surface.free_surface.model")
        from tools.run_dry_basin import verify_profile

        physical = config.load_config(BASELINE)
        verify_profile(physical, BASELINE)
        settings = free.FreeSurfaceConfig()
        physical.duration = settings.duration_s
        report, bank = run_validation(physical, settings, external=args.external)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if report["passed"]:
            mpath, fpath = (
                args.output.parent / "playback_modes.npz",
                args.output.parent / "playback_fluid.npz",
            )
            model.save_bank(mpath, fpath, model.retained_bank(bank, settings.playback_count))
            report["playback_artifacts"] = {
                name: {
                    "filename": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for name, path in (("modes", mpath), ("fluid", fpath))
            }
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            f"Free-surface validation {'PASSED' if report['passed'] else 'FAILED'}: {args.output}"
        )
        return 0 if report["passed"] else 1
    except (OSError, ValueError, ImportError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
