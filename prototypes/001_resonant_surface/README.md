# 001 — Resonant surface

## Concept

A shallow, water-filled metal basin forms a coupled physical/acoustic system.
Different regions of the vessel and water may vibrate and radiate differently,
inviting listeners to move around the sculpture and perceive its spatial behavior.

Potential physical flow:

```text
contact exciter
    ↓
metal basin
    ↓
water
    ↓
hydrophone
    ↓
signal processing
    ↓
another contact exciter
```

The long-term sculpture may use contact exciters, hydrophones, controlled water
droplets, air/bubbles, electronic feedback, frequency shifting, delay, and modal
resonances. The arrangement here is a starting proposition, not a fabrication
specification or a prediction of its sound.

## Current simulation status

There are now two runnable versions of this sculpture:

| Version | What it models | Listening output |
| --- | --- | --- |
| Original `build.py` | Artistic waves on water and sculpture geometry | Optional SuperCollider resonant-noise sketch driven by control values |
| [Numerical dry basin](dry/README.md) | Linear curved metal shell, local spring supports and housing masses | Model-derived contact-velocity WAV and synchronized Blender/MP4 |

```bash
python tools/run_dry_basin.py --profile contact_100hz --preview --view
python tools/run_dry_basin.py --profile contact_100hz --preview --render
```

The numerical version has no water. Its visible pickups represent metal contact
sensors rather than hydrophones. Profile, thickness, supports and mounting masses
affect its eigenmodes; a shared modal response generates audio and motion. The
[technical paper](../../docs/research/dry_basin/paper.md) documents this transition
and its verification limits. The original version is preserved below.
The saved dry profile passes numerical contact-response criteria through 100 Hz;
its listening filter passes through 80 Hz and reaches a stop band at 100 Hz.
Omitting `--profile` retains the original exploratory dry configuration.

Version 1 is a geometric prototype and a visual wave/interference simulation.
It is **not CFD, not FEM, and not a physically correct acoustic simulation**.
Default builds produce no audio or active feedback. There is no measured pressure
or fluid volume. An optional SuperCollider listening sketch can be driven by
control-rate simulated values.

## Simulation and consumers

```text
                 Python simulation (ResonantField)
                              │
                          FieldState
                              │
                  ┌───────────┴───────────┐
                  │                       │
                  ▼                       ▼
               Blender                   OSC
            visualization                 │
                                          ▼
                                   SuperCollider
                                          │
                                     synthesis
                                          │
                                    spatial audio
```

`simulation.py` is ordinary Python: equations, exciter influence, droplet impulses,
virtual hydrophone sampling, and state calculations. It imports neither `bpy` nor
the Blender helpers. `runtime.py` runs its wall clock and OSC outside Blender.
`visualization.py` contains the Blender timeline handler/live timer, mesh
deformation, and droplet updates. Materials, camera, lights, and
visible components remain presentation concerns.

```python
field = ResonantField(config)
state = field.step(time)   # absolute seconds, not dt
blender_adapter.update(state)
osc_transport.send_state(state)
value = field.sample(x, y)
```

`ResonantField` can run with no Blender installation or OSC server. The two
hydrophones genuinely sample displacement at `config.hydrophones`; those values
appear in `state.sensor_states` every step. `state.exciter_states` records the
current relative amplitudes and configured frequencies.

State metrics use a separate 8-ring × 32-segment equal-area sampling grid:
`total_energy` is **mean squared displacement in m²**, an artistic activity proxy,
not energy in joules. `max_displacement` is the sampled maximum absolute displacement
in metres, not an exact global maximum. `drop_impact` is a 0..1 envelope that decays
linearly for 0.12 s after each impact. No velocity, pressure conversion, dominant
frequency estimator, or material-energy calculation is implemented yet.

A future solver can expose comparable state and field sampling while consumers
retain their responsibilities. This is a design goal, not a FEM abstraction layer.

The procedural, slightly asymmetric metal vessel is approximately 1.4 m wide,
with a 5 mm Solidify shell and a subtle beveled rim. A 48-ring, 144-segment water
mesh contains 6,913 vertices. Three visible contact exciters sit underneath,
two hydrophones sit in the water, four slim supports raise the basin, and one
overhead arm supplies a falling droplet.

Each exciter contributes:

```text
r = distance((x, y), source)
k = 2π / wavelength
omega = 2π * frequency * time_scale
wave = amplitude * exp(-damping * r) * sin(k * r - omega * t + phase)
```

The water's displacement is the sum of these waves, scaled by `wave_amplitude`,
plus expanding drip ripples and optional subtle irregular modulation. A soft
edge taper fixes the mesh boundary. It does not compute reflections or basin
eigenmodes. Frequency and wavelength are independent visual controls: this model
has no material dispersion relation, metal/water coupling, or energy accounting.

