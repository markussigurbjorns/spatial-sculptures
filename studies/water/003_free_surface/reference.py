"""Rigid-cell gravity/capillary dispersion and independent fluid-potential checks."""

from dataclasses import dataclass
from math import pi, sqrt


@dataclass
class CosineSurface:
    """Explicit zero-mean reference shapes with rigid-cell natural capillary edges."""

    length_x: float
    length_y: float
    indices: tuple = ((1, 0), (0, 1), (1, 1), (2, 0), (0, 2), (2, 1))

    def evaluate(self, x, y):
        import numpy as np

        values, dx, dy = [], [], []
        for m, n in self.indices:
            kx, ky = m * pi / self.length_x, n * pi / self.length_y
            xx, yy = (
                kx * (np.asarray(x) + self.length_x / 2),
                ky * (np.asarray(y) + self.length_y / 2),
            )
            values.append(np.cos(xx) * np.cos(yy))
            dx.append(-kx * np.sin(xx) * np.cos(yy))
            dy.append(-ky * np.cos(xx) * np.sin(yy))
        return np.asarray(values).T, (np.asarray(dx).T, np.asarray(dy).T)


def analytical_cell(lengths=(1.44, 1.16), depth=0.065, gravity=9.81, tension=0.072):
    import numpy as np

    from spatial_sculptures.simulation.free_surface import gravity_capillary_frequency

    lx, ly = lengths
    surface = CosineSurface(lx, ly)
    probes = np.array([[-0.2 * lx, -0.04 * ly, 0.4 * depth], [0.25 * lx, -0.1 * ly, 0.6 * depth]])
    shapes = surface.evaluate(*probes[:, :2].T)[0]
    mass, pressure, frequency = [], [], []
    for index, (m, n) in enumerate(surface.indices):
        k = pi * sqrt((m / lx) ** 2 + (n / ly) ** 2)
        norm = (lx if m == 0 else lx / 2) * (ly if n == 0 else ly / 2)
        mass.append(1000 * norm / (k * np.tanh(k * depth)))
        pressure.append(
            -1000 * shapes[:, index] * np.cosh(k * probes[:, 2]) / (k * np.sinh(k * depth))
        )
        frequency.append(gravity_capillary_frequency(k, depth, 1000, gravity, tension))
    return surface, probes, np.diag(mass), np.asarray(pressure).T, np.sort(frequency)


def check_cells(degrees=(6, 8, 10)):
    """Check true gravity, mixed gravity/capillary and pure-capillary cases, in SI."""
    import numpy as np

    from spatial_sculptures.simulation.fluid_loading import ColumnWater
    from spatial_sculptures.simulation.fluid_potential import PotentialSettings
    from spatial_sculptures.simulation.free_surface import assemble_free_surface, solve_free_modes
    from spatial_sculptures.simulation.structures import GraphSurface

    cases = []
    for lengths, depth, gravity, tension in (
        ((1.44, 1.16), 0.065, 9.81, 0.0),
        ((0.05, 0.04), 0.0035, 9.81, 0.072),
        ((0.05, 0.04), 0.0035, 0.0, 0.072),
    ):
        eta, probes, expected_mass, expected_pressure, expected_frequency = analytical_cell(
            lengths, depth, gravity, tension
        )
        rows = []
        for degree in degrees:
            system = assemble_free_surface(
                GraphSurface(lengths[0] / 2, lengths[1] / 2, domain="rectangle"),
                ColumnWater(depth),
                settings=PotentialSettings(degree, 4, 7, 2, 6),
                surface_basis=eta,
                gravity=gravity,
                surface_tension=tension,
            )
            f, _, diagnostics = solve_free_modes(system, len(eta.indices))
            pressure = system.pressure_weights(probes)[0]
            rows.append(
                {
                    "degree": degree,
                    "frequency_maximum_relative_difference": float(
                        np.max(abs(f / expected_frequency - 1))
                    ),
                    "mass_matrix_relative_difference": float(
                        np.linalg.norm(system.mass - expected_mass) / np.linalg.norm(expected_mass)
                    ),
                    "pressure_relative_difference": float(
                        np.linalg.norm(pressure - expected_pressure)
                        / np.linalg.norm(expected_pressure)
                    ),
                    "frequencies_hz": f.tolist(),
                    "diagnostics": diagnostics,
                    "fluid_diagnostics": system.diagnostics,
                }
            )
        passed = (
            max(
                rows[-1][key]
                for key in (
                    "frequency_maximum_relative_difference",
                    "mass_matrix_relative_difference",
                    "pressure_relative_difference",
                )
            )
            < 0.002
        )
        cases.append(
            {
                "lengths_m": lengths,
                "depth_m": depth,
                "gravity_m_s2": gravity,
                "surface_tension_n_m": tension,
                "expected_frequencies_hz": expected_frequency.tolist(),
                "probe_positions_m": probes.tolist(),
                "refinements": rows,
                "passed": passed,
            }
        )
    return {
        "passed": all(c["passed"] for c in cases),
        "tolerance": 0.002,
        "cases": cases,
        "boundary_conditions": (
            "rigid floor/sides, dynamic top, zero normal surface slope; no mean-volume mode"
        ),
    }


