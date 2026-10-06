"""Lightweight vocabulary for sampling a scalar field without Blender."""

from collections.abc import Callable

# A displacement field f(x_metres, y_metres, time_seconds) -> metres.
ScalarField = Callable[[float, float, float], float]
