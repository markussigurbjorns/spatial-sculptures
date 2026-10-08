"""Export dry-basin contact mobility and compare supplied solver/measurement data."""

import argparse
import csv
import hashlib
import importlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
UNITS = "(m/s)/N"
CONVENTION = "exp(+i*2*pi*f*t)"
COLUMNS = ("pickup", "exciter", "frequency_hz", "real_m_per_s_per_n", "imag_m_per_s_per_n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path, frequencies, values):
    """Write unnormalized complex velocity/force, with one-based physical path indices."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for pickup in range(values.shape[0]):
            for exciter in range(values.shape[1]):
                for frequency, value in zip(frequencies, values[pickup, exciter], strict=True):
                    writer.writerow((pickup + 1, exciter + 1, frequency, value.real, value.imag))


def read_csv(path, pickup_count, exciter_count):
    """Reject missing paths, duplicate/unsorted samples, nonfinite values and wrong units."""
    import numpy as np

    paths = {(p, e): [] for p in range(1, pickup_count + 1) for e in range(1, exciter_count + 1)}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError(f"CSV columns must be {COLUMNS}; SI mobility is required")
        for row in reader:
            key = int(row["pickup"]), int(row["exciter"])
            if key not in paths:
                raise ValueError("CSV contains an unknown pickup/exciter index")
            paths[key].append(
                (
                    float(row["frequency_hz"]),
                    complex(float(row[COLUMNS[3]]), float(row[COLUMNS[4]])),
                )
            )
    frequencies, result = None, []
    for samples in paths.values():
        if len(samples) < 2:
            raise ValueError("Every pickup/exciter path needs at least two frequency samples")
        f, values = np.array([s[0] for s in samples]), np.array([s[1] for s in samples])
        if (
            not np.all(np.isfinite(f))
            or not np.all(np.isfinite(values))
            or np.any(f < 0)
            or np.any(np.diff(f) <= 0)
        ):
            raise ValueError(
                "Finite, increasing nonnegative frequencies and complex values required"
            )
        if frequencies is not None and not np.array_equal(frequencies, f):
            raise ValueError("All paths must use the same frequency grid")
        frequencies = f
        result.append(values)
    return frequencies, np.array(result).reshape(pickup_count, exciter_count, -1)


def prepare(config_path, output, *, lower_hz=20.0, upper_hz=200.0, step_hz=0.05):
    """Save a solver-neutral request, predicted mobility, and an explicit source record."""
    import numpy as np

    from spatial_sculptures.simulation.convergence import resonance_grid
    from tools.run_dry_basin import verify_profile
    from tools.validate_dry_basin import transfer

    config_module = importlib.import_module("prototypes.001_resonant_surface.dry.config")
    model = importlib.import_module("prototypes.001_resonant_surface.dry.model")
    config = config_module.load_config(config_path)
    model.validate_config(config)
    verification = verify_profile(config, config_path)
    if (
        not np.isfinite(lower_hz)
        or not np.isfinite(upper_hz)
        or not 0 <= lower_hz < upper_hz
        or step_hz > (upper_hz - lower_hz) / 10
    ):
        raise ValueError("Increasing finite interval and sufficiently fine spacing required")
    if verification and upper_hz > verification["verified_sampled_transfer_band_hz"]:
        raise ValueError("Requested response exceeds this profile's checked band")
    modes, _, _ = model.get_modes(config, ROOT / "data/fem/001_resonant_surface")
    frequencies = resonance_grid([modes.frequencies], config.damping_ratio, upper_hz, step_hz)
    interval_edges = [v for v in (40.0, 80.0, 160.0) if lower_hz < v < upper_hz]
    frequencies = np.unique(
        np.r_[lower_hz, frequencies[frequencies >= lower_hz], interval_edges, upper_hz]
    )
    values = transfer(modes, config, frequencies, config.mode_count)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "model_mobility.csv"
    write_csv(csv_path, frequencies, values)
    request = {
        "schema": 1,
        "parameters": asdict(config),
        "units": UNITS,
        "harmonic_convention": CONVENTION,
        "frequency_interval_hz": [lower_hz, upper_hz],
        "frequency_sample_count": len(frequencies),
        "csv_columns": list(COLUMNS),
        "model_mobility_sha256": digest(csv_path),
        "model_cache_key": modes.metadata["cache_key"],
        "model_provenance": modes.metadata["source_sha256"],
        "profile_verification": verification,
        "assumptions": [
            "Dry linear Kirchhoff-Love graph shell; free rim; translational consistent mass.",
            "Each support is a spring on patch-mean displacement: K_patch=k*mean(N)*mean(N)^T.",
            "Attached housings add rigid patch-mean translational inertia in X/Y/Z.",
            "Force is one total newton along the exciter direction, area-weighted over its patch.",
            "Pickups measure point global-Z velocity; damping is a constant modal ratio.",
            "No water, prestress, rotary inertia, glue compliance or electrical actuator model.",
        ],
        "source_sha256": {
            name: digest(ROOT / name)
            for name in (
                "tools/check_dry_response.py",
                "tools/validate_dry_basin.py",
                "src/spatial_sculptures/simulation/convergence.py",
            )
        },
    }
    request_path = output / "request.json"
    request_path.write_text(json.dumps(request, indent=2, allow_nan=False))
    (output / "model_source.json").write_text(
        json.dumps(
            {
                "kind": "model_prediction",
                "source": "This repository's configured dry-basin model",
                "units": UNITS,
                "harmonic_convention": CONVENTION,
                "request_sha256": digest(request_path),
                "data_sha256": digest(csv_path),
                "notes": "Self-comparison tests the tool; it provides no independent validation.",
            },
            indent=2,
        )
    )
    return request_path


def compare(request_path, data_path, source_path, output, *, tolerance=0.10):
    """Compare all paths at requested frequencies, without gain or phase fitting."""
    import numpy as np

    from spatial_sculptures.simulation.convergence import relative_response_error, trapezoid_weights

    request = json.loads(request_path.read_text())
    source = json.loads(source_path.read_text())
    if request.get("schema") != 1:
        raise ValueError("Unsupported request schema")
    for name, expected in {**request["model_provenance"], **request["source_sha256"]}.items():
        # Solver archives use package-local names; other identities use repository paths.
        path = ROOT / name if "/" in name else ROOT / "src/spatial_sculptures/simulation" / name
        if digest(path) != expected:
            raise ValueError(f"Stale source {name}; prepare the response again")
    if (
        source.get("kind")
        not in ("external_solver", "measurement", "synthetic_test", "model_prediction")
        or not isinstance(source.get("source"), str)
        or not source["source"].strip()
        or source.get("units") != UNITS
        or source.get("harmonic_convention") != CONVENTION
        or source.get("request_sha256") != digest(request_path)
        or source.get("data_sha256") != digest(data_path)
    ):
        raise ValueError(
            "Source metadata must identify kind, origin, SI units, convention and file hashes"
        )
    if not np.isfinite(tolerance) or not 0 < tolerance < 1:
        raise ValueError("Agreement tolerance must lie between zero and one")
    model_path = request_path.parent / "model_mobility.csv"
    if digest(model_path) != request["model_mobility_sha256"]:
        raise ValueError("Prepared model mobility changed; prepare the response again")
    parameters = request["parameters"]
    pickups, exciters = len(parameters["pickups"]), len(parameters["exciters"])
    frequencies, predicted = read_csv(model_path, pickups, exciters)
    imported_frequencies, supplied = read_csv(data_path, pickups, exciters)
    if not np.array_equal(frequencies, imported_frequencies):
        raise ValueError(
            "Imported data must use the requested frequency grid; no interpolation is applied"
        )
    intervals = [request["frequency_interval_hz"]]
    edges = np.unique(
        [
            frequencies[0],
            *[v for v in (40, 80, 160) if frequencies[0] < v < frequencies[-1]],
            frequencies[-1],
        ]
    )
    intervals += [list(pair) for pair in zip(edges[:-1], edges[1:], strict=True)]
    records = []
    for low, high in intervals:
        mask = (frequencies >= low) & (frequencies <= high)
        errors = relative_response_error(
            supplied[..., mask], predicted[..., mask], trapezoid_weights(frequencies[mask])
        )
        maximum = float(errors.max()) if np.all(np.isfinite(errors)) else None
        records.append(
            {
                "interval_hz": [float(low), float(high)],
                "per_path_relative_L2": [
                    [float(v) if np.isfinite(v) else None for v in row] for row in errors
                ],
                "maximum_relative_L2": maximum,
                "passed": maximum is not None and maximum <= tolerance,
            }
        )
    passed = all(record["passed"] for record in records)
    report = {
        "schema": 1,
        "source": source,
        "request_sha256": digest(request_path),
        "parameters": parameters,
        "units": UNITS,
        "tolerance": tolerance,
        "frequency_sample_count": len(frequencies),
        "intervals": records,
        "sampled_agreement_passed": passed,
        "scope": "Sampled agreement only; provenance labels do not establish physical validity.",
        "limitations": [
            "No normalization, fitted phase, automatic fitting or independent solver execution.",
            "Unknown narrow resonances may need a denser common grid and repeated measurements.",
            "WAV/amplifier voltage is not calibrated velocity per applied newton.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("prepare", help="Export the physical comparison request")
    export.add_argument(
        "--config",
        type=Path,
        default=ROOT / "prototypes/001_resonant_surface/dry/profiles/contact_200hz.json",
    )
    export.add_argument(
        "--output", type=Path, default=ROOT / "data/fem/001_resonant_surface/external_check"
    )
    export.add_argument("--lower-hz", type=float, default=20.0)
    export.add_argument("--upper-hz", type=float, default=200.0)
    export.add_argument("--step-hz", type=float, default=0.05)
    check = commands.add_parser("compare", help="Compare independently supplied SI mobility")
    check.add_argument("request", type=Path)
    check.add_argument("data", type=Path)
    check.add_argument("--source", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    check.add_argument("--tolerance", type=float, default=0.10)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            path = prepare(
                args.config,
                args.output,
                lower_hz=args.lower_hz,
                upper_hz=args.upper_hz,
                step_hz=args.step_hz,
            )
            print(f"Comparison request: {path}")
            return 0
        report = compare(
            args.request, args.data, args.source, args.output, tolerance=args.tolerance
        )
        print(
            f"{report['source']['kind']}: sampled agreement "
            f"{report['sampled_agreement_passed']}; {args.output}"
        )
        return 0 if report["sampled_agreement_passed"] else 1
    except (ValueError, OSError, TypeError, KeyError) as error:
        parser.error(str(error))
    except ImportError as error:
        parser.error(f"Numerical dependency unavailable ({error}); install .[numerical]")


if __name__ == "__main__":
    raise SystemExit(main())
