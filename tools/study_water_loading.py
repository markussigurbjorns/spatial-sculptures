"""Study provisional water inertia on the dry basin; no audio/Blender dependency."""

import argparse
import hashlib
import importlib
import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def loaded_case(system, dry, config, water, settings, output, index):
    """Solve one depth and a refined integration rule; retain numerical gates and modes."""
    import numpy as np

    from spatial_sculptures.simulation.fluid_loading import with_column_water
    from spatial_sculptures.simulation.mode_cache import modes_from_system, save_modes

    print(f"Loading depth {water.depth_m * 1000:g} mm...", flush=True)
    wet, loading = with_column_water(
        system,
        water,
        order=settings.integration_order,
        refinement=settings.integration_refinement,
    )
    refined, higher = with_column_water(
        system,
        water,
        order=settings.integration_order + 2,
        refinement=settings.integration_refinement + 1,
    )
    modes = modes_from_system(
        wet, config.mode_count, {"water": asdict(water)}, backend=config.eigensolver
    )
    finer = modes_from_system(refined, config.mode_count, {}, backend=config.eigensolver)
    frequency_error = float(np.max(np.abs(modes.frequencies / finer.frequencies - 1)))
    matrix_error = float(
        np.linalg.norm(loading.matrix - higher.matrix) / max(np.linalg.norm(higher.matrix), 1e-30)
    )
    volume_error = abs(loading.volume_m3 / higher.volume_m3 - 1) if higher.volume_m3 else 0.0
    # Sorted eigenvalues compare the same discrete structure, not mode identities
    # across different depths. Load changes can rotate/reorder physical modes.
    ratios = modes.frequencies / dry.frequencies
    minimum_mass_eigenvalue = float(np.linalg.eigvalsh(loading.matrix)[0])
    mass_scale = max(float(np.trace(loading.matrix)), 1.0)
    checks = {
        "integration_frequency_passed": frequency_error < 0.001,
        "integration_matrix_passed": matrix_error < 0.001,
        "integration_volume_passed": volume_error < 0.001,
        "nonnegative_added_inertia_passed": minimum_mass_eigenvalue > -1e-10 * mass_scale,
        "ordered_frequencies_nonincreasing_passed": bool(np.all(ratios <= 1 + 1e-8)),
        "dry_stiffness_preserved_passed": bool(np.array_equal(wet.stiffness, system.stiffness)),
        "zero_depth_recovers_dry_passed": bool(np.array_equal(wet.mass, system.mass))
        if water.depth_m == 0
        else None,
    }
    coefficients = modes.coefficients[list(system.components)].reshape(-1, config.mode_count)
    fluid_fraction = np.sum(coefficients * (loading.matrix @ coefficients), axis=0) / modes.masses
    name = f"depth_{index + 1}_modes.npz"
    save_modes(output / name, modes)
    record = {
        "water": asdict(water),
        "surface_level_m": loading.surface_level_m,
        "volume_m3": loading.volume_m3,
        "water_mass_kg": loading.water_mass_kg,
        "wetted_projected_area_m2": loading.wetted_projected_area_m2,
        "frequencies_hz": modes.frequencies.tolist(),
        "ordered_frequency_ratios_to_dry": ratios.tolist(),
        "water_fraction_of_modal_inertia": fluid_fraction.tolist(),
        "integration_refinement": {
            "maximum_relative_frequency_difference": frequency_error,
            "relative_matrix_difference": matrix_error,
            "relative_volume_difference": volume_error,
        },
        "checks": checks,
        "diagnostics": modes.metadata["diagnostics"],
        "modal_archive": name,
    }
    return record, digest(output / name)


