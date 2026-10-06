"""Dry reference plate: retained modes, finite contact patches, and virtual contact pickups."""

from copy import deepcopy
from math import isfinite

from spatial_sculptures.simulation.modal import ModalState
from spatial_sculptures.simulation.mode_bank import ModalResponse

from .config import StudyConfig

MODEL_CAPABILITIES = {
    "geometry": "flat rectangle; centred XY coordinates in metres",
    "material": "homogeneous isotropic E, density and Poisson ratio",
    "thickness": "uniform, in metres",
    "supports": "continuous simply supported edges; no local support springs",
    "mounting": "rigid uniform square patch, transverse force, no attached mass",
    "fluid": "dry only; water depth must be zero",
    "sensors": "ideal point contact velocity in m/s; not pressure",
}


def validate_model_support(config: StudyConfig) -> None:
    """Reject physical requests this reference cannot represent; never silently ignore them."""
    unsupported = []
    if config.profile.kind != "flat_rectangle":
        unsupported.append(f"profile.kind={config.profile.kind!r}")
    if config.profile.rise_m != 0 or config.profile.mesh_path is not None:
        unsupported.append("profile rise/imported mesh")
    if config.thickness_map is not None:
        unsupported.append("nonuniform thickness_map")
    if config.supports.kind != "simply_supported_edges" or config.supports.contacts:
        unsupported.append("local or alternative supports")
    if not isfinite(config.water.depth_m) or config.water.depth_m < 0:
        raise ValueError("Water depth must be finite and nonnegative")
    if config.water.depth_m > 0:
        unsupported.append(f"water.depth_m={config.water.depth_m:g}")
    for index, event in enumerate((*config.impulses, *config.drives), 1):
        mounting = event.mounting
        if mounting.added_mass_kg != 0 or mounting.stiffness_n_per_m is not None:
            unsupported.append(f"excitation {index}: attached mass/compliant mounting")
        if tuple(mounting.force_direction) not in ((0, 0, 1), (0, 0, -1)):
            unsupported.append(f"excitation {index}: non-transverse unit force_direction")
    if unsupported:
        raise ValueError("Dry analytical reference does not support: " + "; ".join(unsupported))


class PlateSimulation:
    """Exact absolute-time responses; Blender and exported audio use the same mode bank."""

    def __init__(self, config: StudyConfig) -> None:
        self.config = deepcopy(config)
        config = self.config
        validate_model_support(config)
        if not isinstance(config.modes_per_axis, int) or config.modes_per_axis < 1:
            raise ValueError("Mode count per axis must be a positive integer")
        if not isfinite(config.duration) or config.duration <= 0:
            raise ValueError("Duration must be finite and positive")
        if not isinstance(config.sample_rate, int) or config.sample_rate <= 0:
            raise ValueError("Sample rate must be a positive integer")
        if not config.pickups or any(
            len(point) != 2 or not all(isfinite(v) for v in point) for point in config.pickups
        ):
            raise ValueError("At least one finite XY contact pickup is required")
        if not isinstance(config.display_fps, int) or config.display_fps <= 0:
            raise ValueError("Display FPS must be a positive integer")
        if not isfinite(config.visual_time_scale) or config.visual_time_scale <= 0:
            raise ValueError("Visual time scale must be finite and positive")
        if not isfinite(config.visual_gain) or config.visual_gain <= 0:
            raise ValueError("Visual displacement gain must be finite and positive")
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
                        * event.mounting.force_direction[2]
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
                        * drive.mounting.force_direction[2]
                        * config.plate.patch_projection(m, n, drive.x, drive.y, drive.patch_width),
                    )
                    for drive in config.drives
                )
            )
        if any(not config.plate.contains(x, y) for x, y in config.pickups):
            raise ValueError("Contact pickups must lie on the reference plate")
        self.response = ModalResponse(self.modes, self.impulses, self.drives)
        self.state: ModalState | None = None

    def step(self, time: float) -> ModalState:
        """Evaluate the shared scalar modal response in physical seconds."""
        self.state = self.response.step(time)
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
        """Batch the shared response for offline audio, with the dependency-free fallback."""
        result = self.response.trace(times, use_numpy=use_numpy)
        self.state = self.response.state
        return result

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
