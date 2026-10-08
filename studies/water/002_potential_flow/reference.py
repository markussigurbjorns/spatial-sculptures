"""Manufactured curved-volume fields and analytical rigid-sided fluid-cell checks."""

from math import pi, sqrt


def manufactured_bowl():
    """Check known harmonic potentials, nonlocal inertia and pressure in the actual bowl."""
    import numpy as np

    from spatial_sculptures.simulation.fluid_loading import ColumnWater
    from spatial_sculptures.simulation.fluid_potential import PotentialSettings, assemble_potential
    from spatial_sculptures.simulation.structures import GraphSurface

    surface = GraphSurface(0.72, 0.58, 0.12, 0.006, 0.72)
    fluid = assemble_potential(surface, ColumnWater(0.065), PotentialSettings(2, 0))
    x, y = fluid.x, fluid.y
    z, bx, by, *_ = surface.geometry(x, y)
    height = z - fluid.basis.level
    # Exact harmonic phi: (z-H), (z-H)*x, (z-H)*y, (z-H)*(x²-y²).
    flux = np.column_stack(
        (
            np.ones_like(x),
            x - height * bx,
            y - height * by,
            x**2 - y**2 - height * (2 * x * bx - 2 * y * by),
        )
    )
    coefficients, mass, diagnostics = fluid.solve_flux(flux)
    probes = np.array(
        [[-0.2, -0.04, fluid.basis.level - 0.02], [0.25, -0.10, fluid.basis.level - 0.02]]
    )
    px, py, pz = probes.T
    expected = (
        -fluid.water.density_kg_m3
        * (pz[:, None] - fluid.basis.level)
        * np.column_stack((np.ones_like(px), px, py, px**2 - py**2))
    )
    actual = fluid.observations(coefficients, probes)
    error = float(np.max(np.abs(actual - expected)))
    return {
        "passed": bool(error < 1e-8 and abs(mass[0, 0] / (1000 * fluid.volume_m3) - 1) < 1e-10),
        "maximum_absolute_pressure_weight_error": error,
        "volume_m3": fluid.volume_m3,
        "vertical_translation_mass_kg": float(mass[0, 0]),
        "diagnostics": diagnostics,
        "pressure_weights": actual.tolist(),
        "expected_pressure_weights": expected.tolist(),
        "scope": "Manufactured harmonic fields; not measured vessel calibration",
    }


def rigid_cell_reference(degrees=(6, 8, 10), depth=0.065):
    """Compare full nonlocal matrices and pressure to separated cosine solutions.

    Top potential is zero; FOUR VERTICAL SIDES ARE RIGID (zero normal flux).
    This differs from the earlier pressure-release-sided sine reference.
    """
    import numpy as np

    from spatial_sculptures.simulation.fluid_loading import (
        ColumnWater,
        pressure_release_mass_per_area,
    )
    from spatial_sculptures.simulation.fluid_potential import PotentialSettings, assemble_potential
    from spatial_sculptures.simulation.structures import GraphSurface

    surface = GraphSurface(0.72, 0.58, domain="rectangle")
    water = ColumnWater(depth)
    indices = ((0, 0), (1, 0), (0, 1), (1, 1), (2, 1), (1, 2))
    lx, ly = 2 * surface.radius_x, 2 * surface.radius_y
    probes = np.array([[-0.2, -0.04, depth * 0.5], [0.25, -0.10, depth * 0.6]])
    expected_mass, expected_pressure = [], []
    for m, n in indices:
        k = pi * sqrt((m / lx) ** 2 + (n / ly) ** 2)
        norm = (lx if m == 0 else lx / 2) * (ly if n == 0 else ly / 2)
        expected_mass.append(norm * pressure_release_mass_per_area(k, water))
        shape = np.cos(m * pi * (probes[:, 0] / lx + 0.5)) * np.cos(
            n * pi * (probes[:, 1] / ly + 0.5)
        )
        vertical = (
            (probes[:, 2] - depth)
            if k == 0
            else np.sinh(k * (probes[:, 2] - depth)) / (k * np.cosh(k * depth))
        )
        expected_pressure.append(-water.density_kg_m3 * shape * vertical)
    expected_mass = np.diag(expected_mass)
    expected_pressure = np.asarray(expected_pressure).T
    rows = []
    for degree in degrees:
        fluid = assemble_potential(surface, water, PotentialSettings(degree, 3, 7, 2, 6))
        flux = np.column_stack(
            [
                np.cos(m * pi * (fluid.x / lx + 0.5)) * np.cos(n * pi * (fluid.y / ly + 0.5))
                for m, n in indices
            ]
        )
        coefficients, actual_mass, diagnostics = fluid.solve_flux(flux)
        pressure = fluid.observations(coefficients, probes)
        mass_error = float(
            np.linalg.norm(actual_mass - expected_mass) / np.linalg.norm(expected_mass)
        )
        pressure_error = float(
            np.linalg.norm(pressure - expected_pressure) / np.linalg.norm(expected_pressure)
        )
        rows.append(
            {
                "degree": degree,
                "relative_added_matrix_difference": mass_error,
                "relative_pressure_weight_difference": pressure_error,
                "pressure_weights": pressure.tolist(),
                "added_mass_matrix_kg": actual_mass.tolist(),
                "diagnostics": diagnostics,
            }
        )
    return {
        "passed": max(
            rows[-1]["relative_added_matrix_difference"],
            rows[-1]["relative_pressure_weight_difference"],
        )
        < 0.002,
        "tolerance": 0.002,
        "depth_m": depth,
        "density_kg_m3": water.density_kg_m3,
        "lengths_m": [lx, ly],
        "mode_indices": indices,
        "probe_positions_m": probes.tolist(),
        "expected_added_matrix_kg": expected_mass.tolist(),
        "expected_pressure_weights": expected_pressure.tolist(),
        "refinements": rows,
        "boundary_conditions": "phi=0 on top; rigid vertical sides; prescribed cosine bottom flux",
    }


