"""Independently check curved modes and measure mesh/modal contact-signal convergence."""

import argparse
import hashlib
import importlib
import json
import sys
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

# Research tolerances, declared separately from observed results; not specimen accuracy.
POLICY = {
    "frequency_relative": 0.01,
    "minimum_subspace_MAC": 0.99,
    "reference_frequency_relative": 0.0025,
    "reference_minimum_subspace_MAC": 0.995,
    "reference_transfer_relative_L2": 0.05,
    "reference_truncation_relative_L2": 0.05,
    "mesh_transfer_relative_L2": 0.05,
    "truncation_transfer_relative_L2": 0.05,
    "independent_transfer_relative_L2": 0.10,
    "cluster_relative_gap": 0.002,
}
DEFAULT_BANDS = (5.0, 10.0, 15.0, 20.0, 30.0, 40.0, 60.0, 80.0, 100.0, 150.0, 200.0)


def transfer(modes, config, sample_hz, count):
    from spatial_sculptures.simulation.convergence import contact_transfer

    surface_points = [p for p in config.pickups]
    import numpy as np

    pickups = modes.weights(*np.asarray(surface_points).T)[:, 2, :count]
    if hasattr(modes, "masses"):
        forces = np.asarray(
            [modes.patch_weights(e.patch, e.direction)[:count] for e in config.exciters]
        )
        masses = modes.masses[:count]
    else:
        forces = np.asarray(
            [modes.patch_weights(asdict(e.patch), e.direction)[:count] for e in config.exciters]
        )
        masses = np.ones(count)  # Reference eigenvectors have unit modal mass.
    return contact_transfer(
        modes.frequencies[:count], masses, pickups, forces, config.damping_ratio, sample_hz
    )


def bands_for(comparison, cutoff, policy=POLICY, *, reference=False):
    groups = [g for g in comparison["groups"] if min(g["reference_frequencies_hz"]) <= cutoff]
    if not groups:
        return False
    frequency = policy["reference_frequency_relative" if reference else "frequency_relative"]
    mac = policy["reference_minimum_subspace_MAC" if reference else "minimum_subspace_MAC"]
    return all(
        g["maximum_relative_frequency_difference"] <= frequency and g["minimum_subspace_MAC"] >= mac
        for g in groups
    )


def add_frequencies(comparison, frequencies):
    for group in comparison["groups"]:
        group["reference_frequencies_hz"] = [
            float(frequencies[i]) for i in group["reference_indices"]
        ]
    return comparison


def error_record(reference, candidate):
    import numpy as np

    from spatial_sculptures.simulation.convergence import relative_response_error

    values = relative_response_error(reference, candidate)
    return {
        "per_path_relative_L2": [
            [float(v) if np.isfinite(v) else None for v in row] for row in values
        ],
        "maximum_relative_L2": float(values.max()) if np.all(np.isfinite(values)) else None,
    }


def within(record, tolerance):
    error = record["maximum_relative_L2"]
    return error is not None and error <= tolerance


