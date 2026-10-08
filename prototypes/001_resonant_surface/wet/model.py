"""Pure numerical wet model: shared metal motion, surface elevation and fluid pressure."""

import importlib
from dataclasses import replace


def build_model(baseline, settings, cache_directory, *, integration_order=7, refinement=2):
    """Reduce 3D nonlocal fluid inertia into an explicitly retained dry modal subspace."""
    import numpy as np

    from spatial_sculptures.simulation.fluid_loading import ColumnWater
    from spatial_sculptures.simulation.fluid_potential import (
        PotentialSettings,
        assemble_potential,
        couple_wall_modes,
        loaded_modal_modes,
    )

    dry_model = importlib.import_module("prototypes.001_resonant_surface.dry.model")
    physical = replace(baseline, mode_count=settings.dry_basis_count)
    dry, _, _ = dry_model.get_modes(physical, cache_directory)
    fluid = assemble_potential(
        physical.surface,
        ColumnWater(settings.depth_m, settings.density_kg_m3),
        PotentialSettings(
            settings.horizontal_degree, settings.vertical_degree, integration_order, refinement
        ),
    )
    coefficients, mass, fluid_diagnostics = couple_wall_modes(fluid, dry)
    wet, potentials, modal_diagnostics = loaded_modal_modes(
        dry, mass, coefficients, settings.playback_count
    )
    probes = np.array([(x, y, fluid.basis.level - d) for x, y, d in settings.hydrophones])
    pressure_weights = fluid.observations(potentials, probes)
    return (
        wet,
        fluid,
        potentials,
        pressure_weights,
        {
            "fluid": fluid_diagnostics,
            "modal": modal_diagnostics,
            "volume_m3": fluid.volume_m3,
            "water_mass_kg": settings.density_kg_m3 * fluid.volume_m3,
            "probe_positions_m": probes.tolist(),
        },
    )


class WetSimulation:
    """All observations derive from one finite-pulse/harmonic modal response."""

    def __init__(self, physical, settings, modes, pressure_weights):
        import numpy as np

        from spatial_sculptures.simulation.modal import Mode
        from spatial_sculptures.simulation.mode_bank import ModalResponse

        self.cached, self.pressure_weights = modes, np.asarray(pressure_weights, dtype=float)
        if (
            self.pressure_weights.ndim != 2
            or self.pressure_weights.shape[1] != len(modes.frequencies)
            or not np.all(np.isfinite(self.pressure_weights))
        ):
            raise ValueError("Finite hydrophone x mode pressure weights required")
        projected = [modes.patch_weights(e.patch, e.direction) for e in physical.exciters]
        mode_parameters = tuple(
            Mode(f"wet_{i + 1}", float(f), float(m), physical.damping_ratio)
            for i, (f, m) in enumerate(zip(modes.frequencies, modes.masses, strict=True))
        )
        drives = []
        for index in range(len(modes.frequencies)):
            events = [
                (e.start, e.frequency_hz, e.phase, e.force_n * p[index])
                for e, p in zip(physical.exciters, projected, strict=True)
                if e.force_n
            ]
            for impulse in physical.impulses:
                force = (
                    impulse.impulse_ns / settings.pulse_seconds * projected[impulse.exciter][index]
                )
                events.extend(
                    (
                        (impulse.time, 0.0, 0.0, force),
                        (impulse.time + settings.pulse_seconds, 0.0, 0.0, -force),
                    )
                )
            drives.append(events)
        self.response = ModalResponse(mode_parameters, [()] * len(drives), drives)

    def accelerations(self, times, q, v):
        """Finite-pulse forcing balance, m/s²; avoids dropping impulse pressure distributions."""
        import numpy as np

        forces = np.zeros_like(q)
        for index, events in enumerate(self.response.drives):
            for start, frequency, phase, force in events:
                active = times >= start
                forces[index] += (
                    force
                    * np.cos(2 * np.pi * frequency * np.maximum(times - start, 0) + phase)
                    * active
                )
        masses = np.array([m.mass_kg for m in self.response.modes])[:, None]
        decay = np.array([m.decay for m in self.response.modes])[:, None]
        omega = np.array([m.omega for m in self.response.modes])[:, None]
        return forces / masses - 2 * decay * v - omega**2 * q

    def pressure_trace(self, times, *, chunk_samples=4096):
        """Actual perturbation pressure in Pa; bounded audio-rate modal histories."""
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
            raise ValueError("Finite nonnegative times and a positive integer chunk size required")
        result = np.empty((len(self.pressure_weights), len(times)))
        for start in range(0, len(times), chunk_samples):
            part = slice(start, start + chunk_samples)
            q, v = self.response.trace(times[part], use_numpy=True)
            result[:, part] = self.pressure_weights @ self.accelerations(times[part], q, v)
        return result
