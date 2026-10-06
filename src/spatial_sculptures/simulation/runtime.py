"""An ordinary-Python wall-clock loop; no visualization or network dependencies."""

import time
from collections.abc import Callable
from math import isfinite
from threading import Event

from .fields import FieldState


def run_clock(
    step: Callable[[float], FieldState],
    publish: Callable[[FieldState], None],
    *,
    tick_rate: float = 60.0,
    duration: float | None = None,
    stop: Event | None = None,
) -> None:
    """Step at elapsed monotonic time, skipping missed deadlines without a catch-up burst.

    This is a control-rate research loop, not a hard real-time audio scheduler.
    Slow consumers belong in other processes; publish should only send a small snapshot.
    """
    if not isfinite(tick_rate) or tick_rate <= 0:
        raise ValueError("Tick rate must be finite and positive")
    if duration is not None and (not isfinite(duration) or duration <= 0):
        raise ValueError("Duration must be finite and positive")
    stop = Event() if stop is None else stop
    start = time.monotonic()
    deadline = start
    period = 1.0 / tick_rate
    while not stop.is_set():
        now = time.monotonic()
        elapsed = now - start
        if duration is not None and elapsed >= duration:
            return
        publish(step(elapsed))
        deadline += period
        now = time.monotonic()
        if deadline < now:
            deadline = now + period
        delay = deadline - now
        if duration is not None:
            delay = min(delay, max(0.0, start + duration - now))
        stop.wait(delay)
