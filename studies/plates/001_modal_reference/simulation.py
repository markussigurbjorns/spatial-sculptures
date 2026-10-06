"""Dry reference plate: retained modes, finite contact patches, and virtual contact pickups."""

from copy import deepcopy
from math import isfinite, tau

from spatial_sculptures.simulation.modal import (
    ModalState,
    free_response,
    harmonic_amplitude,
    harmonic_response,
    modal_energy,
)

from .config import StudyConfig


class PlateSimulation:
    """Exact absolute-time responses; Blender and exported audio use the same mode bank."""

    def __init__(self, config: StudyConfig) -> None:
        self.config = deepcopy(config)
        config = self.config
        if not isinstance(config.modes_per_axis, int) or config.modes_per_axis < 1:
            raise ValueError("Mode count per axis must be a positive integer")
        if not isfinite(config.duration) or config.duration <= 0:
            raise ValueError("Duration must be finite and positive")
        if not isinstance(config.sample_rate, int) or config.sample_rate <= 0:
            raise ValueError("Sample rate must be a positive integer")
        for event in config.impulses:
            if not isfinite(event.time) or event.time < 0 or not isfinite(event.impulse_ns):
                raise ValueError("Impulse time must be nonnegative and impulse finite")
        for drive in config.drives:
            values = (drive.start, drive.frequency_hz, drive.force_n, drive.phase)
            if not all(isfinite(v) for v in values) or drive.start < 0 or drive.frequency_hz < 0:
                raise ValueError("Drive parameters must be finite; time/frequency nonnegative")
        self.indices = tuple(
            (m, n)
            for m in range(1, config.modes_per_axis + 1)
            for n in range(1, config.modes_per_axis + 1)
        )
        self.modes = tuple(config.plate.mode(m, n, config.damping_ratio) for m, n in self.indices)
        self.impulses = []
        self.drives = []
        for m, n in self.indices:
            self.impulses.append(
                tuple(
                    (
                        event.time,
                        event.impulse_ns
                        * config.plate.patch_projection(m, n, event.x, event.y, event.patch_width),
                    )
                    for event in config.impulses
                )
            )
            self.drives.append(
                tuple(
                    (
                        drive.start,
                        drive.frequency_hz,
                        drive.phase,
                        drive.force_n
                        * config.plate.patch_projection(m, n, drive.x, drive.y, drive.patch_width),
                    )
                    for drive in config.drives
                )
            )
        if any(not config.plate.contains(x, y) for x, y in config.pickups):
            raise ValueError("Contact pickups must lie on the reference plate")
        self.state: ModalState | None = None

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

    def weights(self, x: float, y: float) -> tuple[float, ...]:
        """Mode shapes at a point; prepare once for fixed mesh or pickup positions."""
        return tuple(self.config.plate.shape(m, n, x, y) for m, n in self.indices)

    def sample(self, x: float, y: float, state: ModalState | None = None) -> float:
        """Transverse plate displacement in metres; not water pressure."""
        state = state or self.state or self.step(0.0)
        return sum(w * q for w, q in zip(self.weights(x, y), state.displacements, strict=True))

    def sample_velocity(self, x: float, y: float, state: ModalState | None = None) -> float:
        """Ideal point contact-pickup velocity in m/s, without acoustic radiation."""
        state = state or self.state or self.step(0.0)
        return sum(w * v for w, v in zip(self.weights(x, y), state.velocities, strict=True))

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

    def pickup_velocities(self, velocities):
        """Reconstruct point pickup velocities from the same modal coordinates."""
        weights = [self.weights(x, y) for x, y in self.config.pickups]
        if hasattr(velocities, "shape"):
            import numpy as np

            return np.asarray(weights) @ velocities
        return [
            [
                sum(w * velocities[i][j] for i, w in enumerate(row))
                for j in range(len(velocities[0]))
            ]
            for row in weights
        ]
