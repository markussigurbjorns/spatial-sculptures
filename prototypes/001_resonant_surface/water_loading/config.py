"""Prototype water-loading study settings; the dry playback configuration is separate."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class LoadingStudyConfig:
    depths_m: tuple[float, ...] = (0.0, 0.01, 0.03, 0.065)
    density_kg_m3: float = 1000.0
    integration_order: int = 5
    integration_refinement: int = 2
    # The baseline's 18x18 structure/128-mode bank is specified by contact_200hz.
    # Its DRY certificate does not certify the loaded configurations.

    def __post_init__(self):
        if (
            not self.depths_m
            or any(not isfinite(d) or d < 0 for d in self.depths_m)
            or len(set(self.depths_m)) != len(self.depths_m)
        ):
            raise ValueError("Distinct finite nonnegative water depths required")
        if not isfinite(self.density_kg_m3) or self.density_kg_m3 <= 0:
            raise ValueError("Water density must be finite and positive")
        for name, minimum in (("integration_order", 4), ("integration_refinement", 1)):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
