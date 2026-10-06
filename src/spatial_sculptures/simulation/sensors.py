"""Virtual point sensors shared by simulations; these do not predict hydrophone pressure."""

from dataclasses import dataclass

from .fields import ScalarField


@dataclass(frozen=True)
class VirtualSensor:
    """A named XY sample position with a simple measurement gain."""

    name: str
    x: float
    y: float
    gain: float = 1.0

    def sample(self, field: ScalarField, time: float) -> float:
        """Sample the field. Units remain those of the field, scaled by gain."""
        return self.gain * field(self.x, self.y, time)