def study(baseline: Path, output: Path, settings, *, external_plate=False):
    """Check the approximation separately from integration and dry-reference agreement."""
    import numpy as np

    from spatial_sculptures.simulation.fluid_loading import ColumnWater
    from spatial_sculptures.simulation.mode_cache import modes_from_system
    from spatial_sculptures.simulation.structures import AttachedMass, assemble_shell
    from tools.run_dry_basin import verify_profile

    configuration = importlib.import_module("prototypes.001_resonant_surface.dry.config")
    dry_model = importlib.import_module("prototypes.001_resonant_surface.dry.model")
    reference = importlib.import_module("studies.water.001_column_loading.reference")
    config = configuration.load_config(baseline)
    dry_model.validate_config(config)
    verification = verify_profile(config, baseline)
    if not settings.depths_m or len(set(settings.depths_m)) != len(settings.depths_m):
        raise ValueError("At least one distinct water depth required")
    # Validate depth/density settings before writing results or launching a solve.
    waters = [ColumnWater(d, settings.density_kg_m3) for d in settings.depths_m]
    output.mkdir(parents=True, exist_ok=True)
    print("Checking analytical flat plate and shallow-limit approximation...", flush=True)
    plate = reference.check_plate_assembly()
    analytic = reference.analytical_cases()
    shallow_errors = [
        m["relative_frequency_approximation_error"]
        for r in analytic
        if r["depth_m"] <= 0.005
        for m in r["modes"]
    ]
    external = {"status": "not_requested", "passed": None}
    if external_plate:
        print("Checking the independent 3D potential-flow reference...", flush=True)
        external = {"status": "executed", **reference.check_potential_cell()}
    print("Assembling the baseline dry basin once...", flush=True)
    system = assemble_shell(
        config.surface,
        config.material,
        config.thickness,
        elements=config.elements,
        gauss_order=config.gauss_order,
        patch_refinement=config.patch_refinement,
        supports=config.supports,
        attached_masses=tuple(
            AttachedMass(e.patch, e.added_mass_kg) for e in config.exciters if e.added_mass_kg
        ),
    )
    dry = modes_from_system(system, config.mode_count, {}, backend=config.eigensolver)
    cached, cache_path, _ = dry_model.get_modes(config, ROOT / "data/fem/001_resonant_surface")
    dry_error = float(np.max(np.abs(dry.frequencies / cached.frequencies - 1)))
    records = []
    artifacts = {}
    for index, water in enumerate(waters):
        record, artifact_digest = loaded_case(system, dry, config, water, settings, output, index)
        records.append(record)
        artifacts[record["modal_archive"]] = artifact_digest
    passed = (
        plate["passed"]
        and max(shallow_errors) < 0.001
        and dry_error < 1e-8
        and external["passed"] is not False
        and all(all(v is not False for v in r["checks"].values()) for r in records)
    )
    source_names = (
        "src/spatial_sculptures/simulation/fluid_loading.py",
        "src/spatial_sculptures/simulation/structures.py",
        "src/spatial_sculptures/simulation/splines.py",
        "src/spatial_sculptures/simulation/mode_cache.py",
        "studies/water/001_column_loading/reference.py",
        "prototypes/001_resonant_surface/water_loading/config.py",
        "tools/study_water_loading.py",
        "prototypes/001_resonant_surface/dry/config.py",
        "prototypes/001_resonant_surface/dry/model.py",
        "tools/run_dry_basin.py",
    )
    report = {
        "schema": 1,
        "status": "passed" if passed else "failed",
        "scope": (
            "Numerical checks of provisional shallow-column inertia; "
            "no wet-basin accuracy certificate."
        ),
        "runtime": {"numpy": np.__version__},
        "baseline_configuration": asdict(config),
        "baseline_sha256": digest(baseline),
        "baseline_path": str(baseline.resolve().relative_to(ROOT))
        if baseline.resolve().is_relative_to(ROOT)
        else str(baseline.resolve()),
        "dry_band_verification": verification,
        "dry_mode_cache": str(cache_path.relative_to(ROOT)),
        "dry_cache_frequency_agreement_relative": dry_error,
        "study_settings": asdict(settings),
        "dry_frequencies_hz": dry.frequencies.tolist(),
        "plate_assembly": plate,
        "finite_depth_analytical_reference": analytic,
        "external_potential_cell": external,
        "shallow_reference_maximum_relative_frequency_error": max(shallow_errors),
        "numerical_policy": {
            "plate_frequency_relative": 0.002,
            "shallow_reference_frequency_relative": 0.001,
            "integration_frequency_matrix_volume_relative": 0.001,
            "dry_cache_frequency_relative": 1e-8,
        },
        "depth_cases": records,
        "modal_artifacts_sha256": artifacts,
        "source_sha256": {name: digest(ROOT / name) for name in source_names},
        "wet_contact_band_validated": False,
        "hydrophone_pressure_available": False,
        "limitations": [
            "Local shallow-column approximation; no lateral fluid solve in the basin.",
            "Pressure-release top; gravity/capillary sloshing and fluid damping absent.",
            "No hydrostatic prestress or physical measurements; mid-surface used as wetted floor.",
            "Dry 200 Hz contact certificate does not transfer to these loaded configurations.",
            "Flat reference has pressure-release sides; not a rigid-wall tank or basin validation.",
        ],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    write_summary(report, output / "summary.md")
    return report


def write_summary(report, path):
    lines = [
        "# Provisional water-loading study",
        "",
        report["scope"],
        "",
        f"Numerical checks: **{report['status']}**. Water depth is above the deepest floor point.",
        "",
        "| Depth (mm) | Water (kg) | First ordered frequency (Hz) |",
        "| ---: | ---: | ---: |",
    ]
    for row in report["depth_cases"]:
        lines.append(
            f"| {1000 * row['water']['depth_m']:g} | {row['water_mass_kg']:.3f} "
            f"| {row['frequencies_hz'][0]:.5f} |"
        )
    lines += [
        "",
        "Sorted frequency ranks are not tracked mode identities. "
        "Water-loaded contact audio and hydrophone pressure remain unvalidated.",
        "",
        "See report.json for the analytical approximation errors, independent fluid "
        "reference status, integration checks and source/artifact hashes.",
        "",
    ]
    path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "prototypes/001_resonant_surface/dry/profiles/contact_200hz.json",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/fem/001_resonant_surface/water_loading"
    )
    parser.add_argument(
        "--depths", type=float, nargs="+", help="Depths in metres; zero recovers dry"
    )
    parser.add_argument("--density", type=float)
    parser.add_argument(
        "--external-plate",
        action="store_true",
        help="Also check a separate NGSolve 3D potential-flow cell",
    )
    args = parser.parse_args()
    try:
        module = importlib.import_module("prototypes.001_resonant_surface.water_loading.config")
        settings = module.LoadingStudyConfig()
        overrides = {}
        if args.depths is not None:
            overrides["depths_m"] = tuple(args.depths)
        if args.density is not None:
            overrides["density_kg_m3"] = args.density
        settings = module.LoadingStudyConfig(**{**asdict(settings), **overrides})
        if args.external_plate and importlib.util.find_spec("ngsolve") is None:
            raise ImportError("--external-plate requires the optional .[external] extra")
        report = study(args.baseline, args.output, settings, external_plate=args.external_plate)
    except (ImportError, OSError, ValueError, TypeError) as error:
        parser.error(str(error))
    print(f"Water-loading numerical checks {report['status']}: {args.output.resolve()}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
