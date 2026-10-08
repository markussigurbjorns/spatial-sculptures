"""Check nonlocal fluid inertia, pressure and kinematic surface response before wet playback."""

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
REPORT = ROOT / "docs/research/wet_basin/validation.json"

# Declared numerical criteria; no claim of physical specimen accuracy.
POLICY = {
    "horizontal_response": 0.02,
    "vertical_response": 0.02,
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
}
SOURCES = (
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
    "prototypes/001_resonant_surface/wet/config.py",
    "prototypes/001_resonant_surface/wet/model.py",
    "studies/water/002_potential_flow/reference.py",
    "tools/validate_wet_basin.py",
    "tools/run_wet_basin.py",
    "prototypes/001_resonant_surface/wet/build.py",
)


def source_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def observations(model, physical, sample_hz, count=None):
    """Six paths each, unnormalized complex transfer: contact velocity, pressure, elevation."""
    import numpy as np

    modes, fluid, potentials, pressure, _ = model
    count = len(modes.frequencies) if count is None else count
    forces = np.array(
        [modes.patch_weights(e.patch, e.direction)[:count] for e in physical.exciters]
    )
    contact = modes.weights(*np.asarray(physical.pickups).T)[:, 2, :count]
    surface = fluid.surface_weights(potentials, np.asarray(model[-1]["probe_positions_m"])[:, :2])[
        :, :count
    ]
    omega = 2 * np.pi * np.asarray(sample_hz)
    natural = 2 * np.pi * modes.frequencies[:count]
    compliance = 1 / (
        modes.masses[:count, None]
        * (
            natural[:, None] ** 2
            - omega**2
            + 2j * physical.damping_ratio * natural[:, None] * omega
        )
    )
    return {
        name: np.einsum("pm,em,mf->pef", weights, forces, compliance * factor, optimize=True)
        for name, weights, factor in (
            ("contact_velocity", contact, 1j * omega),
            ("hydrophone_pressure", pressure[:, :count], -(omega**2)),
            ("surface_elevation", surface, np.ones_like(omega)),
        )
    }


def error_record(reference, candidate, weights):
    import numpy as np

    from spatial_sculptures.simulation.convergence import relative_response_error

    result = {}
    for name in reference:
        errors = relative_response_error(reference[name], candidate[name], weights)
        result[name] = {
            "per_path_relative_L2": errors.tolist(),
            "maximum_relative_L2": float(np.max(errors)),
        }
    return result


def passes(record, limit):
    return all(r["maximum_relative_L2"] <= limit for r in record.values())


def check_sources(report):
    if report["source_sha256"] != source_hashes():
        raise ValueError("Wet numerical sources changed; rerun tools/validate_wet_basin.py")


def filtered_pulses(model, physical, settings, counts, *, rate=48000, duration=1.0):
    """All three unit-area finite force pulses; pressure in Pa/(N s), bounded histories."""
    import numpy as np

    from spatial_sculptures.audio.filtering import filter_zero_phase, lowpass_kernel
    from spatial_sculptures.simulation.modal import Mode
    from spatial_sculptures.simulation.mode_bank import ModalResponse

    modes, _, _, pressure, _ = model
    if modes.frequencies[-1] >= rate / 2:
        raise ValueError("Pulse reference needs a sample rate above twice all retained frequencies")
    kernel = lowpass_kernel(rate, settings.output_stop_hz)
    n, guard = round(rate * duration), len(kernel) // 2
    times = np.arange(n + guard) / rate
    parameters = tuple(
        Mode(str(i), float(f), float(m), physical.damping_ratio)
        for i, (f, m) in enumerate(zip(modes.frequencies, modes.masses, strict=True))
    )
    force = 1 / settings.pulse_seconds
    response = ModalResponse(
        parameters,
        [()] * len(parameters),
        [[(0.0, 0.0, 0.0, force), (settings.pulse_seconds, 0.0, 0.0, -force)] for _ in parameters],
    )
    drive_weights = np.array([modes.patch_weights(e.patch, e.direction) for e in physical.exciters])
    result = {c: np.empty((len(pressure), len(drive_weights), len(times))) for c in counts}
    mass = modes.masses[:, None]
    omega = (2 * np.pi * modes.frequencies)[:, None]
    for start in range(0, len(times), 2048):
        part = slice(start, start + 2048)
        q, v = response.trace(times[part], use_numpy=True)
        a = force * (times[part] < settings.pulse_seconds) / mass
        a = a - 2 * physical.damping_ratio * omega * v - omega**2 * q
        for count in counts:
            result[count][..., part] = np.einsum(
                "pm,em,mt->pet",
                pressure[:, :count],
                drive_weights[:, :count],
                a[:count],
                optimize=True,
            )
    return {c: filter_zero_phase(signal, kernel, output_samples=n) for c, signal in result.items()}


