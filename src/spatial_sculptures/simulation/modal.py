"""Exact linear, underdamped modal responses in SI units, independent of any geometry.

Mode shapes and force projections belong to the model that supplies the modes.
These helpers do not compute eigenmodes or model fluid/acoustic radiation.
"""

from dataclasses import dataclass
from math import cos, exp, isfinite, sin, sqrt, tau


@dataclass(frozen=True)
class Mode:
    """One mode with a consistent shape normalization and associated modal mass."""

    name: str
    frequency_hz: float
    mass_kg: float
    damping_ratio: float

    def __post_init__(self) -> None:
        if not all(isfinite(v) for v in (self.frequency_hz, self.mass_kg, self.damping_ratio)):
            raise ValueError("Modal parameters must be finite")
        if self.frequency_hz <= 0 or self.mass_kg <= 0 or not 0 <= self.damping_ratio < 1:
            raise ValueError("Positive frequency/mass and 0 <= damping ratio < 1 are required")

    @property
    def omega(self) -> float:
        """Undamped angular frequency, rad/s."""
        return tau * self.frequency_hz

    @property
    def decay(self) -> float:
        """Exponential amplitude decay rate, 1/s."""
        return self.damping_ratio * self.omega

    @property
    def damped_omega(self) -> float:
        """Angular frequency of the free response, rad/s."""
        return self.omega * sqrt(1 - self.damping_ratio**2)


def free_response(
    mode: Mode, time: float, displacement: float = 0.0, velocity: float = 0.0
) -> tuple[float, float]:
    """Return displacement/velocity after time seconds from given initial conditions."""
    if not isfinite(time) or time < 0:
        raise ValueError("Elapsed response time must be finite and nonnegative")
    decay, omega = mode.decay, mode.damped_omega
    a = displacement
    b = (velocity + decay * displacement) / omega
    cosine, sine = cos(omega * time), sin(omega * time)
    envelope = exp(-decay * time)
    q = envelope * (a * cosine + b * sine)
    v = envelope * ((-decay * a + omega * b) * cosine + (-decay * b - omega * a) * sine)
    return q, v


def harmonic_amplitude(
    mode: Mode, force_n: float, frequency_hz: float, phase: float = 0.0
) -> complex:
    """Complex steady-state displacement for F*cos(2*pi*f*t + phase), in metres.

    The resonant undamped case has no bounded steady state and raises ValueError.
    harmonic_response below handles its finite-time response separately.
    """
    if not all(isfinite(v) for v in (force_n, frequency_hz, phase)) or frequency_hz < 0:
        raise ValueError("Harmonic drive must be finite with frequency >= 0")
    omega = tau * frequency_hz
    denominator = complex(mode.omega**2 - omega**2, 2 * mode.decay * omega)
    if denominator == 0:
        raise ValueError("An undamped resonant drive has no bounded steady state")
    return force_n / mode.mass_kg * complex(cos(phase), sin(phase)) / denominator


def harmonic_response(
    mode: Mode, time: float, force_n: float, frequency_hz: float, phase: float = 0.0
) -> tuple[float, float]:
    """Exact switched-on harmonic response with zero displacement/velocity at time zero."""
    if not isfinite(time) or time < 0:
        raise ValueError("Elapsed response time must be finite and nonnegative")
    omega = tau * frequency_hz
    if mode.damping_ratio == 0 and frequency_hz == mode.frequency_hz:
        if not isfinite(force_n) or not isfinite(phase):
            raise ValueError("Force and phase must be finite")
        scale = force_n / (2 * mode.mass_kg * omega)
        q = scale * (time * sin(omega * time + phase) - sin(phase) * sin(omega * time) / omega)
        v = scale * (
            sin(omega * time + phase)
            + omega * time * cos(omega * time + phase)
            - sin(phase) * cos(omega * time)
        )
        return q, v
    amplitude = harmonic_amplitude(mode, force_n, frequency_hz, phase)
    q = amplitude.real * cos(omega * time) - amplitude.imag * sin(omega * time)
    v = -omega * (amplitude.real * sin(omega * time) + amplitude.imag * cos(omega * time))
    transient_q, transient_v = free_response(mode, time, -amplitude.real, omega * amplitude.imag)
    return q + transient_q, v + transient_v


def modal_energy(mode: Mode, displacement: float, velocity: float) -> float:
    """Mechanical energy of this retained mode, joules (kinetic plus elastic)."""
    return 0.5 * mode.mass_kg * (velocity**2 + mode.omega**2 * displacement**2)


@dataclass(frozen=True)
class ModalState:
    """State of a retained linear mode bank; energy is explicitly in joules."""

    time: float
    displacements: tuple[float, ...]
    velocities: tuple[float, ...]
    energy_joules: float
