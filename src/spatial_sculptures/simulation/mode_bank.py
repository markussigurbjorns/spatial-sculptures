"""One geometry-independent retained modal response for analytical and numerical models.

Force projections and shape evaluation belong to the model. This engine receives
projected total forces/impulses, and returns modal displacement, velocity and energy.
The scalar path is dependency-free; offline NumPy batching uses the same equations.
"""

from math import isfinite, tau

from .modal import ModalState, free_response, harmonic_amplitude, harmonic_response, modal_energy


class ModalResponse:
    """Exact absolute-time superposition; no integrator, Blender objects or audio mapping."""

    def __init__(self, modes, impulses, drives):
        self.modes = tuple(modes)
        self.impulses = tuple(tuple(events) for events in impulses)
        self.drives = tuple(tuple(events) for events in drives)
        if (
            not self.modes
            or len(self.impulses) != len(self.modes)
            or len(self.drives) != len(self.modes)
        ):
            raise ValueError("One excitation list per nonempty retained mode bank is required")
        for events in self.impulses:
            for start, impulse in events:
                if not isfinite(start) or start < 0 or not isfinite(impulse):
                    raise ValueError("Finite impulse and nonnegative start required")
        for events in self.drives:
            for start, frequency, phase, force in events:
                if (
                    not all(isfinite(v) for v in (start, frequency, phase, force))
                    or min(start, frequency) < 0
                ):
                    raise ValueError("Finite drive and nonnegative start/frequency required")
        self.state = None

    def step(self, time: float) -> ModalState:
        """Return SI modal coordinates and mechanical energy of retained modes."""
        if not isfinite(time) or time < 0:
            raise ValueError("Study time must be finite and nonnegative")
        positions, velocities = [], []
        for mode, impulses, drives in zip(self.modes, self.impulses, self.drives, strict=True):
            q = v = 0.0
            for start, impulse_ns in impulses:
                if time >= start:
                    dq, dv = free_response(mode, time - start, velocity=impulse_ns / mode.mass_kg)
                    q, v = q + dq, v + dv
            for start, frequency, phase, force_n in drives:
                if time >= start:
                    dq, dv = harmonic_response(mode, time - start, force_n, frequency, phase)
                    q, v = q + dq, v + dv
            positions.append(q)
            velocities.append(v)
        self.state = ModalState(
            time,
            tuple(positions),
            tuple(velocities),
            sum(
                modal_energy(mode, q, v)
                for mode, q, v in zip(self.modes, positions, velocities, strict=True)
            ),
        )
        return self.state

    def trace(self, times, *, use_numpy: bool | None = None):
        """Return mode-by-time displacement/velocity arrays, or lists without NumPy.

        NumPy evaluates the exact expressions in batches for offline audio; it does
        not change the model, introduce integration steps or drive a second clock.
        """
        np = None
        if use_numpy is not False:
            try:
                import numpy as np
            except ImportError:
                if use_numpy:
                    raise
        if np is None:
            states = [self.step(float(time)) for time in times]
            return (
                [[state.displacements[i] for state in states] for i in range(len(self.modes))],
                [[state.velocities[i] for state in states] for i in range(len(self.modes))],
            )
        times = np.asarray(times, dtype=float)
        if times.ndim != 1 or not np.all(np.isfinite(times)) or np.any(times < 0):
            raise ValueError("Trace times must be a finite nonnegative vector")
        positions = np.zeros((len(self.modes), len(times)))
        velocities = np.zeros_like(positions)
        for index, (mode, impulses, drives) in enumerate(
            zip(self.modes, self.impulses, self.drives, strict=True)
        ):

            def add_free(elapsed, q0, v0, active, mode=mode, index=index):
                beta, decay = mode.damped_omega, mode.decay
                a, b = q0, (v0 + decay * q0) / beta
                cosine, sine = np.cos(beta * elapsed), np.sin(beta * elapsed)
                envelope = np.exp(-decay * elapsed) * active
                positions[index] += envelope * (a * cosine + b * sine)
                velocities[index] += envelope * (
                    (-decay * a + beta * b) * cosine + (-decay * b - beta * a) * sine
                )

            for start, impulse_ns in impulses:
                elapsed = np.maximum(0.0, times - start)
                add_free(elapsed, 0.0, impulse_ns / mode.mass_kg, times >= start)
            for start, frequency, phase, force_n in drives:
                elapsed, active = np.maximum(0.0, times - start), times >= start
                omega = tau * frequency
                if mode.damping_ratio == 0 and frequency == mode.frequency_hz:
                    scale = force_n / (2 * mode.mass_kg * omega)
                    positions[index] += (
                        scale
                        * (
                            elapsed * np.sin(omega * elapsed + phase)
                            - np.sin(phase) * np.sin(omega * elapsed) / omega
                        )
                        * active
                    )
                    velocities[index] += (
                        scale
                        * (
                            np.sin(omega * elapsed + phase)
                            + omega * elapsed * np.cos(omega * elapsed + phase)
                            - np.sin(phase) * np.cos(omega * elapsed)
                        )
                        * active
                    )
                    continue
                amplitude = harmonic_amplitude(mode, force_n, frequency, phase)
                cosine, sine = np.cos(omega * elapsed), np.sin(omega * elapsed)
                positions[index] += (amplitude.real * cosine - amplitude.imag * sine) * active
                velocities[index] += (
                    -omega * (amplitude.real * sine + amplitude.imag * cosine) * active
                )
                add_free(elapsed, -amplitude.real, omega * amplitude.imag, active)
        return positions, velocities