def run_validation(
    config,
    *,
    meshes=(8, 10, 12, 14),
    degrees=(12, 16, 18, 20),
    counts=(16, 32, 48, 64),
    bands=DEFAULT_BANDS,
    sample_step_hz=0.05,
    signal_duration=2.0,
    signal_rate=4096,
):
    """Independent physical-unit evidence. Failed accuracy criteria remain recorded failures."""
    import numpy as np

    from spatial_sculptures.simulation.convergence import compare_modes
    from spatial_sculptures.simulation.modal import Mode
    from spatial_sculptures.simulation.mode_bank import ModalResponse

    model = importlib.import_module("prototypes.001_resonant_surface.dry.model")
    reference = importlib.import_module("studies.plates.002_curved_shell_reference.ritz")
    model.validate_config(config)
    if config.damping_ratio <= 0:
        raise ValueError("Transfer convergence needs positive damping")
    if (
        len(meshes) < 2
        or len(degrees) < 2
        or len(counts) < 2
        or tuple(sorted(set(meshes))) != tuple(meshes)
        or tuple(sorted(set(degrees))) != tuple(degrees)
        or tuple(sorted(set(counts))) != tuple(counts)
        or any(v < 1 for v in meshes + counts)
        or any(not 3 <= v <= 20 for v in degrees)
    ):
        raise ValueError("Increasing meshes/degrees/counts, with at least two of each, required")
    if (
        not bands
        or tuple(sorted(set(bands))) != tuple(bands)
        or min(bands) <= 0
        or not np.isfinite(sample_step_hz)
        or sample_step_hz <= 0
        or sample_step_hz > min(bands) / 10
    ):
        raise ValueError(
            "Increasing positive bands and sufficiently fine frequency sampling required"
        )
    parameters = asdict(config)
    maximum_modes = max(counts)
    sample_hz = np.arange(1, int(np.ceil(max(bands) / sample_step_hz)) + 1) * sample_step_hz
    references, reference_rows = [], []
    for degree in degrees:
        print(f"Independent Ritz reference: degree {degree}", flush=True)
        modes = reference.solve(parameters, degree, maximum_modes)
        references.append(modes)
        reference_rows.append(
            {
                "degree": degree,
                "frequencies_hz": modes.frequencies.tolist(),
                "diagnostics": modes.diagnostics,
            }
        )
    finest = references[-1]
    # Comparison grid is independent polar quadrature, with vector and physical area weights.
    x, y, w = reference.disk_quadrature(parameters["surface"], 20, 80)
    _, zx, zy, *_ = reference.geometry(parameters["surface"], x, y)
    w *= np.sqrt(1 + zx * zx + zy * zy)
    reference_shapes = finest.weights(x, y)
    for modes, row in zip(references[:-1], reference_rows[:-1], strict=True):
        row["comparison_to_finest"] = add_frequencies(
            compare_modes(
                finest.frequencies,
                reference_shapes,
                modes.frequencies,
                modes.weights(x, y),
                w,
                cluster_gap=POLICY["cluster_relative_gap"],
            ),
            finest.frequencies,
        )
    reference_comparison = reference_rows[-2]["comparison_to_finest"]
    reference_transfer = transfer(finest, config, sample_hz, maximum_modes)
    preceding_transfer = transfer(references[-2], config, sample_hz, maximum_modes)
    reference_truncated = transfer(finest, config, sample_hz, counts[-2])
    rows, candidates = [], []
    for cells in meshes:
        print(f"Production spline mesh: {cells} × {cells}, {maximum_modes} modes", flush=True)
        candidate_config = deepcopy(config)
        candidate_config.elements, candidate_config.mode_count = (cells, cells), maximum_modes
        modes, path, reused = model.get_modes(
            candidate_config, ROOT / "data/fem/001_resonant_surface"
        )
        candidates.append(modes)
        comparisons = add_frequencies(
            compare_modes(
                finest.frequencies,
                reference_shapes,
                modes.frequencies,
                modes.weights(x, y),
                w,
                cluster_gap=POLICY["cluster_relative_gap"],
            ),
            finest.frequencies,
        )
        rows.append(
            {
                "elements_per_axis": cells,
                "frequencies_hz": modes.frequencies.tolist(),
                "diagnostics": modes.metadata["diagnostics"],
                "cache_path": str(path.relative_to(ROOT)),
                "cache_key": modes.metadata["cache_key"],
                "cache_reused": reused,
                "independent_mode_comparison": comparisons,
                "retained_counts": [],
            }
        )
    spline_transfers = [transfer(m, config, sample_hz, maximum_modes) for m in candidates]
    fine_transfer, preceding_mesh = spline_transfers[-1], spline_transfers[-2]
    for index, (modes, row) in enumerate(zip(candidates, rows, strict=True)):
        for count in counts:
            response = transfer(modes, config, sample_hz, count)
            checks = []
            for band in bands:
                selected = sample_hz <= band + 1e-10
                ref_diff = error_record(
                    reference_transfer[:, :, selected], preceding_transfer[:, :, selected]
                )
                ref_trunc = error_record(
                    reference_transfer[:, :, selected], reference_truncated[:, :, selected]
                )
                mesh_difference = error_record(
                    fine_transfer[:, :, selected], preceding_mesh[:, :, selected]
                )
                truncation = error_record(
                    spline_transfers[index][:, :, selected], response[:, :, selected]
                )
                independent = error_record(
                    reference_transfer[:, :, selected], response[:, :, selected]
                )
                # A retained cutoff must include all reference modes in the proposed band.
                # Near-degenerate groups crossing the cutoff are not silently certified.
                coverage = (
                    band <= modes.frequencies[count - 1]
                    and band <= finest.frequencies[count - 1]
                    and band <= min(candidates[-1].frequencies[-1], finest.frequencies[-1])
                    and all(
                        max(g["candidate_indices"]) < count and max(g["reference_indices"]) < count
                        for g in row["independent_mode_comparison"]["groups"]
                        if min(g["reference_frequencies_hz"]) <= band
                    )
                )
                modal_pass = coverage and bands_for(row["independent_mode_comparison"], band)
                reference_pass = (
                    bands_for(reference_comparison, band, reference=True)
                    and within(ref_diff, POLICY["reference_transfer_relative_L2"])
                    and within(ref_trunc, POLICY["reference_truncation_relative_L2"])
                )
                passed = (
                    modal_pass
                    and reference_pass
                    and within(mesh_difference, POLICY["mesh_transfer_relative_L2"])
                    and within(truncation, POLICY["truncation_transfer_relative_L2"])
                    and within(independent, POLICY["independent_transfer_relative_L2"])
                )
                checks.append(
                    {
                        "band_hz": band,
                        "passed": bool(passed and all(b["passed"] for b in checks)),
                        "individual_band_checks_passed": bool(passed),
                        "modal_checks_passed": bool(modal_pass),
                        "reference_checks_passed": bool(reference_pass),
                        "mode_coverage": bool(coverage),
                        "reference_refinement": ref_diff,
                        "reference_truncation": ref_trunc,
                        "finest_mesh_refinement": mesh_difference,
                        "modal_truncation": truncation,
                        "independent_response": independent,
                    }
                )
            row["retained_counts"].append(
                {
                    "count": count,
                    "bands": checks,
                    "supported_sampled_band_hz": max(
                        [b["band_hz"] for b in checks if b["passed"]], default=None
                    ),
                }
            )
            verified_frequency = None
            for group in row["independent_mode_comparison"]["groups"]:
                edge = max(group["reference_frequencies_hz"])
                if (
                    max(group["candidate_indices"]) >= count
                    or max(group["reference_indices"]) >= count
                    or not bands_for(row["independent_mode_comparison"], edge)
                    or not bands_for(reference_comparison, edge, reference=True)
                ):
                    break
                verified_frequency = edge
            row["retained_counts"][-1]["frequency_only_verified_prefix_hz"] = verified_frequency
    # Unfiltered ring-down signal test: all three unit impulses, every contact,
    # exact common times and masses. No WAV normalization or sign alignment.
    if signal_duration <= 0 or signal_rate <= 2 * max(
        finest.frequencies[-1], candidates[-1].frequencies[-1]
    ):
        raise ValueError("Positive signal duration and sample rate above modal Nyquist required")
    times = np.arange(round(signal_duration * signal_rate)) / signal_rate

    def impulse_signals(modes, count):
        pickups = modes.weights(*np.asarray(config.pickups).T)[:, 2, :count]
        is_spline = hasattr(modes, "masses")
        masses = modes.masses[:count] if is_spline else np.ones(count)
        bank = tuple(
            Mode(str(i), float(f), float(mass), config.damping_ratio)
            for i, (f, mass) in enumerate(zip(modes.frequencies[:count], masses, strict=True))
        )
        signals = []
        for exciter in config.exciters:
            force = modes.patch_weights(
                exciter.patch if is_spline else asdict(exciter.patch), exciter.direction
            )[:count]
            response = ModalResponse(bank, [[(0, float(v))] for v in force], [[] for _ in bank])
            signals.append(pickups @ response.trace(times, use_numpy=True)[1])
        return np.asarray(signals).transpose(1, 0, 2)

    reference_signal = impulse_signals(finest, maximum_modes)
    for modes, row in zip(candidates, rows, strict=True):
        full_signal = impulse_signals(modes, maximum_modes)
        for case in row["retained_counts"]:
            signal = impulse_signals(modes, case["count"])
            case["unfiltered_impulse"] = {
                "vs_independent_reference": error_record(reference_signal, signal),
                "vs_full_modal_bank": error_record(full_signal, signal),
                "pickup_peak_m_per_s_per_ns": np.max(np.abs(signal), axis=-1).tolist(),
            }
    default_row = next(
        (r for r in rows if tuple(config.elements) == (r["elements_per_axis"],) * 2), None
    )
    default_case = (
        next((r for r in default_row["retained_counts"] if r["count"] == config.mode_count), None)
        if default_row
        else None
    )
    sources = (
        "src/spatial_sculptures/simulation/convergence.py",
        "src/spatial_sculptures/simulation/structures.py",
        "src/spatial_sculptures/simulation/splines.py",
        "src/spatial_sculptures/simulation/mode_cache.py",
        "src/spatial_sculptures/simulation/mode_bank.py",
        "src/spatial_sculptures/simulation/modal.py",
        "prototypes/001_resonant_surface/dry/model.py",
        "studies/plates/002_curved_shell_reference/ritz.py",
        "tools/validate_dry_basin.py",
    )
    return {
        "schema": 1,
        "scope": "numerical cross-verification of one dry linear shell and configured contacts",
        "parameters": parameters,
        "policy": POLICY,
        "reference": reference_rows,
        "meshes": rows,
        "sampling": {
            "step_hz": sample_step_hz,
            "maximum_hz": max(bands),
            "impulse_duration_s": signal_duration,
            "impulse_sample_rate": signal_rate,
            "unit_impulse_ns": 1.0,
            "normalization": "none; raw SI velocity per N s",
        },
        "default_supported_sampled_band_hz": default_case["supported_sampled_band_hz"]
        if default_case
        else None,
        "evaluated_bands_hz": list(bands),
        "limitations": [
            "Shared Kirchhoff-Love physics; independently assembled numerical reference.",
            "Sampled complex L2 tolerances are not pointwise bounds or broadband certification.",
            "Transfer band assumes band-limited input/output; default WAV is unfiltered.",
            "Finite reference/modal banks; no measured vessel, fluid or acoustic radiation.",
        ],
        "software": {"python": sys.version.split()[0], "numpy": np.__version__},
        "source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources
        },
    }


