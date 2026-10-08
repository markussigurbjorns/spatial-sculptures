"""Recheck dry contact response while varying supports and mounting widths explicitly."""

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def profile(report, report_path, required):
    from tools.validate_dry_basin import select_profile

    parameters, verification = select_profile(report, required)
    return {
        "parameters": parameters,
        "verification": {
            **verification,
            "report_path": str(report_path.resolve().relative_to(ROOT))
            if report_path.resolve().is_relative_to(ROOT)
            else str(report_path.resolve()),
            "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        },
    }


def run(baseline_path, output, names):
    """Give every changed configuration its own convergence evidence."""
    import numpy as np

    from spatial_sculptures.simulation.convergence import (
        relative_response_error,
        resonance_grid,
        trapezoid_weights,
    )
    from tools.validate_dry_basin import check_provenance, run_validation, transfer, write_summary

    baseline = json.loads(baseline_path.read_text())
    check_provenance(baseline)
    if max(baseline["evaluated_bands_hz"]) != 200:
        raise ValueError("This explicit sensitivity study requires the checked 200 Hz baseline")
    config_module = importlib.import_module("prototypes.001_resonant_surface.dry.config")
    variations = importlib.import_module("prototypes.001_resonant_surface.dry.sensitivity")
    model = importlib.import_module("prototypes.001_resonant_surface.dry.model")
    if not names or len(set(names)) != len(names) or any(n not in variations.CASES for n in names):
        raise ValueError(f"Choose distinct cases from {list(variations.CASES)}")
    base = config_module.from_dict(baseline["parameters"])
    required = max(baseline["evaluated_bands_hz"])
    baseline_profile = profile(baseline, baseline_path, required)
    base.elements = tuple(baseline_profile["parameters"]["elements"])
    base.mode_count = max(c["count"] for c in baseline["meshes"][0]["retained_counts"])
    base_modes = model.get_modes(base, ROOT / "data/fem/001_resonant_surface")[0]
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for name in names:
        print(f"Sensitivity case: {name}", flush=True)
        config = variations.configure(config_module.from_dict(baseline["parameters"]), name)
        report = run_validation(
            config,
            meshes=(18, 22, 26),
            degrees=(32, 36),
            counts=(32, 64, 128, 384, 512),
            bands=(5.0, 10.0, 20.0, 40.0, 80.0, 100.0, 150.0, 200.0),
            signal_rate=48000,
            interval_edges=(20.0, 40.0, 80.0, 160.0, 200.0),
        )
        directory = output / name
        directory.mkdir(parents=True, exist_ok=True)
        report_path = directory / "convergence.json"
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False))
        write_summary(report, directory / "convergence.md")
        try:
            selected = profile(report, report_path, required)
        except ValueError:
            selected = None
        if selected:
            (directory / "profile.json").write_text(json.dumps(selected, indent=2))
            config = config_module.from_dict(selected["parameters"])
        else:
            (directory / "profile.json").unlink(missing_ok=True)
            config.elements = base.elements
        # Sensitivity is a change of physical assumptions, not an accuracy error.
        # Use equally sized full banks and a grid containing both sets of resonances.
        config.mode_count = base.mode_count
        modes = model.get_modes(config, ROOT / "data/fem/001_resonant_surface")[0]
        frequencies = np.unique(
            np.r_[
                20.0,
                resonance_grid(
                    [base_modes.frequencies, modes.frequencies],
                    config.damping_ratio,
                    required,
                    0.05,
                ),
            ]
        )
        frequencies = frequencies[frequencies >= 20]
        original = transfer(base_modes, base, frequencies, base.mode_count)
        changed = transfer(modes, config, frequencies, config.mode_count)
        differences = relative_response_error(original, changed, trapezoid_weights(frequencies))
        records.append(
            {
                "case": name,
                "change": list(variations.CASES[name]),
                "first_frequency_hz": float(modes.frequencies[0]),
                "first_twelve_frequencies_hz": modes.frequencies[:12].tolist(),
                "comparison_interval_hz": [20, required],
                "physical_response_change_per_path_relative_L2": differences.tolist(),
                "maximum_physical_response_change_relative_L2": float(differences.max()),
                "convergence_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                "passing_profile": selected["verification"] if selected else None,
            }
        )
    summary = {
        "schema": 1,
        "baseline_report_sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
        "baseline_first_frequency_hz": float(base_modes.frequencies[0]),
        "scope": "One-factor provisional sensitivity; no measured calibration.",
        "records": records,
        "source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "tools/study_dry_sensitivity.py",
                "prototypes/001_resonant_surface/dry/sensitivity.py",
            )
        },
    }
    (output / "comparison.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    lines = [
        "# Dry support/mount sensitivity",
        "",
        "Provisional assumptions changed, with independent convergence checks per case.",
        "Changes use raw SI mobility over 20–200 Hz, all six paths, and full banks.",
        "These changes are not numerical errors or measured uncertainty estimates.",
        "",
        "| Case | First frequency (Hz) | Largest response change (%) | Passing 200 Hz bank |",
        "| --- | ---: | ---: | --- |",
    ]
    for record in records:
        selected = record["passing_profile"]
        bank = (
            f"{selected['elements_per_axis']} × {selected['elements_per_axis']}, "
            f"{selected['mode_count']} modes"
            if selected
            else "none"
        )
        lines.append(
            f"| [{record['case']}]({record['case']}/convergence.md) "
            f"| {record['first_frequency_hz']:.3f} "
            f"| {100 * record['maximum_physical_response_change_relative_L2']:.2f} | {bank} |"
        )
    lines += [
        "",
        "Support cases scale all total X/Y/Z springs together. Mount cases change patch "
        "width while retaining each 120 g rigid housing and total applied force. "
        "Glue compliance and electrical actuation remain absent.",
        "",
    ]
    (output / "comparison.md").write_text("\n".join(lines))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-report",
        type=Path,
        default=ROOT / "docs/research/dry_basin/contact_bandwidth.json",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/fem/001_resonant_surface/sensitivity"
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        default=["support_half", "support_double", "mount_narrow", "mount_wide"],
    )
    args = parser.parse_args()
    try:
        run(args.baseline_report, args.output, args.cases)
    except (ValueError, OSError, TypeError, KeyError) as error:
        parser.error(str(error))
    except ImportError as error:
        parser.error(f"Numerical dependency unavailable ({error}); install .[numerical]")
    print(f"Sensitivity comparison: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
