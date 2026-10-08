"""Shared free-surface response: metal motion, water elevation and interior pressure."""

import importlib
import json
from dataclasses import dataclass, replace


@dataclass
class CoupledBank:
    metal: object
    potential_basis: object
    surface_basis: object
    potentials: object
    elevations: object
    pressure_a: object
    pressure_q: object
    damping: object

    def surface_weights(self, xy):
        """Elevation per modal displacement; resting footprint is checked separately."""
        import numpy as np

        xy = np.asarray(xy, dtype=float)
        if (
            xy.ndim != 2
            or xy.shape[1] != 2
            or not np.all(np.isfinite(xy))
            or not np.all(self.metal.surface.contains(*xy.T))
            or np.any(self.metal.surface.geometry(*xy.T)[0] > self.potential_basis.level + 1e-12)
        ):
            raise ValueError("Surface positions must lie in the resting wet footprint")
        return (
            np.column_stack((np.ones(len(xy)), self.surface_basis.evaluate(*xy.T)[0]))
            @ self.elevations
        )


def build_model(physical, settings, cache_directory, *, integration_order=7, refinement=2):
    """Couple a cached dry shell to independent gravity/capillary elevation coordinates."""
    import numpy as np

    from spatial_sculptures.simulation.fluid_loading import ColumnWater, water_quadrature
    from spatial_sculptures.simulation.fluid_potential import PotentialSettings
    from spatial_sculptures.simulation.free_surface import assemble_free_surface, solve_free_modes
    from spatial_sculptures.simulation.mode_cache import CachedModes
    from spatial_sculptures.simulation.structures import quadrature

    dry_module = importlib.import_module("prototypes.001_resonant_surface.dry.model")
    dry, _, _ = dry_module.get_modes(
        replace(physical, mode_count=settings.dry_basis_count), cache_directory
    )
    system = assemble_free_surface(
        dry.surface,
        ColumnWater(settings.depth_m, settings.density_kg_m3),
        settings=PotentialSettings(
            settings.horizontal_degree, settings.vertical_degree, integration_order, refinement
        ),
        surface_degree=settings.surface_degree,
        gravity=settings.gravity_m_s2,
        surface_tension=settings.surface_tension_n_m,
        wall_modes=dry,
    )
    frequencies, transform, modal_diagnostics = solve_free_modes(system, settings.playback_count)
    coefficients = np.einsum(
        "cbm,mn->cbn", dry.coefficients, transform[: system.wall_count], optimize=True
    )
    x, y, _ = quadrature(dry.surface, 8, 8, 5)
    metal_values = np.einsum(
        "pb,cbm->pcm", dry.space.evaluate(x, y)[0], coefficients, optimize=True
    )
    wx, wy, _, _ = water_quadrature(
        dry.surface,
        system.water,
        np.linspace(-dry.surface.radius_x, dry.surface.radius_x, 9),
        np.linspace(-dry.surface.radius_y, dry.surface.radius_y, 9),
        order=5,
    )
    eta_values = system.surface_weights(np.column_stack((wx, wy))) @ transform
    peaks = np.maximum(
        np.linalg.norm(metal_values, axis=1).max(axis=0), abs(eta_values).max(axis=0)
    )
    if np.any(peaks <= 0) or not np.all(np.isfinite(peaks)):
        raise ValueError("Vanishing coupled shape on normalization grids")
    # Damping interpolates prescribed solid/surface ratios by modal restoring-energy share.
    surface_fraction = (
        np.sum(transform * (system.surface_stiffness @ transform), axis=0)
        / (2 * np.pi * frequencies) ** 2
    )
    surface_fraction = np.clip(surface_fraction, 0.0, 1.0)
    damping = (
        physical.damping_ratio * (1 - surface_fraction)
        + settings.surface_damping_ratio * surface_fraction
    )
    transform /= peaks
    coefficients /= peaks
    metal = CachedModes(
        dry.surface,
        dry.space,
        coefficients,
        frequencies,
        1 / peaks**2,
        {
            "model": "linear shell + gravity/capillary surface, frozen shell equilibrium",
            "normalization": "unit joint sampled metal-vector/water-elevation peak; SI kg",
        },
    )
    probes = np.array([(x, y, system.basis.level - d) for x, y, d in settings.hydrophones])
    pressure_a, pressure_q = system.pressure_weights(probes)
    bank = CoupledBank(
        metal,
        system.basis,
        system.surface_basis,
        system.potentials @ transform,
        system.elevations @ transform,
        pressure_a @ transform,
        pressure_q @ transform,
        damping,
    )
    diagnostics = {
        "fluid": system.diagnostics,
        "modal": modal_diagnostics,
        "volume_m3": system.volume_m3,
        "area_m2": system.area_m2,
        "water_mass_kg": settings.density_kg_m3 * system.volume_m3,
        "probe_positions_m": probes.tolist(),
        "surface_energy_fraction": surface_fraction.tolist(),
        "limitations": [
            "Frozen dry-shell equilibrium: no hydrostatic prestress/elastogravity correction",
            "Linear resting footprint and natural capillary edge; no physical wetting law",
            "Inviscid incompressible fluid; assumed modal damping, no acoustic radiation",
        ],
    }
    return bank, system, diagnostics


