"""Analytical pressure-release fluid cell and independent flat-plate checks.

The reference's TOP AND VERTICAL SIDES have zero perturbation potential; the
bottom has a prescribed sine-product velocity. These are not rigid tank sides.
Separating Laplace's equation gives ma/area = rho*tanh(k*h)/k. The column model
keeps its shallow limit rho*h. Approximation error is reported, never fitted away.
"""

from math import pi, sqrt

import numpy as np

from spatial_sculptures.simulation.fluid_loading import (
    ColumnWater,
    pressure_release_mass_per_area,
    with_column_water,
)
from spatial_sculptures.simulation.plates import RectangularPlate
from spatial_sculptures.simulation.structures import (
    GraphSurface,
    Material,
    assemble_shell,
    solve_modes,
)


def plate_reference():
    plate = RectangularPlate(1.44, 1.16, 0.005, 193e9, 8030.0, 0.3)
    indices = sorted(
        (plate.mode(m, n, 0).frequency_hz, m, n) for m in range(1, 8) for n in range(1, 8)
    )[:6]
    return plate, indices


def analytical_cases(depths=(0.0, 0.001, 0.005, 0.01, 0.02, 0.065)):
    """Compare the column approximation to exact finite-depth modal loading."""
    plate, indices = plate_reference()
    rows = []
    for depth in depths:
        water = ColumnWater(depth)
        modes = []
        for dry_frequency, m, n in indices:
            k = pi * sqrt((m / plate.length_x) ** 2 + (n / plate.length_y) ** 2)
            exact_mass = pressure_release_mass_per_area(k, water)
            column_mass = water.density_kg_m3 * depth
            wall_mass = plate.density * plate.thickness
            exact_f = dry_frequency / sqrt(1 + exact_mass / wall_mass)
            column_f = dry_frequency / sqrt(1 + column_mass / wall_mass)
            modes.append(
                {
                    "indices": [m, n],
                    "kh": k * depth,
                    "dry_frequency_hz": dry_frequency,
                    "finite_depth_frequency_hz": exact_f,
                    "column_frequency_hz": column_f,
                    "relative_frequency_approximation_error": abs(column_f / exact_f - 1),
                    "finite_depth_added_mass_kg_m2": exact_mass,
                    "column_added_mass_kg_m2": column_mass,
                }
            )
        rows.append({"depth_m": depth, "modes": modes})
    return rows


def check_plate_assembly():
    """Verify assembled loaded plate frequencies against the independent column formula."""
    plate, indices = plate_reference()
    system = assemble_shell(
        GraphSurface(plate.length_x / 2, plate.length_y / 2, domain="rectangle"),
        Material(),
        plate.thickness,
        elements=(8, 8),
        simply_supported_plate=True,
    )
    rows = []
    for depth in (0.0, 0.005, 0.02, 0.065):
        water = ColumnWater(depth)
        wet, loading = with_column_water(system, water)
        frequencies, _, diagnostics = solve_modes(wet, 6)
        expected = np.asarray([row[0] for row in indices]) / sqrt(
            1 + water.density_kg_m3 * depth / (plate.density * plate.thickness)
        )
        error = float(np.max(np.abs(frequencies / expected - 1)))
        rows.append(
            {
                "depth_m": depth,
                "expected_frequencies_hz": expected.tolist(),
                "assembled_frequencies_hz": frequencies.tolist(),
                "maximum_relative_frequency_error": error,
                "volume_m3": loading.volume_m3,
                "diagnostics": diagnostics,
                "passed": error < 0.002,
            }
        )
    return {"passed": all(r["passed"] for r in rows), "tolerance": 0.002, "cases": rows}


def check_potential_cell(mesh_sizes=(0.35, 0.25, 0.18), depth=0.02):
    """Independent optional NGSolve 3D Laplace solve versus six analytic added masses.

    Mesh a unit cube then map it affinely to the thin reference cell. This avoids
    requiring an isotropic tetrahedral mesh at the water thickness scale.
    """
    import ngsolve as ng
    from netgen.csg import unit_cube

    plate, indices = plate_reference()
    water = ColumnWater(depth)
    if depth == 0:
        raise ValueError("The 3D reference requires positive depth")
    rows = []
    for maxh in mesh_sizes:
        mesh = ng.Mesh(unit_cube.GenerateMesh(maxh=maxh))
        deformation = ng.GridFunction(ng.VectorH1(mesh, order=1))
        deformation.Set(
            ng.CF(((plate.length_x - 1) * ng.x, (plate.length_y - 1) * ng.y, (depth - 1) * ng.z))
        )
        mesh.SetDeformation(deformation)
        space = ng.H1(mesh, order=3, dirichlet="left|right|front|back|top")
        u, v = space.TnT()
        stiffness = ng.BilinearForm(space, symmetric=True)
        stiffness += ng.grad(u) * ng.grad(v) * ng.dx
        stiffness.Assemble()
        inverse = stiffness.mat.Inverse(space.FreeDofs(), inverse="sparsecholesky")
        computed, expected = [], []
        for _, m, n in indices:
            shape = ng.sin(m * pi * ng.x / plate.length_x) * ng.sin(n * pi * ng.y / plate.length_y)
            rhs = ng.LinearForm(space)
            rhs += -shape * v * ng.ds("bottom", bonus_intorder=8)
            rhs.Assemble()
            potential = ng.GridFunction(space)
            potential.vec.data = inverse * rhs.vec
            computed.append(
                float(
                    -water.density_kg_m3
                    * ng.Integrate(
                        shape * potential,
                        mesh,
                        ng.BND,
                        definedon=mesh.Boundaries("bottom"),
                        order=10,
                    )
                )
            )
            k = pi * sqrt((m / plate.length_x) ** 2 + (n / plate.length_y) ** 2)
            expected.append(
                pressure_release_mass_per_area(k, water) * plate.length_x * plate.length_y / 4
            )
        error = float(np.max(np.abs(np.asarray(computed) / expected - 1)))
        rows.append(
            {
                "unit_cube_maxh": maxh,
                "dofs": space.ndof,
                "added_masses_kg": computed,
                "analytical_added_masses_kg": expected,
                "maximum_relative_added_mass_error": error,
            }
        )
    return {
        "passed": rows[-1]["maximum_relative_added_mass_error"] < 0.002,
        "tolerance": 0.002,
        "depth_m": depth,
        "ngsolve_version": ng.__version__,
        "boundary_conditions": "phi=0 on top and all four sides; prescribed bottom velocity",
        "meshes": rows,
    }
