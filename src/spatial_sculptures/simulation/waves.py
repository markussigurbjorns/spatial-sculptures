"""Artistic wave approximations, not solutions of coupled fluid/metal acoustics.

Coordinates and displacements are in metres, time in seconds, frequency in Hz.
The explicit time_scale slows phase motion for visual exploration; it changes the
apparent beat period too. Wavelength and frequency are independently chosen.
"""

from math import exp, hypot, sin, tau


def radial_wave(
    x: float,
    y: float,
    source_x: float,
    source_y: float,
    time: float,
    frequency: float,
    wavelength: float,
    phase: float,
    amplitude: float,
    damping: float,
    time_scale: float,
) -> float:
    """Evaluate amplitude * exp(-damping*r) * sin(k*r - omega*time + phase).

    This intentionally omits boundary reflections, dispersion, and material coupling.
    """
    if wavelength <= 0:
        raise ValueError("Wavelength must be positive")
    if damping < 0:
        raise ValueError("Damping must be non-negative")
    radius = hypot(x - source_x, y - source_y)
    k = tau / wavelength
    omega = tau * frequency * time_scale
    return amplitude * exp(-damping * radius) * sin(k * radius - omega * time + phase)


def expanding_ripple(
    x: float,
    y: float,
    source_x: float,
    source_y: float,
    age: float,
    *,
    amplitude: float,
    speed: float,
    wavelength: float = 0.075,
    width: float = 0.055,
    decay: float = 0.85,
) -> float:
    """Evaluate a decaying sinusoid within an expanding Gaussian ring.

    Negative ages represent impacts that have not happened. This is a visual impulse
    model, without conservation of energy or a capillary/gravity dispersion relation.
    """
    if wavelength <= 0 or width <= 0 or speed <= 0 or decay < 0:
        raise ValueError("Ripple wavelength, width, speed must be positive; decay >= 0")
    if age < 0:
        return 0.0
    radius = hypot(x - source_x, y - source_y)
    distance_to_front = radius - speed * age
    envelope = exp(-((distance_to_front / width) ** 2)) * exp(-decay * age)
    attack = 1.0 - exp(-age / 0.04)
    return amplitude * attack * envelope * sin(tau * distance_to_front / wavelength)
