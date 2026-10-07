"""Offline band selection, phase, physical level and absence of FFT wraparound."""

import unittest

try:
    import numpy as np

    from spatial_sculptures.audio.filtering import filter_zero_phase, lowpass_kernel
except ImportError:
    np = None


@unittest.skipIf(np is None, "Optional NumPy filtering unavailable")
class FilteringTests(unittest.TestCase):
    def test_passband_stopband_and_shared_physical_gain(self):
        kernel = lowpass_kernel(4096, 100)
        spectrum = np.abs(np.fft.rfft(kernel, 262144))
        f = np.fft.rfftfreq(262144, 1 / 4096)
        self.assertLess(float(np.max(np.abs(spectrum[f <= 80] - 1))), 1e-4)
        self.assertLess(float(spectrum[f >= 100].max()), 1e-4)
        t = np.arange(4096 * 2) / 4096
        signal = np.sin(2 * np.pi * 60 * t)
        filtered = filter_zero_phase(np.array([signal, 0.3 * signal]), kernel)
        np.testing.assert_allclose(filtered[1], 0.3 * filtered[0], atol=1e-13)
        np.testing.assert_allclose(filtered[0, 1500:-1500], signal[1500:-1500], atol=1e-4)

    def test_impulse_preserves_clock_without_circular_wrap(self):
        kernel = lowpass_kernel(1000, 100)
        signal = np.zeros(3000)
        signal[1500] = 1
        filtered = filter_zero_phase(signal, kernel)
        self.assertEqual(int(np.argmax(filtered)), 1500)
        np.testing.assert_allclose(filtered[:1000], 0, atol=1e-15)
        np.testing.assert_allclose(filtered[2000:], 0, atol=1e-15)
        edge = np.zeros(1000)
        edge[0] = 1
        result = filter_zero_phase(edge, kernel)
        np.testing.assert_allclose(result[-100:], 0, atol=1e-15)

    def test_invalid_filters_fail(self):
        for stop in (0, -1, float("nan"), 500):
            with self.assertRaises(ValueError):
                lowpass_kernel(1000, stop)
        with self.assertRaises(ValueError):
            filter_zero_phase([1, 2, 3], [0.1, 0.3, 0.6])


if __name__ == "__main__":
    unittest.main()