Drips impact at 3.2 s, 6.4 s, and so on. A droplet falls during the preceding
0.55 s; its impact starts a decaying ripple. Each frame is recomputed from stored
undeformed coordinates, so scrubbing backwards and rendering isolated frames
produce the same field. Time is `(frame - frame_start) / fps`.

The 20-second baseline has 600 frames at 30 FPS. Its `time_scale=0.06` deliberately
slows visible phase motion; the displayed 59 Hz settings are not 59 Hz physical
water motion. Beat periods are also stretched by this factor.

In **live mode**, elapsed wall-clock time replaces frame time. The sculpture runs
continuously, including past 20 seconds, until its launcher stops. Virtual
hydrophones and OSC update in the independent Python worker even when Blender's
view is slow or its timeline is paused. The baseline worker ticks at 60 Hz;
Blender requests the latest snapshot at up to 30 Hz (15 in preview). The worker
uses actual elapsed time and skips missed deadlines without catch-up bursts.
SuperCollider owns audio-rate synthesis; this Python loop is control-rate.

## Configuration and experiments

Edit [config.py](config.py) to change animation, basin, water, exciters,
hydrophones, drip, rendering, runtime rates, or OSC. Values use metres, seconds,
Hz, and radians.
`default_config()` supplies independent deep copies of every section.

From the repository root:

```bash
python tools/run_blender.py 001_resonant_surface
python tools/run_blender.py 001_resonant_surface --experiment 001_three_exciters
python tools/run_blender.py 001_resonant_surface --experiment 002_close_frequencies
python tools/render.py 001_resonant_surface prototypes/001_resonant_surface/renders/drip.png --frame 105
```

For a lightweight first look:

```bash
python tools/run_blender.py 001_resonant_surface --preview --live --osc
```

Live motion starts automatically; leave timeline playback stopped. This command
owns both the Python worker and Blender; closing Blender shuts down its worker.
Use `--no-osc` to preview without networking. `--osc` enables OSC for this run
without editing configuration. See the [SuperCollider setup](supercollider/README.md)
to start the listening sketch.

For audio/control experiments without Blender:

```bash
python tools/run_simulation.py 001_resonant_surface --osc
python tools/run_simulation.py 001_resonant_surface --no-osc --duration 20
```

Ctrl+C stops the worker. `--experiment` also works here. Timeline rendering uses
the commands above without `--live`; live mode rejects frame/render arguments
because its clock keeps advancing. For a scripted external viewer, the runtime
can publish a latest-state file using `--state-file /tmp/resonant-state.json`.

Preview uses a 12-ring × 64-segment water mesh (769 vertices), a coarser basin,
solid material colors, and Workbench rendering at half resolution. Baseline
playback is 15 FPS with frame dropping. The sculpture's controls, wave equations,
drip timing in seconds, and sensor sampling are preserved; surface detail is lower.
Higher-frequency experiments keep their original FPS to avoid aliasing, so begin
with the baseline preview if the close-frequency experiment is too demanding.

Prepared samples in `sampling.py` cache source distances, attenuation, spatial
phases, drop radii and edge taper. NumPy batches these arrays when available;
cached standard-library math remains a supported fallback. The adapter writes
all coordinates with Blender's `foreach_set`, always starting from base Z.
Rebuild after changing static field parameters; amplitude and frequency can
vary per snapshot. Both paths reproduce the original scalar equation.

One local Blender 4.5.9 comparison (median of 12 updates, NumPy enabled):

| Water mesh | Original per-vertex update | Cached/bulk update |
| --- | --- | --- |
| Detailed, 6,913 vertices | 41.9 ms | 2.2 ms |
| Preview, 769 vertices | 5.5 ms | 0.55 ms |

The measurement includes mesh writes and mesh data updates, but excludes viewport
draws, rendering, and OSC. Results depend on hardware. The original scalar model
is retained for reference/equivalence tests. Sensor/metric state generation took
about 0.2–0.3 ms here, independently of mesh density.

The live launcher shares a single configuration snapshot and an atomic JSON
latest-state file in a temporary directory. It sends only `FieldState`, not
mesh coordinates. Blender reconstructs the analytic surface using the snapshot's
time and exciter controls; hydrophone values and metrics come from the worker.
Blender never sends OSC in live mode. Closing the launcher removes the exchange
directory. This small local exchange can later be replaced if real measurements
or a different solver require richer field data.

The close-frequency experiment uses 59.00, 59.08, and 59.17 Hz with a common
wavelength. It sets `time_scale=1`, a 60-second duration, and 240 FPS to sample the
fast carrier while showing slow envelopes. Live tick/display rates are also
240 Hz for this experiment. Pairwise beat periods are about 12.5,
11.1, and 5.9 seconds. Interactive playback may run slower than real time; the
timing refers to the animation clock. A full rendered animation is intentionally
outside this initial toolchain.

