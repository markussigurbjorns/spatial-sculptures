"""Verify the numerical plate, then report dry-basin mesh/quadrature refinement."""

import argparse
import hashlib
import importlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def validate_plate() -> dict:
    """Independent analytical frequencies/shapes versus assembled spline K/M."""
    import numpy as np

    from spatial_sculptures.simulation.plates import RectangularPlate
    from spatial_sculptures.simulation.structures import (
        GraphSurface,
        Material,
        assemble_shell,
        quadrature,
        solve_modes,
    )

    plate = RectangularPlate(1.44, 1.16, 0.005, 193e9, 8030, 0.30)
    reference = sorted(
        (plate.mode(m, n, 0.005).frequency_hz, m, n) for m in range(1, 8) for n in range(1, 8)
    )[:6]
    surface = GraphSurface(0.72, 0.58, domain="rectangle")
    x, y, measures = quadrature(surface, 12, 12, 5)
    rows = []
    for count in (2, 4, 6, 8):
        system = assemble_shell(
            surface, Material(), 0.005, elements=(count, count), simply_supported_plate=True
        )
        frequencies, coefficients, diagnostics = solve_modes(system, 6)
        shapes = system.space.evaluate(x, y)[0] @ coefficients
        macs = []
        for index, (_, m, n) in enumerate(reference):
            analytical = np.sin(m * np.pi * (x / plate.length_x + 0.5)) * np.sin(
                n * np.pi * (y / plate.length_y + 0.5)
            )
            actual = shapes[:, index]
            macs.append(
                float(
                    (measures @ (analytical * actual)) ** 2
                    / ((measures @ analytical**2) * (measures @ actual**2))
                )
            )
        rows.append(
            {
                "elements_per_axis": count,
                "frequencies_hz": frequencies.tolist(),
                "relative_frequency_errors": (
                    frequencies / np.array([v[0] for v in reference]) - 1
                ).tolist(),
                "shape_mass_weighted_MAC": macs,
                "diagnostics": diagnostics,
            }
        )
    passed = (
        max(abs(v) for v in rows[-1]["relative_frequency_errors"]) < 0.002
        and min(rows[-1]["shape_mass_weighted_MAC"]) > 0.999
    )
    return {
        "passed": passed,
        "reference_indices": [[m, n] for _, m, n in reference],
        "reference_frequencies_hz": [f for f, _, _ in reference],
        "meshes": rows,
        "criterion": "8x8 cells: first six frequencies within 0.2%; MAC > 0.999",
    }


def basin_refinement(config) -> dict:
    """Observed refinement differences, not an independent basin accuracy certificate."""
    import numpy as np

    from spatial_sculptures.simulation.structures import AttachedMass, assemble_shell, solve_modes

    rows = []
    for count in (4, 6, 8, 10):
        system = assemble_shell(
            config.surface,
            config.material,
            config.thickness,
            elements=(count, count),
            gauss_order=config.gauss_order,
            supports=config.supports,
            attached_masses=tuple(
                AttachedMass(e.patch, e.added_mass_kg) for e in config.exciters if e.added_mass_kg
            ),
        )
        f, _, diagnostics = solve_modes(system, config.mode_count)
        rows.append(
            {"elements_per_axis": count, "frequencies_hz": f.tolist(), "diagnostics": diagnostics}
        )
    last = np.array(rows[-1]["frequencies_hz"])
    for row in rows:
        row["relative_difference_from_10x10"] = (
            np.array(row["frequencies_hz"]) / last - 1
        ).tolist()
    quadrature_rows = []
    for order in (4, 5, 7):
        system = assemble_shell(
            config.surface,
            config.material,
            config.thickness,
            elements=config.elements,
            gauss_order=order,
            supports=config.supports,
            attached_masses=tuple(
                AttachedMass(e.patch, e.added_mass_kg) for e in config.exciters if e.added_mass_kg
            ),
        )
        f, _, d = solve_modes(system, config.mode_count)
        quadrature_rows.append(
            {"gauss_order": order, "frequencies_hz": f.tolist(), "diagnostics": d}
        )
    return {
        "meshes": rows,
        "quadrature": quadrature_rows,
        "interpretation": (
            "Ordered frequency differences; near-degenerate modes can rotate/swap. "
            "No specimen validation, broadband convergence, or universal locking claim."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/fem/001_resonant_surface/verification.json"
    )
    parser.add_argument("--plate-only", action="store_true")
    args = parser.parse_args()
    try:
        report = {
            "plate": validate_plate(),
            "source_sha256": {
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in (
                    "src/spatial_sculptures/simulation/splines.py",
                    "src/spatial_sculptures/simulation/structures.py",
                    "src/spatial_sculptures/simulation/plates.py",
                    "tools/validate_structure.py",
                )
            },
        }
        if not args.plate_only:
            config = importlib.import_module(
                "prototypes.001_resonant_surface.dry.config"
            ).load_config()
            report["dry_basin"] = basin_refinement(config)
            report["dry_basin"]["parameters"] = asdict(config)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False))
    except ImportError:
        parser.error(
            "Numerical verification requires NumPy: python -m pip install -e '.[numerical]'"
        )
    print(
        f"Plate verification {'passed' if report['plate']['passed'] else 'FAILED'}; "
        f"data: {args.output.resolve()}"
    )
    return 0 if report["plate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
