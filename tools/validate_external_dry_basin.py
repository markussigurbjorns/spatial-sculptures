"""Run the optional NGSolve dry-shell study and compare SI contact responses.

The external model independently assembles its shell. Production modules are
used here only to prepare requests and compare outputs, never to assemble the
external model. A comparison pass requires the external refinement checks too.
"""

import argparse
import importlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
STUDY = "studies.plates.003_external_shell.model"
DEFAULT_OUTPUT = ROOT / "data/fem/001_resonant_surface/external_solver"
POLICY = {
    "plate_frequency_relative": 0.005,
    "external_frequency_relative": 0.0025,
    "external_minimum_subspace_MAC": 0.995,
    "mesh_response_relative_L2": 0.05,
    "modal_truncation_relative_L2": 0.05,
    "quadrature_response_relative_L2": 0.01,
    "rim_response_relative_L2": 0.01,
    "frequency_grid_relative_L2": 0.01,
    "production_frequency_relative": 0.01,
    "production_minimum_subspace_MAC": 0.99,
    "production_response_relative_L2": 0.10,
}
REQUIRED_GATES = {
    "mesh_1_to_2",
    "mesh_1_to_2_shapes",
    "mesh_2_to_3",
    "mesh_2_to_3_shapes",
    "quadrature",
    "quadrature_shapes",
    "rim",
    "rim_shapes",
    "truncation",
    "frequency_grid",
}


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def dependency_status():
    """Report the missing runtime without importing any Blender consumer."""
    try:
        ng, np, scipy = importlib.import_module(STUDY).dependencies()
    except (ImportError, OSError) as error:
        return {"available": False, "reason": str(error), "solver_result_available": False}
    return {
        "available": True,
        "ngsolve": ng.__version__,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }


def intervals(frequencies):
    """Whole interval plus smaller listening bands; do not mask high-band errors."""
    import numpy as np

    low, high = float(frequencies[0]), float(frequencies[-1])
    edges = [low, *[v for v in (40.0, 80.0, 160.0) if low < v < high], high]
    if len(frequencies) < 2 or not np.all(np.isfinite(frequencies)) or low < 0 or high <= low:
        raise ValueError("A finite increasing frequency interval is required")
    if not all(np.any(np.isclose(frequencies, edge, rtol=0, atol=1e-12)) for edge in edges):
        raise ValueError("Request needs explicit comparison interval edges; prepare it again")
    return [(low, high), *zip(edges[:-1], edges[1:], strict=True)]


def response_checks(reference, candidate, frequencies, tolerance):
    """Compare raw complex values by path and interval, with no gain or phase fitting."""
    import numpy as np

    from spatial_sculptures.simulation.convergence import relative_response_error, trapezoid_weights

    records = []
    for low, high in intervals(frequencies):
        mask = (frequencies >= low) & (frequencies <= high)
        if mask.sum() < 2:
            raise ValueError("Every interval needs at least two samples")
        errors = relative_response_error(
            reference[..., mask], candidate[..., mask], trapezoid_weights(frequencies[mask])
        )
        maximum = float(errors.max()) if np.all(np.isfinite(errors)) else None
        records.append(
            {
                "interval_hz": [low, high],
                "maximum_relative_L2": maximum,
                "per_path_relative_L2": [
                    [float(v) if np.isfinite(v) else None for v in row] for row in errors
                ],
                "passed": maximum is not None and maximum <= tolerance,
            }
        )
    return {
        "tolerance": tolerance,
        "intervals": records,
        "passed": all(row["passed"] for row in records),
    }


def mode_count_for_shapes(frequencies, cutoff):
    """Include the band and the next complete close-frequency cluster (at least twelve)."""
    import numpy as np

    count = min(
        len(frequencies), max(12, int(np.searchsorted(frequencies, cutoff, side="right")) + 1)
    )
    while count < len(frequencies) and frequencies[count] / frequencies[count - 1] - 1 <= 0.002:
        count += 1
    return count


def probe_grid(surface):
    """Common physical-area mode-shape observations, independent of either basis."""
    import numpy as np

    node, weights = np.polynomial.legendre.leggauss(12)
    rx, ry = surface["radius_x"], surface["radius_y"]
    if surface["domain"] == "ellipse":
        radius, angle = np.meshgrid(
            np.sqrt((node + 1) / 2), np.arange(48) * 2 * np.pi / 48, indexing="ij"
        )
        x, y = (
            rx * radius.ravel() * np.cos(angle.ravel()),
            ry * radius.ravel() * np.sin(angle.ravel()),
        )
        measure = np.repeat(weights / 4, 48) * 2 * np.pi / 48 * rx * ry
    else:
        x, y = np.meshgrid(rx * node, ry * node, indexing="ij")
        x, y, measure = x.ravel(), y.ravel(), np.outer(weights, weights).ravel() * rx * ry
    a, b = x / rx, y / ry
    zx = (2 * surface["rise"] * a + surface["asymmetry"] * (1 - 3 * a * a - b * b)) / rx
    zy = (2 * surface["rise"] * b - 2 * surface["asymmetry"] * a * b) / ry
    return x, y, measure * np.sqrt(1 + zx * zx + zy * zy)