Experiments implement only `configure(config) -> config`. Geometry, animation,
and presentation continue through the same build. See the
[experiment notes](experiments/README.md) for adding variations.

Direct Blender execution also works from any directory:

```bash
blender --python /absolute/path/to/spatial-sculptures/prototypes/001_resonant_surface/build.py
```

In Blender's Python console, after the initial build:

```python
import importlib
prototype = importlib.import_module("prototypes.001_resonant_surface.build")
sculpture = prototype.build(prototype.load_config("002_close_frequencies"))
```

The named callback `resonant_surface_frame_change` and live timer
`resonant_surface_live_update` are removed and replaced at each build, including
callbacks left by re-executed/reloaded modules. `clear_scene()` removes tracked
research timers as well as tagged frame callbacks. Unrelated callbacks are retained.
Rebuild after reopening a saved `.blend` to restore the Python animation handler.

## Code map

| File | Responsibility |
| --- | --- |
| `build.py` | Import bootstrap, experiment selection, readable assembly, optional still render/save |
| `config.py` | Sculpture-specific editable parameters |
| `geometry.py` | Basin, water, exciters, hydrophones, supports, drip structure |
| `simulation.py` | Blender-free combined field, drip clock, virtual hydrophones, and FieldState |
| `sampling.py` | Cached fixed-position field sampling; optional NumPy batching |
| `runtime.py` | Independent wall-clock loop, state publication, and OSC output |
| `visualization.py` | Bulk mesh updates; timeline callback or live state consumer |
| `feedback.py` | Virtual hydrophone sampling and opt-in processing proposals |
| `scene.py` | Floor, camera, lights, world, timing, and render settings |
| `supercollider/` | Receiver, small SynthDef, entry point, and future spatial routing |

Reusable material/camera/primitive helpers and generic wave/sensor math live in
`src/spatial_sculptures/`. Assets, curated Blender scenes, and render outputs stay
alongside this prototype. No sculpture-specific geometry lives in the library.

## Optional OSC and SuperCollider

The reusable `src/spatial_sculptures/transport/` layer contains message paths and
a small standard-library OSC sender. Use `--osc` or set `OSC["enabled"] = True`
in `config.py`, then load the [SuperCollider entry point](supercollider/main.scd). Match `host`
and `port` to its language listener; default is `127.0.0.1:57120`. Audio-server
port 57110 is a separate endpoint.

`--no-osc` overrides the configured OSC setting for one run. Disabled transport
creates no socket and has no `python-osc` dependency. An enabled sender caps bundles
at `send_rate` per wall-clock second. UDP does not acknowledge delivery; these snapshots and impact
envelopes are not a reliable event log. Blender keeps working if a network error
disables optional output. In live mode the worker continues sending independently
of Blender display rate; in timeline mode OSC follows displayed frames.

Each bundle carries hydrophone amplitudes, each exciter's amplitude/frequency,
water activity/max displacement, drop impact, and simulation time. Indexes are
one-based in configuration order. Position and feedback addresses are reserved
for later. See the [SuperCollider README](supercollider/README.md) for the message
table, receiver-only use, preview start/stop, and validation status.

## Feedback scaffold

```text
simulation
    ↓
virtual hydrophone
    ↓
OSC → SuperCollider
    ↓
DSP / delay / filtering / frequency shifting
    ↓
OSC → virtual exciter
    ↓
simulation
```

`sample_field(config, time)` reads visual displacement at the two hydrophone
positions. `FeedbackRoute` and `apply_feedback(samples, routes)` propose bounded
control adjustments without mutating the scene or creating a loop. No default
route is enabled. A future experiment needs a pressure/control mapping, delay,
filtering, optional frequency shifting, and explicit gain limits before closing
the loop. Individual route bounds do not guarantee closed-loop stability.

Future `/feedback/exciter/N/amplitude` and `/feedback/exciter/N/frequency`
messages will require an explicit Python receiver and control mapping. None is
active yet. This mirrors real water/metal → hydrophone → SuperCollider → DSP →
amplifier → contact exciter → metal/water. The goal is to retain useful DSP while
replacing the virtual input with real hydrophone/audio-interface input later.

## Research questions

- How does water loading affect metal modes?
- Where should exciters be mounted?
- Where should hydrophones be located?
- Can slightly offset excitation frequencies produce slowly moving spatial interference?
- Can frequency-shifted feedback prevent the system from settling into one resonance?
- Can listeners physically perceive different modal regions while moving around the sculpture?

## Future progression

```text
1. artistic field simulation
2. virtual sensor feedback
3. SuperCollider integration
4. better numerical/modal model
5. FEM / coupled simulation
6. physical sculpture
7. measurement/model correction
```

Each stage should revise the previous assumptions using evidence. Preserve useful
parameter sets and observations rather than treating the first visual result as
a physical model.