def write_summary(report, path: Path):
    """Human-readable result with separate frequency and contact-response conclusions."""
    lines = [
        "# Dry-basin numerical convergence",
        "",
        "Independently assembled spline and disk-polynomial Ritz models share shell assumptions.",
        "This is numerical cross-verification, not specimen or acoustic validation.",
        "",
        "Default supported sampled transfer band: "
        f"**{report['default_supported_sampled_band_hz']} Hz**.",
        "All lower tested cutoffs must pass. Band support does not certify the unfiltered WAV.",
        "",
        "| Cells/axis | Modes | Frequency-only prefix (Hz) | Sampled transfer band (Hz) |"
        " Unfiltered impulse error vs reference (%) |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["meshes"]:
        for case in row["retained_counts"]:
            frequency = case["frequency_only_verified_prefix_hz"]
            transfer_band = case["supported_sampled_band_hz"]
            error = case["unfiltered_impulse"]["vs_independent_reference"]["maximum_relative_L2"]
            frequency_text = f"{frequency:.3f}" if frequency is not None else "none"
            error_text = f"{100 * error:.2f}" if error is not None else "undefined"
            band_text = str(transfer_band) if transfer_band is not None else "none"
            lines.append(
                f"| {row['elements_per_axis']} | {case['count']} | {frequency_text} "
                f"| {band_text} | {error_text} |"
            )
    lines += [
        "",
        "Frequency checks: ≤1% difference and subspace MAC ≥0.99.",
        "Reference checks: ≤0.25% frequency difference and subspace MAC ≥0.995.",
        "Complex contact transfer: ≤10% relative L2 per pickup/exciter path; "
        "reference, mesh and modal refinement each ≤5%.",
        "Signals retain SI units and common time; no listening normalization or phase alignment.",
        "See JSON for individual path errors, failed checks, configurations and source provenance.",
        "",
        *report["limitations"],
        "",
    ]
    path.write_text("\n".join(lines))


def required_band_passes(report, required):
    """A failed or unexamined configured band cannot produce a successful accuracy gate."""
    supported = report["default_supported_sampled_band_hz"]
    return (
        required in report["evaluated_bands_hz"] and supported is not None and supported >= required
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--config", type=Path)
    source.add_argument(
        "--check-report",
        type=Path,
        help="Check provenance and gate a saved report without solving again",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/fem/001_resonant_surface/convergence.json"
    )
    parser.add_argument("--meshes", type=int, nargs="+", default=[8, 10, 12, 14])
    parser.add_argument("--degrees", type=int, nargs="+", default=[12, 16, 18, 20])
    parser.add_argument("--counts", type=int, nargs="+", default=[16, 32, 48, 64])
    parser.add_argument("--bands", type=float, nargs="+", default=list(DEFAULT_BANDS))
    parser.add_argument("--step-hz", type=float, default=0.05)
    parser.add_argument(
        "--require-band",
        type=float,
        help="Return status 1 unless the configured default mesh/count supports this sampled band",
    )
    args = parser.parse_args()
    if (
        not args.check_report
        and args.require_band is not None
        and (not 0 < args.require_band <= max(args.bands) or args.require_band not in args.bands)
    ):
        parser.error("--require-band must be one of the requested positive sampled band cutoffs")
    try:
        if args.check_report:
            report = json.loads(args.check_report.read_text())
            if report.get("schema") != 1:
                parser.error("Unsupported convergence report schema")
            for name, digest in report["source_sha256"].items():
                if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
                    parser.error(f"Stale source {name}; regenerate the report")
            print(
                f"Recorded sampled transfer band: {report['default_supported_sampled_band_hz']} Hz"
            )
            return (
                0
                if args.require_band is None or required_band_passes(report, args.require_band)
                else 1
            )
        config = importlib.import_module("prototypes.001_resonant_surface.dry.config").load_config(
            args.config
        )
        report = run_validation(
            config,
            meshes=tuple(args.meshes),
            degrees=tuple(args.degrees),
            counts=tuple(args.counts),
            bands=tuple(args.bands),
            sample_step_hz=args.step_hz,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False))
        write_summary(report, args.output.with_suffix(".md"))
    except (ValueError, OSError, TypeError, KeyError) as error:
        parser.error(str(error))
    except ImportError:
        parser.error("Numerical validation requires NumPy: python -m pip install -e '.[numerical]'")
    supported = report["default_supported_sampled_band_hz"]
    print(f"Default supported sampled transfer band: {supported} Hz; report: {args.output}")
    if args.require_band is not None and not required_band_passes(report, args.require_band):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
