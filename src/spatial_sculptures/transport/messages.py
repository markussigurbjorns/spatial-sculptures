"""OSC address vocabulary. Indexes are one-based and follow configuration order."""

from collections.abc import Iterator

from spatial_sculptures.simulation.fields import FieldState

SIMULATION_TIME = "/simulation/time"
HYDROPHONE_AMPLITUDE = "/hydrophone/{index}/amplitude"
EXCITER_AMPLITUDE = "/exciter/{index}/amplitude"
EXCITER_FREQUENCY = "/exciter/{index}/frequency"
WATER_TOTAL_ENERGY = "/water/total_energy"
WATER_MAX_DISPLACEMENT = "/water/max_displacement"
DROP_IMPACT = "/drop/impact"

# Reserved vocabulary, not sent/received by the initial one-way implementation.
EXCITER_POSITION = "/exciter/{index}/position"
HYDROPHONE_POSITION = "/hydrophone/{index}/position"
FEEDBACK_EXCITER_AMPLITUDE = "/feedback/exciter/{index}/amplitude"
FEEDBACK_EXCITER_FREQUENCY = "/feedback/exciter/{index}/frequency"


def state_messages(state: FieldState) -> Iterator[tuple[str, float]]:
    """Map a snapshot to scalar messages; transport never evaluates the simulation."""
    yield SIMULATION_TIME, state.time
    for index, sensor in enumerate(state.sensor_states, start=1):
        yield HYDROPHONE_AMPLITUDE.format(index=index), sensor.amplitude
    for index, exciter in enumerate(state.exciter_states, start=1):
        yield EXCITER_AMPLITUDE.format(index=index), exciter.amplitude
        yield EXCITER_FREQUENCY.format(index=index), exciter.frequency
    yield WATER_TOTAL_ENERGY, state.total_energy
    yield WATER_MAX_DISPLACEMENT, state.max_displacement
    yield DROP_IMPACT, state.drop_impact