def run_validation(physical, settings, *, external=False):
    """Multiple successive refinements; failed wider intervals remain in the report."""
    import numpy as np

    from spatial_sculptures.simulation.convergence import (
        compare_modes,
        resonance_grid,
        trapezoid_weights,
    )
    from spatial_sculptures.simulation.structures import quadrature

    model_module = importlib.import_module("prototypes.001_resonant_surface.wet.model")
    # This first explicit study certifies one resolution family. Avoid silently certifying
    # an untested degree/subspace if editable defaults change; add that family explicitly.
    if (settings.horizontal_degree, settings.vertical_degree, settings.dry_basis_count) != (
        10,
        2,
        256,
    ):
        raise ValueError(
            "This study tests degree 10/2 and dry subspace 256; extend cases for others"
        )
    if settings.playback_count not in (32, 64, 128, 256) or settings.output_stop_hz not in (
        20,
        40,
        80,
        160,
        200,
    ):
        raise ValueError("Choose a tested retained count and interval-edge stop frequency")
    reference = importlib.import_module("studies.water.002_potential_flow.reference")
    print("Analytical and manufactured fluid references", flush=True)
    checks = {
        "manufactured_bowl": reference.manufactured_bowl(),
        "analytical_rigid_cell": reference.rigid_cell_reference(),
    }
    if external:
        print("Independent NGSolve fluid cell (mass and pressure)", flush=True)
        checks["ngsolve_rigid_cell"] = reference.ngsolve_rigid_cell()
    models, rows = {}, {}
    cases = (
        ("horizontal_8", 18, 8, 2, 512, 7, 2),
        ("horizontal_10", 18, 10, 2, 512, 7, 2),
        ("horizontal_12", 18, 12, 2, 512, 7, 2),
        ("vertical_3", 18, 10, 3, 512, 7, 2),
        ("integration", 18, 10, 2, 512, 9, 3),
        ("subspace_256", 18, 10, 2, 256, 7, 2),
        ("mesh_22", 22, 10, 2, 512, 7, 2),
        ("mesh_26", 26, 10, 2, 512, 7, 2),
    )
    for name, cells, degree, vertical, subspace, order, refinement in cases:
        print(
            f"Wet case {name}: dry {cells}×{cells}/{subspace}, fluid {degree}/{vertical}",
            flush=True,
        )
        started = time.perf_counter()
        case = replace(
            settings,
            horizontal_degree=degree,
            vertical_degree=vertical,
            dry_basis_count=subspace,
            playback_count=subspace,
        )
        result = model_module.build_model(
            replace(physical, elements=(cells, cells)),
            case,
            ROOT / "data/fem/001_resonant_surface",
            integration_order=order,
            refinement=refinement,
        )
        models[name] = result
        rows[name] = {
            "settings": asdict(case),
            "elements": [cells, cells],
            "integration_order": order,
            "integration_refinement": refinement,
            "diagnostics": result[-1],
            "frequencies_hz": result[0].frequencies.tolist(),
            "elapsed_seconds": time.perf_counter() - started,
        }
    banks = [m[0].frequencies for m in models.values()]
    frequencies = resonance_grid(banks, physical.damping_ratio, 200.0, 0.025)
    responses = {name: observations(m, physical, frequencies) for name, m in models.items()}
    comparisons = (
        ("horizontal_8_to_10", "horizontal_10", "horizontal_8", "horizontal_response"),
        ("horizontal_10_to_12", "horizontal_12", "horizontal_10", "horizontal_response"),
        ("vertical_2_to_3", "vertical_3", "horizontal_10", "vertical_response"),
        ("integration", "integration", "horizontal_10", "integration_response"),
        ("dry_subspace_256_to_512", "horizontal_10", "subspace_256", "dry_subspace_response"),
        ("mesh_18_to_22", "mesh_22", "horizontal_10", "structural_mesh_response"),
        ("mesh_22_to_26", "mesh_26", "mesh_22", "structural_mesh_response"),
    )
    counts = (32, 64, 128, 256)
    production = models["subspace_256"]
    retained = {c: observations(production, physical, frequencies, c) for c in counts}
    intervals = []
    for lower, upper in ((0, 20), (20, 40), (40, 80), (80, 160), (160, 200)):
        subset = (frequencies >= lower) & (frequencies <= upper)
        weights = trapezoid_weights(frequencies[subset])
        records = {}
        for label, fine, coarse, policy in comparisons:
            record = error_record(
                {k: v[..., subset] for k, v in responses[fine].items()},
                {k: v[..., subset] for k, v in responses[coarse].items()},
                weights,
            )
            records[label] = {
                "errors": record,
                "passed": passes(record, POLICY[policy]),
                "tolerance": POLICY[policy],
            }
        truncation = {}
        for c in counts:
            record = error_record(
                {k: v[..., subset] for k, v in responses["horizontal_10"].items()},
                {k: v[..., subset] for k, v in retained[c].items()},
                weights,
            )
            truncation[c] = {
                "errors": record,
                "passed": passes(record, POLICY["retained_response"]),
            }
        intervals.append(
            {"range_hz": [lower, upper], "comparisons": records, "retained_counts": truncation}
        )
    fine_grid = resonance_grid(
        banks, physical.damping_ratio, settings.output_stop_hz, 0.0125, samples_per_half_width=16
    )
    coarse_grid = frequencies[frequencies <= settings.output_stop_hz]
    fine = observations(production, physical, fine_grid, settings.playback_count)
    coarse = observations(production, physical, coarse_grid, settings.playback_count)
    # Compare integrated path norms under twice the base/resonance sampling density.
    grid_error = {}
    for name in fine:
        fine_norm = np.sqrt(np.sum(trapezoid_weights(fine_grid) * abs(fine[name]) ** 2, axis=-1))
        coarse_norm = np.sqrt(
            np.sum(trapezoid_weights(coarse_grid) * abs(coarse[name]) ** 2, axis=-1)
        )
        grid_error[name] = float(np.max(abs(coarse_norm / fine_norm - 1)))
    x, y, w = quadrature(physical.surface, 12, 12, 6)
    w *= np.sqrt(
        1 + physical.surface.geometry(x, y)[1] ** 2 + physical.surface.geometry(x, y)[2] ** 2
    )
    modal = {}
    for label, fine_name, coarse_name, _ in comparisons:
        fine_modes, coarse_modes = models[fine_name][0], models[coarse_name][0]
        n = int(np.searchsorted(fine_modes.frequencies, settings.output_stop_hz)) + 1
        while (
            n < len(fine_modes.frequencies)
            and fine_modes.frequencies[n] / fine_modes.frequencies[n - 1] - 1 <= 0.002
        ):
            n += 1
        comparison = compare_modes(
            fine_modes.frequencies[:n],
            fine_modes.weights(x, y)[..., :n],
            coarse_modes.frequencies,
            coarse_modes.weights(x, y),
            w,
        )
        modal[label] = {
            "comparison": comparison,
            "passed": all(
                g["maximum_relative_frequency_difference"] <= POLICY["frequency_relative"]
                and g["minimum_subspace_MAC"] >= POLICY["minimum_subspace_MAC"]
                for g in comparison["groups"]
            ),
        }
    print("Finite-pulse pressure convergence after the declared offline output filter", flush=True)
    pulses = filtered_pulses(production, physical, settings, counts)
    pulse_reference = filtered_pulses(models["horizontal_10"], physical, settings, (512,))[512]
    pulse_errors = {
        c: error_record(
            {"pressure": pulse_reference}, {"pressure": pulses[c]}, np.ones(pulses[c].shape[-1])
        )
        for c in counts
    }
    required = [r for r in intervals if r["range_hz"][1] <= settings.output_stop_hz]
    passed = (
        all(c["passed"] for c in checks.values())
        and all(c["passed"] for c in modal.values())
        and all(v <= POLICY["frequency_grid_response"] for v in grid_error.values())
        and all(
            all(c["passed"] for c in row["comparisons"].values())
            and row["retained_counts"][settings.playback_count]["passed"]
            for row in required
        )
        and passes(pulse_errors[settings.playback_count], POLICY["filtered_pulse_response"])
        and all(
            r["diagnostics"]["fluid"]["relative_equation_residual"] <= POLICY["equation_residual"]
            and r["diagnostics"]["fluid"]["added_mass_symmetry_relative"] <= POLICY["mass_symmetry"]
            and r["diagnostics"]["modal"]["maximum_relative_eigen_residual"]
            <= POLICY["equation_residual"]
            for r in rows.values()
        )
    )
    report = {
        "schema": 1,
        "passed": passed,
        "policy": POLICY,
        "scope": (
            "Sampled numerical convergence for a linear pressure-release wet model; "
            "no measured calibration"
        ),
        "tested_stop_hz": settings.output_stop_hz,
        "physical_parameters": asdict(physical),
        "wet_parameters": asdict(settings),
        "references": checks,
        "cases": rows,
        "intervals": intervals,
        "mode_correspondence": modal,
        "frequency_grid_norm_differences": grid_error,
        "filtered_unit_pulse_pressure": {"rate": 48000, "duration_s": 1.0, "counts": pulse_errors},
        "source_sha256": source_hashes(),
        "numpy_version": np.__version__,
        "limitations": [
            "No gravity or capillary restoring force/free-surface resonances",
            "No acoustic radiation, fluid damping, hydrophone transfer or static prestress",
            "Fixed resting wet footprint; no moving contact line",
            "Fluid external reference is a cell, not an independent curved-basin solve",
        ],
    }
    return report, production


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external", action="store_true", help="Also run independent NGSolve cell")
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()
    try:
        config_module = importlib.import_module("prototypes.001_resonant_surface.dry.config")
        wet_module = importlib.import_module("prototypes.001_resonant_surface.wet.config")
        physical = config_module.load_config(BASELINE)
        from tools.run_dry_basin import verify_profile

        verify_profile(physical, BASELINE)
        report, production = run_validation(
            physical, wet_module.WetConfig(), external=args.external
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if report["passed"]:
            import numpy as np

            from spatial_sculptures.simulation.mode_cache import CachedModes, save_modes

            modes, fluid, potentials, pressure, _ = production
            count = report["wet_parameters"]["playback_count"]
            modes_path, fluid_path = (
                args.output.parent / "playback_modes.npz",
                args.output.parent / "playback_fluid.npz",
            )
            save_modes(
                modes_path,
                CachedModes(
                    modes.surface,
                    modes.space,
                    modes.coefficients[..., :count],
                    modes.frequencies[:count],
                    modes.masses[:count],
                    modes.metadata,
                ),
            )
            parameters = {
                name: getattr(fluid.basis, name)
                for name in ("origin_x", "scale_x", "scale_y", "level", "depth")
            }
            np.savez_compressed(
                fluid_path,
                indices=fluid.basis.indices,
                basis=json.dumps(parameters),
                potentials=potentials[:, :count],
                pressure_weights=pressure[:, :count],
            )
            report["playback_artifacts"] = {
                name: {
                    "filename": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for name, path in (("modes", modes_path), ("fluid", fluid_path))
            }
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            f"Wet numerical validation {'PASSED' if report['passed'] else 'FAILED'}: {args.output}"
        )
        return 0 if report["passed"] else 1
    except (OSError, ValueError, ImportError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
