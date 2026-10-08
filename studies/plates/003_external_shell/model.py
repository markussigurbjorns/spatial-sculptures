"""Independent NGSolve HHJ shell study; optional, not a simulation/playback dependency.

The linear mixed Kirchhoff–Love formulation follows NGSolve's shell tutorial:
https://docu.ngsolve.org/ngs24/SaS/linear_KL_RM_shell_HHJ_TDNNS.html

Only plain parameter dictionaries cross the boundary. No production geometry,
quadrature, basis, shell matrices, mode cache or response equations are imported.
NGSolve runtime verification is required before trusting this implementation.
"""

from dataclasses import dataclass
from math import cos, isfinite, pi, sin, sqrt


@dataclass(frozen=True)
class Settings:
    maxh: float = 0.08  # Netgen XY mesh length, metres, not a tensor-grid cell count.
    rim_segments: int = 64  # Independently refine the approximation of the free boundary.
    geometry_order: int = 2  # Curved quadratic triangles; 1 reproduces the earlier polygon trial.
    order: int = 3
    bonus_intorder: int = 6
    mode_count: int = 512
    eigen_tolerance: float = 1e-9

    def __post_init__(self):
        if not isfinite(self.maxh) or self.maxh <= 0:
            raise ValueError("External mesh length must be finite and positive")
        for name, minimum in (
            ("rim_segments", 16),
            ("order", 3),
            ("bonus_intorder", 0),
            ("mode_count", 1),
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
        if not isfinite(self.eigen_tolerance) or not 0 < self.eigen_tolerance < 1e-3:
            raise ValueError("Eigen tolerance must lie between zero and 1e-3")
        if self.geometry_order not in (1, 2):
            raise ValueError("Geometry order must be 1 (polygon) or 2 (curved)")


def height(surface, x, y):
    """Independent graph definition, also usable with NGSolve coefficient functions."""
    a, b = x / surface["radius_x"], y / surface["radius_y"]
    return (
        surface["center_z"]
        + surface["rise"] * (a * a + b * b)
        + surface["asymmetry"] * a * (1 - a * a - b * b)
    )


def outline(surface, segments):
    """Counterclockwise reference XY boundary; rectangle edges remain exact."""
    a, b = surface["radius_x"], surface["radius_y"]
    if surface["domain"] == "rectangle":
        return [(-a, -b), (a, -b), (a, b), (-a, b)]
    return [
        (a * cos(2 * pi * i / segments), b * sin(2 * pi * i / segments)) for i in range(segments)
    ]


def patch_corners(patch):
    x, y, d = patch["x"], patch["y"], patch["width"] / 2
    return [(x - d, y - d), (x + d, y - d), (x + d, y + d), (x - d, y + d)]


def check_parameters(parameters):
    """Reject unsupported physical problems rather than silently substituting one."""
    surface, material = parameters["surface"], parameters["material"]
    if surface["domain"] not in ("ellipse", "rectangle"):
        raise ValueError("The external study supports ellipse and rectangle graphs")
    numbers = [*surface.values()]
    numbers.remove(surface["domain"])
    if (
        not all(isfinite(v) for v in numbers)
        or min(surface["radius_x"], surface["radius_y"]) <= 0
        or not isfinite(parameters["thickness"])
        or parameters["thickness"] <= 0
        or not all(isfinite(material[k]) and material[k] > 0 for k in ("youngs_modulus", "density"))
        or not isfinite(material["poisson_ratio"])
        or not -1 < material["poisson_ratio"] < 0.5
    ):
        raise ValueError(
            "Finite graph, positive thickness/material and valid Poisson ratio required"
        )
    if parameters.get("water_depth_m", 0) != 0:
        raise ValueError("External study is dry; water coupling is not implemented")
    damping = parameters["damping_ratio"]
    if not isfinite(damping) or not 0 < damping < 1:
        raise ValueError("A positive modal damping ratio below one is required")
    patches = [v["patch"] for key in ("supports", "exciters") for v in parameters[key]]
    for patch in patches:
        if not all(isfinite(patch[k]) for k in ("x", "y", "width")) or patch["width"] <= 0:
            raise ValueError("Contact patches need finite positions and positive widths")
        for x, y in patch_corners(patch):
            inside = (
                (x / surface["radius_x"]) ** 2 + (y / surface["radius_y"]) ** 2 < 1
                if surface["domain"] == "ellipse"
                else abs(x) < surface["radius_x"] and abs(y) < surface["radius_y"]
            )
            if not inside:
                raise ValueError("Contact patches must lie strictly inside the surface")
    # The mesher partitions distinct, non-overlapping contact regions explicitly.
    for i, first in enumerate(patches):
        for other in patches[i + 1 :]:
            reach = (first["width"] + other["width"]) / 2
            if abs(first["x"] - other["x"]) <= reach and abs(first["y"] - other["y"]) <= reach:
                raise ValueError("Touching/overlapping patches require a different mesh partition")
    for support in parameters["supports"]:
        if len(support["stiffness"]) != 3 or not all(
            isfinite(v) and v >= 0 for v in support["stiffness"]
        ):
            raise ValueError("Support stiffness needs three nonnegative finite components")
    for exciter in parameters["exciters"]:
        if not isfinite(exciter["added_mass_kg"]) or exciter["added_mass_kg"] < 0:
            raise ValueError("Attached mass must be finite and nonnegative")
        if len(exciter["direction"]) != 3 or not all(isfinite(v) for v in exciter["direction"]):
            raise ValueError("Exciter direction needs three finite components")
        if abs(sum(v * v for v in exciter["direction"]) - 1) > 1e-10:
            raise ValueError("Exciter directions must be unit vectors")
    for x, y in parameters["pickups"]:
        if not isfinite(x) or not isfinite(y):
            raise ValueError("Pickup coordinates must be finite")
        if surface["domain"] == "ellipse":
            inside = (x / surface["radius_x"]) ** 2 + (y / surface["radius_y"]) ** 2 < 1
        else:
            inside = abs(x) < surface["radius_x"] and abs(y) < surface["radius_y"]
        if not inside:
            raise ValueError("Pickups must lie strictly inside the surface")


def dependencies():
    """Load large optional packages only when an external solve is requested."""
    try:
        import ngsolve as ng
        import numpy as np
        import scipy
    except ImportError as error:
        raise ImportError("External solver needs .[external] (NGSolve, SciPy and NumPy)") from error
    return ng, np, scipy


def make_mesh(parameters, settings):
    """Conforming Netgen triangles lifted by a polynomial graph deformation.

    Contact boundaries are meshed, not quadrature-point masks. Quadratic elements
    follow elliptical arcs; the boundary approximation is independently refined.
    The cubic graph composed with a quadratic XY map has degree six, which is
    retained in the geometry lift. No mechanical displacement mass is condensed.
    """
    import netgen.meshing as nm
    from netgen.geom2d import SplineGeometry

    ng, _, _ = dependencies()
    geometry = SplineGeometry()
    labels = ["shell"]

    def loop(points, left, right, boundary):
        indices = [geometry.AppendPoint(x, y) for x, y in points]
        for i, index in enumerate(indices):
            geometry.Append(
                ["line", index, indices[(i + 1) % len(indices)]],
                leftdomain=left,
                rightdomain=right,
                bc=boundary,
            )

    graph = parameters["surface"]
    if graph["domain"] == "ellipse" and settings.geometry_order == 2:
        # Rational quadratic arcs in Netgen's geometry, followed by polynomial
        # quadratic FE geometry. The latter still needs a boundary refinement check.
        count = settings.rim_segments
        vertices = [geometry.AppendPoint(x, y) for x, y in outline(graph, count)]
        for i, vertex in enumerate(vertices):
            angle = 2 * pi * (i + 0.5) / count
            middle = geometry.AppendPoint(
                graph["radius_x"] * cos(angle) / cos(pi / count),
                graph["radius_y"] * sin(angle) / cos(pi / count),
            )
            geometry.Append(
                ["spline3", vertex, middle, vertices[(i + 1) % count]],
                leftdomain=1,
                rightdomain=0,
                bc=1,
            )
    else:
        loop(outline(graph, settings.rim_segments), 1, 0, 1)
    for key, singular in (("supports", "support"), ("exciters", "exciter")):
        for i, item in enumerate(parameters[key]):
            labels.append(f"{singular}_{i + 1}")
            loop(patch_corners(item["patch"]), len(labels), 1, 2)
    planar = geometry.GenerateMesh(maxh=settings.maxh)
    if settings.geometry_order == 2:
        planar.SecondOrder()
    surface = nm.Mesh(dim=3)
    faces = [surface.AddRegion(label, dim=2) for label in labels]
    rim, interface = surface.AddRegion("rim", dim=1), surface.AddRegion("contact_edge", dim=1)
    vertices = [surface.Add(nm.MeshPoint(nm.Pnt(p.p[0], p.p[1], 0))) for p in planar.Points()]
    for element in planar.Elements2D():
        surface.Add(
            nm.Element2D(faces[element.index - 1], [vertices[v.nr - 1] for v in element.points])
        )
    for edge in planar.Elements1D():
        surface.Add(
            nm.Element1D(
                [vertices[v.nr - 1] for v in edge.points],
                # Netgen's edge index identifies a geometric segment, not its BC.
                index=rim if planar.EdgeDescriptor(edge.index).domout == 0 else interface,
            )
        )
    surface.Compress()
    mesh = ng.Mesh(surface)
    deformation = ng.GridFunction(ng.VectorH1(mesh, order=3 * settings.geometry_order))
    deformation.Set(
        ng.CF((0, 0, height(parameters["surface"], ng.x, ng.y))), definedon=mesh.Boundaries(".*")
    )
    mesh.SetDeformation(deformation)
    return mesh, deformation


def sparse_matrix(matrix):
    """Export full COO, avoiding the half-storage used by symmetric NGSolve forms."""
    from scipy.sparse import coo_matrix

    rows, columns, values = matrix.COO()
    return coo_matrix((values, (rows, columns)), shape=(matrix.height, matrix.width)).tocsr()


def local_inverse(matrix):
    """Invert only disconnected small stress blocks, never a dense global matrix."""
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    graph = matrix.copy()
    graph.eliminate_zeros()
    count, labels = connected_components(graph, directed=False)
    rows, columns, values = [], [], []
    for label in range(count):
        index = np.flatnonzero(labels == label)
        if len(index) > 128:
            raise ValueError("Stress block is not local; check discontinuous HHJ space")
        block = matrix[index][:, index].toarray()
        inverse = np.linalg.inv(block)
        rows.extend(np.repeat(index, len(index)))
        columns.extend(np.tile(index, len(index)))
        values.extend(inverse.ravel())
    return coo_matrix((values, (rows, columns)), shape=matrix.shape).tocsr()


@dataclass
class ExternalModes:
    frequencies: object
    pickup_weights: object
    force_weights: object
    coefficients: object
    mesh: object
    displacement_space: object
    deformation: object  # Keep the geometry lift alive while sampling.
    diagnostics: dict

    def sample_shapes(self, x, y, count):
        """Sample XYZ displacement shapes at reference XY points on the lifted mesh."""
        ng, np, _ = dependencies()
        result = np.empty((len(x), 3, count))
        points = [self.mesh(float(a), float(b), 0, ng.BND) for a, b in zip(x, y, strict=True)]
        field = ng.GridFunction(self.displacement_space)
        for i in range(count):
            field.vec.FV().NumPy()[:] = self.coefficients[:, i]
            result[:, :, i] = [field(point) for point in points]
        return result

    def mobility(self, sample_hz, damping, count=None):
        """Independent mass-normalized modal sum; exp(+iωt), SI velocity per newton."""
        import numpy as np

        count = len(self.frequencies) if count is None else count
        samples = np.asarray(sample_hz)
        if (
            not 1 <= count <= len(self.frequencies)
            or not isfinite(damping)
            or not 0 < damping < 1
            or samples.ndim != 1
            or not len(samples)
            or not np.all(np.isfinite(samples))
            or np.any(samples < 0)
        ):
            raise ValueError("Requested modal count is outside the external bank")
        w = 2 * pi * samples
        natural = 2 * pi * self.frequencies[:count]
        denominator = natural[:, None] ** 2 - w[None, :] ** 2
        denominator = denominator + 2j * damping * natural[:, None] * w[None, :]
        result = np.empty((len(self.pickup_weights), len(self.force_weights), len(w)), complex)
        for pickup, p in enumerate(self.pickup_weights):
            for exciter, f in enumerate(self.force_weights):
                result[pickup, exciter] = (
                    1j * w * np.sum((p[:count] * f[:count])[:, None] / denominator, axis=0)
                )
        return result


def solve(parameters, settings, *, simply_supported=False):
    """Assemble HHJ/Regge shell and solve finite eigenvalues with translational mass.

    Eliminate *only* the discontinuous, massless bending stress. Displacement
    bubbles retain their mass; facet rotations remain massless. Shift-invert
    eigsh supports positive-semidefinite M when sigma is supplied. No shear or
    rotary inertia is added to make that matrix invertible.
    """
    import time

    check_parameters(parameters)
    ng, np, scipy = dependencies()
    from scipy.sparse import block_diag, csr_matrix
    from scipy.sparse.linalg import LinearOperator, eigsh, splu

    started = time.perf_counter()
    mesh, deformation = make_mesh(parameters, settings)
    if simply_supported and (
        parameters["surface"]["domain"] != "rectangle"
        or parameters["surface"]["rise"]
        or parameters["surface"]["asymmetry"]
        or parameters["supports"]
        or parameters["exciters"]
    ):
        raise ValueError("Plate prerequisite requires a flat unsupported/unloaded rectangle")
    boundary = "rim" if simply_supported else ""
    displacement = ng.VectorH1(
        mesh,
        order=settings.order,
        dirichletx_bbnd=boundary,
        dirichlety_bbnd=boundary,
        dirichletz_bbnd=boundary,
    )
    stress = ng.HDivDivSurface(mesh, order=settings.order - 1, discontinuous=True)
    rotation = ng.NormalFacetSurface(mesh, order=settings.order - 1)
    space = displacement * stress * rotation
    (u, moment, angle), (v, test_moment, test_angle) = space.TnT()
    moment, test_moment = moment.Trace(), test_moment.Trace()
    angle, test_angle = angle.Trace(), test_angle.Trace()
    normal, tangent = ng.specialcf.normal(3), ng.specialcf.tangential(3)
    conormal = ng.Cross(normal, tangent)
    projection = ng.Id(3) - ng.OuterProduct(normal, normal)
    regge = ng.HCurlCurl(mesh, order=settings.order - 1)
    strain_u = ng.Interpolate(ng.Sym(projection * ng.Grad(u).Trace()), regge)
    strain_v = ng.Interpolate(ng.Sym(projection * ng.Grad(v).Trace()), regge)
    e, nu = parameters["material"]["youngs_modulus"], parameters["material"]["poisson_ratio"]
    thickness = parameters["thickness"]
    material_strain = e / (1 - nu**2) * ((1 - nu) * strain_u + nu * ng.Trace(strain_u) * ng.Id(3))
    inverse_moment = (1 + nu) / e * (moment - nu / (nu + 1) * ng.Trace(moment) * ng.Id(3))
    curvature_u = (u.Operator("hesseboundary").trans * normal).Reshape((3, 3))
    curvature_v = (v.Operator("hesseboundary").trans * normal).Reshape((3, 3))
    measure = ng.ds(bonus_intorder=settings.bonus_intorder)
    edges = ng.ds(element_boundary=True, bonus_intorder=settings.bonus_intorder)
    form = ng.BilinearForm(space, symmetric=False, condense=False)
    form += (
        thickness * ng.InnerProduct(material_strain, strain_v)
        - 12 / thickness**3 * ng.InnerProduct(inverse_moment, test_moment)
        + ng.InnerProduct(moment, curvature_v)
        + ng.InnerProduct(test_moment, curvature_u)
    ) * measure
    form += (
        moment[conormal, conormal] * (test_angle - ng.Grad(v).Trace()[normal, :]) * conormal
        + test_moment[conormal, conormal] * (angle - ng.Grad(u).Trace()[normal, :]) * conormal
    ) * edges
    trial, test = displacement.TnT()
    mass_form = ng.BilinearForm(displacement, symmetric=False)
    mass_form += (
        parameters["material"]["density"] * thickness * ng.InnerProduct(trial, test) * measure
    )
    with ng.TaskManager():
        form.Assemble()
        mass_form.Assemble()
    full = sparse_matrix(form.mat)
    skew = full - full.T
    symmetry_error = np.linalg.norm(skew.data) / max(np.linalg.norm(full.data), 1e-30)
    if symmetry_error > 1e-10:
        raise ValueError(f"External mixed shell matrix is asymmetric: {symmetry_error}")
    n_u, n_s = displacement.ndof, stress.ndof
    free = np.array(list(space.FreeDofs()), bool)
    u_index = np.flatnonzero(free[:n_u])
    s_index = np.flatnonzero(free[n_u : n_u + n_s]) + n_u
    h_index = np.flatnonzero(free[n_u + n_s :]) + n_u + n_s
    q_index = np.r_[u_index, h_index]
    stress_matrix = full[s_index][:, s_index]
    coupling = full[s_index][:, q_index]
    stiffness = full[q_index][:, q_index] - coupling.T @ local_inverse(stress_matrix) @ coupling
    # Only roundoff symmetrization, after checking the original mixed assembly.
    stiffness = ((stiffness + stiffness.T) * 0.5).tocsr()
    mass = block_diag(
        (
            sparse_matrix(mass_form.mat)[u_index][:, u_index],
            csr_matrix((len(h_index), len(h_index))),
        ),
        format="csr",
    )
    areas, means = {}, {}
    for key, singular in (("supports", "support"), ("exciters", "exciter")):
        for i, item in enumerate(parameters[key]):
            label = f"{singular}_{i + 1}"
            region = mesh.Boundaries(label)
            area = ng.Integrate(
                1, mesh, definedon=region, order=2 * settings.order + settings.bonus_intorder
            )
            if not isfinite(area) or area <= 0:
                raise ValueError(f"Missing contact region {label}")
            areas[label] = area
            directions = []
            for component in range(3):
                load = ng.LinearForm(displacement)
                load += (
                    test[component]
                    / area
                    * ng.ds(definedon=region, bonus_intorder=settings.bonus_intorder)
                )
                load.Assemble()
                mean = np.r_[load.vec.FV().NumPy()[u_index], np.zeros(len(h_index))]
                directions.append(mean)
                vector = csr_matrix(mean[:, None])
                coefficient = (
                    item["stiffness"][component] if key == "supports" else item["added_mass_kg"]
                )
                if coefficient:
                    addition = coefficient * (vector @ vector.T)
                    if key == "supports":
                        stiffness += addition
                    else:
                        mass += addition
            means[label] = np.array(directions)
    if settings.mode_count >= len(u_index):
        raise ValueError("External bank must be smaller than the displacement dimension")
    factor = splu(stiffness.tocsc())
    inverse = LinearOperator(stiffness.shape, matvec=factor.solve, dtype=float)
    initial = np.r_[np.random.default_rng(1729).normal(size=len(u_index)), np.zeros(len(h_index))]
    eigenvalues, vectors = eigsh(
        stiffness,
        M=mass,
        k=settings.mode_count,
        sigma=0,
        which="LM",
        OPinv=inverse,
        tol=settings.eigen_tolerance,
        v0=initial,
        maxiter=2000,
    )
    ordering = np.argsort(eigenvalues)
    eigenvalues, vectors = eigenvalues[ordering], vectors[:, ordering]
    if np.any(eigenvalues <= 0) or not np.all(np.isfinite(eigenvalues)):
        raise ValueError("Zero/negative shell mode: check restraint and HHJ assembly")
    vectors /= np.sqrt(np.einsum("ij,ij->j", vectors, mass @ vectors))[None, :]
    residuals = np.linalg.norm(
        stiffness @ vectors - (mass @ vectors) * eigenvalues[None, :], axis=0
    )
    residuals /= np.linalg.norm(stiffness @ vectors, axis=0) + eigenvalues * np.linalg.norm(
        mass @ vectors, axis=0
    )
    mass_error = float(np.max(np.abs(vectors.T @ (mass @ vectors) - np.eye(settings.mode_count))))
    if residuals.max() > 1e-6 or mass_error > 1e-6:
        raise ValueError("External eigen residual/orthogonality check failed")
    coefficients = np.zeros((n_u, settings.mode_count))
    coefficients[u_index] = vectors[: len(u_index)]
    forces = np.array(
        [
            np.asarray(exciter["direction"]) @ means[f"exciter_{i + 1}"] @ vectors
            for i, exciter in enumerate(parameters["exciters"])
        ]
    )
    frequencies = np.sqrt(eigenvalues) / (2 * pi)
    area = ng.Integrate(1, mesh, ng.BND, order=2 * settings.order + settings.bonus_intorder)
    diagnostics = {
        "ngsolve_version": ng.__version__,
        "scipy_version": scipy.__version__,
        "numpy_version": np.__version__,
        "surface_triangles": len(list(mesh.Elements(ng.BND))),
        "mixed_dofs": space.ndof,
        "displacement_dofs": len(u_index),
        "massless_rotation_dofs": len(h_index),
        "shell_area_m2": float(area),
        "shell_mass_kg": float(area * parameters["material"]["density"] * thickness),
        "contact_areas_m2": areas,
        "matrix_symmetry_relative": float(symmetry_error),
        "maximum_eigen_residual": float(residuals.max()),
        "maximum_mass_orthogonality_error": mass_error,
        "elapsed_seconds": time.perf_counter() - started,
        "membrane": "Regge interpolation, order displacement-1",
        "geometry_order": settings.geometry_order,
        "rim": (
            "simply supported rectangle"
            if simply_supported
            else "quadratic approximation to ellipse"
            if settings.geometry_order == 2
            else "free inscribed polygon"
        ),
    }
    result = ExternalModes(
        frequencies, None, forces, coefficients, mesh, displacement, deformation, diagnostics
    )
    if parameters["pickups"]:
        shapes = result.sample_shapes(*np.array(parameters["pickups"]).T, settings.mode_count)
        result.pickup_weights = shapes[:, 2, :]
    else:
        result.pickup_weights = np.empty((0, settings.mode_count))
    return result


def plate_check(*, maxh=0.08, order=3, bonus_intorder=6):
    """First six simply supported frequencies against an independent closed formula."""
    parameters = {
        "surface": {
            "radius_x": 0.72,
            "radius_y": 0.58,
            "rise": 0.0,
            "asymmetry": 0.0,
            "center_z": 0.0,
            "domain": "rectangle",
        },
        "material": {"youngs_modulus": 193e9, "density": 8030.0, "poisson_ratio": 0.30},
        "thickness": 0.005,
        "supports": [],
        "exciters": [],
        "pickups": [],
        "damping_ratio": 0.005,
        "water_depth_m": 0.0,
    }
    result = solve(
        parameters,
        Settings(maxh=maxh, order=order, bonus_intorder=bonus_intorder, mode_count=6),
        simply_supported=True,
    )
    h, e, rho, nu = 0.005, 193e9, 8030.0, 0.30
    flexural = e * h**3 / (12 * (1 - nu**2))
    exact = sorted(
        pi / 2 * sqrt(flexural / (rho * h)) * ((m / 1.44) ** 2 + (n / 1.16) ** 2)
        for m in range(1, 7)
        for n in range(1, 7)
    )[:6]
    differences = [
        abs(float(actual) / reference - 1)
        for actual, reference in zip(result.frequencies, exact, strict=True)
    ]
    return {
        "analytical_frequencies_hz": exact,
        "external_frequencies_hz": result.frequencies.tolist(),
        "maximum_relative_frequency_difference": max(differences),
        "tolerance": 0.005,
        "passed": max(differences) <= 0.005,
        "diagnostics": result.diagnostics,
    }