def retained_bank(bank, count):
    """Keep one matched prefix of metal, water, pressure, mass and damping coordinates."""
    from spatial_sculptures.simulation.mode_cache import CachedModes

    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or not 1 <= count <= len(bank.metal.frequencies)
    ):
        raise ValueError("Retained count must be within the coupled bank")
    m = bank.metal
    metal = CachedModes(
        m.surface,
        m.space,
        m.coefficients[..., :count],
        m.frequencies[:count],
        m.masses[:count],
        m.metadata,
    )
    return CoupledBank(
        metal,
        bank.potential_basis,
        bank.surface_basis,
        bank.potentials[:, :count],
        bank.elevations[:, :count],
        bank.pressure_a[:, :count],
        bank.pressure_q[:, :count],
        bank.damping[:count],
    )


def save_bank(modes_path, fluid_path, bank):
    """Portable numerical arrays with JSON metadata; playback needs no solver or pickle."""
    import numpy as np

    from spatial_sculptures.simulation.mode_cache import save_modes

    save_modes(modes_path, bank.metal)
    basis = bank.potential_basis
    surface = bank.surface_basis
    parameters = {
        name: getattr(basis, name) for name in ("origin_x", "scale_x", "scale_y", "level", "depth")
    }
    np.savez_compressed(
        fluid_path,
        schema=np.array(1),
        basis=json.dumps(parameters),
        potential_indices=basis.indices,
        trace_means=basis.trace_means,
        surface_indices=surface.indices,
        surface_means=surface.means,
        surface_transform=surface.transform,
        potentials=bank.potentials,
        elevations=bank.elevations,
        pressure_a=bank.pressure_a,
        pressure_q=bank.pressure_q,
        damping=bank.damping,
    )


def load_bank(modes_path, fluid_path):
    """Load a finite, dimensionally consistent bank; evidence hashes are checked by the CLI."""
    import numpy as np

    from spatial_sculptures.simulation.free_surface import FreePotentialBasis, SurfaceBasis
    from spatial_sculptures.simulation.mode_cache import load_modes

    metal = load_modes(modes_path)
    with np.load(fluid_path, allow_pickle=False) as data:
        if int(data["schema"]) != 1:
            raise ValueError("Unknown free-surface cache schema")
        parameters = json.loads(str(data["basis"]))
        basis = FreePotentialBasis(
            data["potential_indices"].copy(),
            **parameters,
            trace_means=data["trace_means"].copy(),
        )
        surface = SurfaceBasis(
            data["surface_indices"].copy(),
            parameters["origin_x"],
            parameters["scale_x"],
            parameters["scale_y"],
            data["surface_means"].copy(),
            data["surface_transform"].copy(),
        )
        arrays = [
            data[k].copy()
            for k in ("potentials", "elevations", "pressure_a", "pressure_q", "damping")
        ]
    n, p, s = len(metal.frequencies), len(basis.indices), len(surface.indices)
    probes = arrays[2].shape[0]
    expected = [(p, n), (s + 1, n), (probes, n), (probes, n), (n,)]
    if (
        any(
            a.shape != shape or not np.all(np.isfinite(a))
            for a, shape in zip(arrays, expected, strict=True)
        )
        or np.any(arrays[-1] < 0)
        or np.any(arrays[-1] >= 1)
    ):
        raise ValueError("Inconsistent coupled cache arrays or damping")
    return CoupledBank(metal, basis, surface, *arrays)


class FreeSurfaceSimulation:
    """One exact finite-pulse/harmonic modal clock for all observations."""

    def __init__(self, physical, settings, bank):
        from spatial_sculptures.simulation.modal import Mode
        from spatial_sculptures.simulation.mode_bank import ModalResponse

        wet_module = importlib.import_module("prototypes.001_resonant_surface.wet.model")
        self.bank = bank
        self.engine = wet_module.WetSimulation(physical, settings, bank.metal, bank.pressure_a)
        parameters = tuple(
            Mode(f"coupled_{i + 1}", float(f), float(m), float(d))
            for i, (f, m, d) in enumerate(
                zip(bank.metal.frequencies, bank.metal.masses, bank.damping, strict=True)
            )
        )
        self.engine.response = ModalResponse(
            parameters, self.engine.response.impulses, self.engine.response.drives
        )
        self.response = self.engine.response

    def pressure_trace(self, times, *, chunk_samples=4096):
        """Pa perturbation, including the displacement-dependent mean-pressure gauge."""
        import numpy as np

        times = np.asarray(times, dtype=float)
        if (
            times.ndim != 1
            or not len(times)
            or not np.all(np.isfinite(times))
            or np.any(times < 0)
            or not isinstance(chunk_samples, int)
            or isinstance(chunk_samples, bool)
            or chunk_samples <= 0
        ):
            raise ValueError("Finite nonnegative times and a positive integer chunk required")
        result = np.empty((len(self.bank.pressure_a), len(times)))
        for start in range(0, len(times), chunk_samples):
            part = slice(start, start + chunk_samples)
            q, v = self.response.trace(times[part], use_numpy=True)
            a = self.engine.accelerations(times[part], q, v)
            result[:, part] = self.bank.pressure_a @ a + self.bank.pressure_q @ q
        return result