def shape_check(reference, candidate, weights, count, *, production=False):
    from spatial_sculptures.simulation.convergence import compare_modes

    result = compare_modes(
        reference["frequencies"][:count],
        reference["shapes"][..., :count],
        candidate["frequencies"][: candidate["shapes"].shape[-1]],
        candidate["shapes"],
        weights,
    )
    prefix = "production" if production else "external"
    for group in result["groups"]:
        group["reference_frequencies_hz"] = [
            float(reference["frequencies"][i]) for i in group["reference_indices"]
        ]
    result["frequency_tolerance"] = POLICY[f"{prefix}_frequency_relative"]
    result["minimum_subspace_MAC"] = POLICY[f"{prefix}_minimum_subspace_MAC"]
    result["passed"] = bool(result["groups"]) and all(
        g["maximum_relative_frequency_difference"] <= result["frequency_tolerance"]
        and g["minimum_subspace_MAC"] >= result["minimum_subspace_MAC"]
        for g in result["groups"]
    )
    result["scope"] = "Physical-area-weighted XYZ shapes; sampled MAC is not measured accuracy."
    return result


def final_status(plate, refinements, agreement, production_shapes):
    """Agreement alone never promotes an unresolved external solve into validation."""
    if not REQUIRED_GATES.issubset(refinements):
        return "failed"
    passed = (
        plate.get("passed") is True
        and all(check.get("passed") is True for check in refinements.values())
        and agreement.get("sampled_agreement_passed") is True
        and production_shapes.get("passed") is True
    )
    return "passed" if passed else "failed"


