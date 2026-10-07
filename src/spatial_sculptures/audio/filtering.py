"""Optional NumPy offline filters with explicit bandwidth and timing; no audio server."""

from math import ceil, isfinite, pi

import numpy as np


def lowpass_kernel(sample_rate: int, stop_hz: float, *, pass_fraction: float = 0.8):
    """Symmetric Kaiser-windowed sinc: pass band to 0.8*stop_hz, transition to stop_hz.

    Kaiser order/beta follow the empirical design equations documented by SciPy.
    Design at 90 dB, report an 80 dB stop-band target with margin for first-lobe
    deviations. This is an offline observation filter, not structural damping.
    """
    if (
        not isinstance(sample_rate, int)
        or sample_rate < 1
        or not isfinite(stop_hz)
        or not 0 < stop_hz < sample_rate / 2
        or not isfinite(pass_fraction)
        or not 0 < pass_fraction < 1
    ):
        raise ValueError("Positive rate and stop band below Nyquist required")
    width = (1 - pass_fraction) * stop_hz
    count = ceil((90 - 7.95) / (2.285 * 2 * pi * width / sample_rate)) + 1
    count += 1 - count % 2
    if count > 1_000_001:
        raise ValueError("Filter exceeds one million taps; use a higher stop frequency")
    offset = np.arange(count) - count // 2
    cutoff = (1 + pass_fraction) / 2 * stop_hz / sample_rate
    kernel = 2 * cutoff * np.sinc(2 * cutoff * offset) * np.kaiser(count, 0.1102 * (90 - 8.7))
    return kernel / kernel.sum()


def filter_zero_phase(signals, kernel, *, output_samples: int | None = None):
    """Linear FFT convolution with the FIR delay removed; retains the input time origin.

    Symmetric offline filtering is noncausal and may ring before an impact.
    Data before time zero are zero. Supply at least half a kernel of physical
    continuation after the requested end to avoid end-padding artifacts. There
    is no circular wrapping and no separate channel normalization.
    """
    signals, kernel = np.asarray(signals, dtype=float), np.asarray(kernel, dtype=float)
    if (
        signals.ndim < 1
        or not signals.shape[-1]
        or kernel.ndim != 1
        or not len(kernel)
        or len(kernel) % 2 != 1
        or not np.all(np.isfinite(signals))
        or not np.all(np.isfinite(kernel))
        or not np.allclose(kernel, kernel[::-1], rtol=1e-12, atol=1e-15)
    ):
        raise ValueError("Finite signals and an odd symmetric kernel required")
    count = signals.shape[-1] if output_samples is None else output_samples
    if not isinstance(count, int) or not 0 < count <= signals.shape[-1]:
        raise ValueError("Output length must be a positive integer within the input")
    size = 1 << (signals.shape[-1] + len(kernel) - 2).bit_length()
    convolution = np.fft.irfft(np.fft.rfft(signals, size) * np.fft.rfft(kernel, size), size)
    delay = len(kernel) // 2
    return convolution[..., delay : delay + count]