def ngsolve_rigid_cell(mesh_sizes=(0.35, 0.25, 0.18), depth=0.065):
    """Independent tetrahedral Laplace solves, checking full matrices AND probe pressure."""
    import ngsolve as ng
    import numpy as np
    from netgen.csg import unit_cube

    reference = rigid_cell_reference(degrees=(10,), depth=depth)
    lx, ly = reference["lengths_m"]
    probes = np.asarray(reference["probe_positions_m"])
    expected_mass = np.asarray(reference["expected_added_matrix_kg"])
    expected_pressure = np.asarray(reference["expected_pressure_weights"])
    rows = []
    for maxh in mesh_sizes:
        mesh = ng.Mesh(unit_cube.GenerateMesh(maxh=maxh))
        deformation = ng.GridFunction(ng.VectorH1(mesh, order=1))
        deformation.Set(ng.CF(((lx - 1) * ng.x, (ly - 1) * ng.y, (depth - 1) * ng.z)))
        mesh.SetDeformation(deformation)
        # Point location uses the undeformed mesh; evaluation uses the affine deformation.
        points = [mesh(x / lx + 0.5, y / ly + 0.5, z / depth) for x, y, z in probes]
        actual_xyz = np.array([[ng.x(p), ng.y(p), ng.z(p)] for p in points])
        if not np.allclose(actual_xyz, probes + [lx / 2, ly / 2, 0], atol=1e-12):
            raise ValueError("NGSolve deformed point coordinates do not match pressure probes")
        space = ng.H1(mesh, order=4, dirichlet="top")
        u, v = space.TnT()
        energy = ng.BilinearForm(space, symmetric=True)
        energy += ng.grad(u) * ng.grad(v) * ng.dx
        energy.Assemble()
        inverse = energy.mat.Inverse(space.FreeDofs(), inverse="sparsecholesky")
        shapes = [
            ng.cos(m * pi * ng.x / lx) * ng.cos(n * pi * ng.y / ly)
            for m, n in reference["mode_indices"]
        ]
        mass, pressure = [], []
        for shape in shapes:
            rhs = ng.LinearForm(space)
            rhs += -shape * v * ng.ds("bottom", bonus_intorder=10)
            rhs.Assemble()
            potential = ng.GridFunction(space)
            potential.vec.data = inverse * rhs.vec
            mass.append(
                [
                    float(
                        -1000
                        * ng.Integrate(
                            other * potential,
                            mesh,
                            ng.BND,
                            definedon=mesh.Boundaries("bottom"),
                            order=12,
                        )
                    )
                    for other in shapes
                ]
            )
            pressure.append([-1000 * potential(p) for p in points])
        mass, pressure = np.asarray(mass).T, np.asarray(pressure).T
        rows.append(
            {
                "unit_cube_maxh": maxh,
                "dofs": space.ndof,
                "relative_added_matrix_difference": float(
                    np.linalg.norm(mass - expected_mass) / np.linalg.norm(expected_mass)
                ),
                "relative_pressure_weight_difference": float(
                    np.linalg.norm(pressure - expected_pressure) / np.linalg.norm(expected_pressure)
                ),
                "pressure_weights": pressure.tolist(),
                "added_mass_matrix_kg": mass.tolist(),
            }
        )
    return {
        "passed": max(
            rows[-1]["relative_added_matrix_difference"],
            rows[-1]["relative_pressure_weight_difference"],
        )
        < 0.002,
        "tolerance": 0.002,
        "ngsolve_version": ng.__version__,
        "depth_m": depth,
        "boundary_conditions": reference["boundary_conditions"],
        "probe_positions_m": probes.tolist(),
        "meshes": rows,
        "scope": "Independent fluid-cell validation, not a curved-vessel external solve",
    }