def run(
    request_path,
    output,
    *,
    maxh=(0.12, 0.085, 0.06),
    rim_segments=(32, 48, 64),
    counts=(256, 384, 512),
    order=3,
    bonus_intorder=6,
    geometry_order=2,
):
    """Execute independent prerequisites/refinements, then consume the comparison request."""
    import numpy as np

    from tools.check_dry_response import (
        CONVENTION,
        UNITS,
        compare,
        digest,
        prepare,
        read_csv,
        write_csv,
    )

    study = importlib.import_module(STUDY)
    runtime = dependency_status()
    if not runtime["available"]:
        raise ImportError(runtime["reason"])
    if (
        len(maxh) != len(rim_segments)
        or len(maxh) < 3
        or len(counts) < 3
        or any(a <= b for a, b in zip(maxh[:-1], maxh[1:], strict=True))
        or any(a >= b for a, b in zip(rim_segments[:-1], rim_segments[1:], strict=True))
        or any(a >= b for a, b in zip(counts[:-1], counts[1:], strict=True))
    ):
        raise ValueError("Need three decreasing mesh lengths and increasing rim/mode counts")
    output.mkdir(parents=True, exist_ok=True)
    # Clear status immediately so an interrupted run cannot leave an earlier pass current.
    write_json(output / "report.json", {"status": "running", "solver_result_available": False})
    plate = study.plate_check(maxh=maxh[-1], order=order, bonus_intorder=bonus_intorder)
    write_json(output / "plate_check.json", plate)
    if not plate["passed"]:
        report = {
            "status": "failed",
            "stage": "analytical_plate_prerequisite",
            "plate": plate,
            "solver_result_available": False,
            "policy": POLICY,
        }
        write_json(output / "report.json", report)
        return report
    if request_path is None:
        request_path = prepare(
            ROOT / "prototypes/001_resonant_surface/dry/profiles/contact_200hz.json",
            output / "request",
            step_hz=0.025,
        )
    request_path = request_path.resolve()
    request = json.loads(request_path.read_text())
    if (
        request.get("schema") != 1
        or request.get("units") != UNITS
        or request.get("harmonic_convention") != CONVENTION
    ):
        raise ValueError("Unsupported comparison request")
    parameters = request["parameters"]
    study.check_parameters(parameters)
    grid, _ = read_csv(
        request_path.parent / "model_mobility.csv",
        len(parameters["pickups"]),
        len(parameters["exciters"]),
    )
    intervals(grid)
    # Check request/source identity before costly external assembly. Labelled tool check only.
    compare(
        request_path,
        request_path.parent / "model_mobility.csv",
        request_path.parent / "model_source.json",
        output / "exchange_self_check.json",
    )
    probe_x, probe_y, weights = probe_grid(parameters["surface"])
    settings = [
        study.Settings(
            maxh=h,
            rim_segments=r,
            order=order,
            bonus_intorder=bonus_intorder,
            mode_count=counts[-1],
            geometry_order=geometry_order,
        )
        for h, r in zip(maxh, rim_segments, strict=True)
    ]
    snapshots, artifacts = [], {}

    def snapshot(name, configuration):
        print(
            f"External {name}: h={configuration.maxh:g} m, rim={configuration.rim_segments}, "
            f"{configuration.mode_count} modes",
            flush=True,
        )
        modes = study.solve(parameters, configuration)
        needed = mode_count_for_shapes(modes.frequencies, grid[-1])
        candidate_count = min(len(modes.frequencies), max(2 * needed, needed + 12))
        shapes = modes.sample_shapes(probe_x, probe_y, candidate_count)
        responses = {n: modes.mobility(grid, parameters["damping_ratio"], n) for n in counts}
        # Serialize reproducible residues and observations, not production matrices.
        archive = output / f"{name}_modes.npz"
        np.savez_compressed(
            archive,
            frequencies_hz=modes.frequencies,
            pickup_weights=modes.pickup_weights,
            force_weights=modes.force_weights,
            probe_x=probe_x,
            probe_y=probe_y,
            probe_area_weights=weights,
            shapes=shapes,
        )
        artifacts[archive.name] = digest(archive)
        diagnostics = {"settings": asdict(configuration), **modes.diagnostics}
        write_json(output / f"{name}_diagnostics.json", diagnostics)
        # The returned closure holds only small modal residues, not the FEM mesh/matrices.
        residue_model = study.ExternalModes(
            modes.frequencies,
            modes.pickup_weights,
            modes.force_weights,
            None,
            None,
            None,
            None,
            diagnostics,
        )
        return {
            "frequencies": modes.frequencies,
            "shapes": shapes,
            "responses": responses,
            "needed_shapes": needed,
            "diagnostics": diagnostics,
            "mobility": residue_model.mobility,
        }

    for i, configuration in enumerate(settings):
        snapshots.append(snapshot(f"mesh_{i + 1}", configuration))
    fine = snapshots[-1]
    quadrature = snapshot(
        "quadrature",
        study.Settings(**{**asdict(settings[-1]), "bonus_intorder": bonus_intorder + 2}),
    )
    rim = snapshot(
        "rim", study.Settings(**{**asdict(settings[-1]), "rim_segments": rim_segments[-1] * 2})
    )
    full = counts[-1]
    shape_count = fine["needed_shapes"]
    if shape_count >= fine["shapes"].shape[-1] or fine["frequencies"][-1] <= grid[-1]:
        raise ValueError("External modes do not cover the comparison band; increase the bank")
    checks = {}
    for i, coarse in enumerate(snapshots[:-1]):
        finer = snapshots[i + 1]
        checks[f"mesh_{i + 1}_to_{i + 2}"] = response_checks(
            finer["responses"][full],
            coarse["responses"][full],
            grid,
            POLICY["mesh_response_relative_L2"],
        )
        checks[f"mesh_{i + 1}_to_{i + 2}_shapes"] = shape_check(
            finer, coarse, weights, finer["needed_shapes"]
        )
    for name, candidate, tolerance in (
        ("quadrature", quadrature, POLICY["quadrature_response_relative_L2"]),
        ("rim", rim, POLICY["rim_response_relative_L2"]),
    ):
        checks[name] = response_checks(
            fine["responses"][full], candidate["responses"][full], grid, tolerance
        )
        checks[f"{name}_shapes"] = shape_check(fine, candidate, weights, shape_count)
    checks["truncation"] = response_checks(
        fine["responses"][full],
        fine["responses"][counts[-2]],
        grid,
        POLICY["modal_truncation_relative_L2"],
    )
    # Record every requested bank; the final pair is the completeness gate.
    truncation = {
        str(n): response_checks(
            fine["responses"][full],
            fine["responses"][n],
            grid,
            POLICY["modal_truncation_relative_L2"],
        )
        for n in counts[:-1]
    }
    extra = []
    for frequency in fine["frequencies"]:
        if grid[0] <= frequency <= grid[-1]:
            half_width = parameters["damping_ratio"] * frequency
            extra.extend(frequency + np.linspace(-3, 3, 49) * half_width)
    dense = np.unique(np.r_[grid, (grid[:-1] + grid[1:]) / 2, extra])
    dense = dense[(dense >= grid[0]) & (dense <= grid[-1])]
    interpolated = np.array(
        [[np.interp(dense, grid, path) for path in pickup] for pickup in fine["responses"][full]]
    )
    checks["frequency_grid"] = response_checks(
        fine["mobility"](dense, parameters["damping_ratio"]),
        interpolated,
        dense,
        POLICY["frequency_grid_relative_L2"],
    )
    # These imports belong to postprocessing, not to the external shell assembly.
    config = importlib.import_module("prototypes.001_resonant_surface.dry.config").from_dict(
        parameters
    )
    production = importlib.import_module("prototypes.001_resonant_surface.dry.model")
    predicted, _, _ = production.get_modes(config, ROOT / "data/fem/001_resonant_surface")
    production_shapes = {
        "frequencies": predicted.frequencies,
        "shapes": predicted.weights(probe_x, probe_y),
    }
    shape_agreement = shape_check(fine, production_shapes, weights, shape_count, production=True)
    csv_path = output / "external_mobility.csv"
    write_csv(csv_path, grid, fine["responses"][full])
    source = {
        "kind": "external_solver",
        "source": f"NGSolve {runtime['ngsolve']}, hybrid HHJ/Regge graph shell",
        "units": UNITS,
        "harmonic_convention": CONVENTION,
        "request_sha256": digest(request_path),
        "data_sha256": digest(csv_path),
        "solver_source_sha256": {
            "studies/plates/003_external_shell/model.py": digest(
                ROOT / "studies/plates/003_external_shell/model.py"
            ),
            "tools/validate_external_dry_basin.py": digest(Path(__file__)),
        },
        "external_refinement_checks_passed": all(check["passed"] for check in checks.values()),
        "notes": "Independently assembled shell; refined rim geometry and Regge membrane strain. "
        "Agreement is provisional unless plate, mesh, modal, rim, quadrature and grid gates pass.",
    }
    write_json(output / "external_source.json", source)
    agreement = compare(
        request_path,
        csv_path,
        output / "external_source.json",
        output / "comparison.json",
        tolerance=POLICY["production_response_relative_L2"],
    )
    report = {
        "schema": 1,
        "status": final_status(plate, checks, agreement, shape_agreement),
        "solver_result_available": True,
        "runtime": runtime,
        "policy": POLICY,
        "parameters": parameters,
        "request_sha256": digest(request_path),
        "solver_source_sha256": source["solver_source_sha256"],
        "modal_artifacts_sha256": artifacts,
        "plate": plate,
        "external_checks": checks,
        "truncation_banks": truncation,
        "production_shape_comparison": shape_agreement,
        "production_response_comparison": agreement,
        "external_meshes": [v["diagnostics"] for v in snapshots],
        "scope": "Numerical cross-validation of a provisional dry shell; no vessel measurement.",
        "limitations": [
            "No water, prestress, shear/rotary inertia or mounting compliance.",
            "Finite refinement/sampling evidence is not an exact error bound.",
            "A failure is retained; no fitted gain, phase or relaxed thresholds.",
        ],
    }
    write_json(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--request", type=Path, help="Prepared exchange request; default prepares contact_200hz"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check-dependencies", action="store_true")
    parser.add_argument("--maxh", type=float, nargs="+", default=[0.12, 0.085, 0.06])
    parser.add_argument("--rim-segments", type=int, nargs="+", default=[32, 48, 64])
    parser.add_argument("--mode-counts", type=int, nargs="+", default=[256, 384, 512])
    parser.add_argument("--order", type=int, default=3)
    parser.add_argument("--bonus-intorder", type=int, default=6)
    parser.add_argument("--geometry-order", type=int, choices=[1, 2], default=2)
    args = parser.parse_args()
    status = dependency_status()
    if args.check_dependencies:
        print(json.dumps(status, indent=2))
        return 0 if status["available"] else 2
    if not status["available"]:
        write_json(
            args.output / "report.json", {"schema": 1, "status": "runtime_unavailable", **status}
        )
        print(
            f"External solver unavailable: {status['reason']}\n"
            "Install in an ordinary Python environment: python -m pip install -e '.[external]'",
            file=sys.stderr,
        )
        return 2
    try:
        report = run(
            args.request,
            args.output,
            maxh=tuple(args.maxh),
            rim_segments=tuple(args.rim_segments),
            counts=tuple(args.mode_counts),
            order=args.order,
            bonus_intorder=args.bonus_intorder,
            geometry_order=args.geometry_order,
        )
    except (ImportError, OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        write_json(
            args.output / "report.json",
            {
                "schema": 1,
                "status": "execution_failed",
                "solver_result_available": False,
                "reason": str(error),
            },
        )
        print(f"External study failed: {error}", file=sys.stderr)
        return 2
    print(f"External dry-basin validation: {report['status']}; {args.output / 'report.json'}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
