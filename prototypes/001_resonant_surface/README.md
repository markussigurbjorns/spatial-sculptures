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

Version 1 is a geometric prototype and a visual wave/interference simulation.
It is **not CFD, not FEM, and not a physically correct acoustic simulation**.
There is no emitted audio, measured pressure, fluid volume, or active feedback.

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

## Configuration and experiments

Edit [config.py](config.py) to change animation, basin, water, exciters,
hydrophones, drip, or rendering. Values use metres, seconds, Hz, and radians.
`default_config()` supplies independent deep copies of every section.

From the repository root:

```bash
python tools/run_blender.py 001_resonant_surface
python tools/run_blender.py 001_resonant_surface --experiment 001_three_exciters
python tools/run_blender.py 001_resonant_surface --experiment 002_close_frequencies
python tools/render.py 001_resonant_surface prototypes/001_resonant_surface/renders/drip.png --frame 105
```

The close-frequency experiment uses 59.00, 59.08, and 59.17 Hz with a common
wavelength. It sets `time_scale=1`, a 60-second duration, and 240 FPS to sample the
fast carrier while showing slow envelopes. Pairwise beat periods are about 12.5,
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

The named callback `resonant_surface_frame_change` is removed and replaced at
each build, including callbacks left by re-executed scripts. `clear_scene()` also
removes tagged research callbacks. Unrelated add-on callbacks are retained.
Rebuild after reopening a saved `.blend` to restore the Python animation handler.

## Code map

| File | Responsibility |
| --- | --- |
| `build.py` | Import bootstrap, experiment selection, readable assembly, optional still render/save |
| `config.py` | Sculpture-specific editable parameters |
| `geometry.py` | Basin, water, exciters, hydrophones, supports, drip structure |
| `simulation.py` | Combined displacement, drip clock, deterministic frame updates |
| `feedback.py` | Virtual hydrophone sampling and opt-in processing proposals |
| `scene.py` | Floor, camera, lights, world, timing, and render settings |

Reusable material/camera/primitive helpers and generic wave/sensor math live in
`src/spatial_sculptures/`. Assets, curated Blender scenes, and render outputs stay
alongside this prototype. No sculpture-specific geometry lives in the library.

## Feedback scaffold

```text
water/metal field
    ↓
virtual hydrophone
    ↓
processing
    ↓
another exciter
```

`sample_field(config, time)` reads visual displacement at the two hydrophone
positions. `FeedbackRoute` and `apply_feedback(samples, routes)` propose bounded
control adjustments without mutating the scene or creating a loop. No default
route is enabled. A future experiment needs a pressure/control mapping, delay,
filtering, optional frequency shifting, and explicit gain limits before closing
the loop. Individual route bounds do not guarantee closed-loop stability.

## Research questions

- How does water loading affect metal modes?
- Where should exciters be mounted?
- Where should hydrophones be located?
- Can slightly offset excitation frequencies produce slowly moving spatial interference?
- Can frequency-shifted feedback prevent the system from settling into one resonance?
- Can listeners physically perceive different modal regions while moving around the sculpture?

## Future progression

```text
1. artistic Blender simulation
2. simulated feedback system
3. numerical/modal analysis
4. FEM / coupled physical simulation
5. physical prototype
6. measurement and model correction
```

Each stage should revise the previous assumptions using evidence. Preserve useful
parameter sets and observations rather than treating the first visual result as
a physical model.