def ngsolve_cell(mesh_sizes=(0.35, 0.25, 0.18)):
    """Independent Neumann 3D potential using a global Lagrange multiplier for its gauge."""
    import ngsolve as ng
    import numpy as np
    from netgen.csg import unit_cube

    lx, ly, depth, gravity, tension = 0.05, 0.04, 0.0035, 9.81, 0.072
    eta, probes, expected_mass, expected_pressure, expected_frequency = analytical_cell(
        (lx, ly), depth, gravity, tension
    )
    rows = []
    for maxh in mesh_sizes:
        mesh = ng.Mesh(unit_cube.GenerateMesh(maxh=maxh))
        deformation = ng.GridFunction(ng.VectorH1(mesh, order=1))
        deformation.Set(ng.CF(((lx - 1) * ng.x, (ly - 1) * ng.y, (depth - 1) * ng.z)))
        mesh.SetDeformation(deformation)
        space = ng.FESpace([ng.H1(mesh, order=4), ng.NumberSpace(mesh)])
        (u, multiplier), (v, constraint) = space.TnT()
        form = ng.BilinearForm(space, symmetric=True)
        form += (ng.grad(u) * ng.grad(v) + multiplier * v + constraint * u) * ng.dx
        form.Assemble()
        inverse = form.mat.Inverse(space.FreeDofs(), inverse="umfpack")
        shapes = [ng.cos(m * pi * ng.x / lx) * ng.cos(n * pi * ng.y / ly) for m, n in eta.indices]
        derivatives = [(s.Diff(ng.x), s.Diff(ng.y)) for s in shapes]
        stiffness = np.array(
            [
                [
                    ng.Integrate(
                        1000 * gravity * a * b + tension * (da[0] * db[0] + da[1] * db[1]),
                        mesh,
                        ng.BND,
                        definedon=mesh.Boundaries("top"),
                        order=14,
                    )
                    for b, db in zip(shapes, derivatives, strict=True)
                ]
                for a, da in zip(shapes, derivatives, strict=True)
            ]
        )
        points = [mesh(x / lx + 0.5, y / ly + 0.5, z / depth) for x, y, z in probes]
        if not np.allclose(
            [[ng.x(p), ng.y(p), ng.z(p)] for p in points], probes + [lx / 2, ly / 2, 0], atol=1e-12
        ):
            raise ValueError("Deformed reference probes do not match physical positions")
        mass, pressure = [], []
        for shape in shapes:
            rhs = ng.LinearForm(space)
            rhs += shape * v * ng.ds("top", bonus_intorder=10)
            rhs.Assemble()
            solution = ng.GridFunction(space)
            solution.vec.data = inverse * rhs.vec
            potential = solution.components[0]
            mean = ng.Integrate(
                potential, mesh, ng.BND, definedon=mesh.Boundaries("top"), order=14
            ) / (lx * ly)
            mass.append(
                [
                    1000
                    * ng.Integrate(
                        other * (potential - mean),
                        mesh,
                        ng.BND,
                        definedon=mesh.Boundaries("top"),
                        order=14,
                    )
                    for other in shapes
                ]
            )
            pressure.append([-1000 * (potential(p) - mean) for p in points])
        mass, pressure = np.asarray(mass).T, np.asarray(pressure).T
        factor = np.linalg.cholesky((mass + mass.T) / 2)
        left = np.linalg.solve(factor, stiffness)
        reduced = np.linalg.solve(factor, left.T).T
        frequencies = np.sqrt(np.linalg.eigvalsh((reduced + reduced.T) / 2)) / (2 * pi)
        rows.append(
            {
                "unit_cube_maxh": maxh,
                "dofs": space.ndof,
                "frequency_maximum_relative_difference": float(
                    np.max(abs(frequencies / expected_frequency - 1))
                ),
                "mass_matrix_relative_difference": float(
                    np.linalg.norm(mass - expected_mass) / np.linalg.norm(expected_mass)
                ),
                "pressure_relative_difference": float(
                    np.linalg.norm(pressure - expected_pressure) / np.linalg.norm(expected_pressure)
                ),
                "frequencies_hz": frequencies.tolist(),
            }
        )
    return {
        "passed": max(
            rows[-1][key]
            for key in (
                "frequency_maximum_relative_difference",
                "mass_matrix_relative_difference",
                "pressure_relative_difference",
            )
        )
        < 0.002,
        "tolerance": 0.002,
        "meshes": rows,
        "ngsolve_version": ng.__version__,
        "expected_frequencies_hz": expected_frequency.tolist(),
        "scope": "Independent rigid gravity/capillary cell, not an external curved basin solve",
    }
