# Dynamic gravity/capillary surface

This stage adds independently evolving water elevation to the existing metal
shell. A Neumann potential solves wall and water-surface flux together, producing
reciprocal fluid inertia. Gravity and surface tension supply water restoring
energy. The simulation is ordinary Python; Blender receives arrays.

```text
linear shell + dynamic free surface
                 │
            q(t), v(t), a(t)
                 │
      ┌──────────┼─────────────┐
      ▼          ▼             ▼
 metal motion  water level  probe pressure (Pa)
      └────┬─────┘             │
           ▼                   ▼
        Blender           WAV / future SC DSP
```

From the repository root, with NumPy installed:

```bash
python tools/run_free_surface.py --preview --view
python tools/run_free_surface.py --preview --render
```

The first command opens Blender; Space starts synchronized picture and audio.
The second uses Blender and FFmpeg to create `renders/free_surface/free_surface.mp4`.
Omit the final option to export only audio and simulation frames. `--duration 2`
exports a shorter run. `BLENDER_BIN` and `FFMPEG_BIN` override executable names.
Playback requires no SuperCollider, SciPy, NGSolve or OSC server.

Outputs include `hydrophones.wav`, raw/filtered pressure in `pressure.npz`,
`frames.npz`, `configuration.json` and a provenance `report.json`. Pressure is
`p'=-rho*chi_ddot+rho*g*mean(eta)`; both terms are retained. Both hydrophones use
one listening gain. The WAV is model pressure, without a microphone response,
acoustic radiation, pitch shift or additional synthesis. Slow water modes may
be below hearing; the pressure response also includes faster metal modes.

The current listening filter passes 0–64 Hz and reaches its stop band at 80 Hz.
The selected model passes separate numerical observation gates through 80 Hz;
see [the recorded results](../../../docs/research/free_surface/validation.md).
It is an offline zero-phase filter and may ring before pulse edges. SI raw data
remain available. Video uses one physical second per playback second and
exposure-averaged displacement, visibly magnified by the dry presentation gain.
Full-frequency pressure audio cannot be reconstructed from 30 fps video frames.
Higher retained modes also contribute to frame states, without a validation
claim for individual modes or observations above 80 Hz.

## Assumptions and configuration

[config.py](config.py) contains provisional 65 mm water depth, 1000 kg/m³ density,
9.81 m/s² gravity, 0.072 N/m tension, hydrophone coordinates/depths, prescribed
surface damping, polynomial degrees and retained-mode count. Metal profile,
thickness, supports and exciter mounting still come from the dry
`contact_200hz` reference profile. The force is a finite 10 ms mechanical pulse,
not a modeled droplet impact.

Water volume is conserved at linear order: mean elevation follows integrated
wall flux; independent wave shapes have zero mean. The capillary edge uses an
ideal natural zero-normal-slope condition. The footprint and fluid floor are
the resting graph mid-surface, without a physical contact-line/meniscus law.

The shell equilibrium and stiffness remain frozen at the dry reference.
Hydrostatic deformation, prestress and elastogravity wall-traction corrections
are absent. This is a useful **supported-vessel, small-amplitude approximation**,
not a gravity-consistent free-body model or a calibrated physical basin.
Viscosity, breaking waves, compressibility, drop forcing and radiation are absent.
Damping ratios are assumptions rather than predictions.

The [research note](../../../docs/research/free_surface/study.md) records the
equations, primary references and numerical scope. The selected bank uses
18×18 shell cells, 256 dry modes, potential degree 12/3, elevation degree 10,
and 128 retained coupled modes. The water modes consume part of that count.
The lowest water modes are around 0.34 and 0.42 Hz; this differs from the prior
pressure-release surface, which had no gravity/capillary resonances.

## Rebuild numerical evidence

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/validate_free_surface.py --external
```

`--external` additionally needs NGSolve and checks a rigid rectangular cell's
mass, pressure and gravity/capillary frequencies independently. The validation
tool checks successive surface, potential, integration and structural
refinements, observation transfer paths and filtered finite pulses. It exports
a portable bank only when required gates pass. Source/artifact hashes prevent
stale results from being presented as validated playback. Changing physical
assumptions requires recomputing and checking a model; it does not automatically
inherit this saved configuration's evidence.

The earlier `wet/`, `water_loading/`, `dry/` and artistic implementations remain
available as reproducible comparison stages. Their original evidence is preserved.
