# Spatial sculptures

**Can matter and space themselves become the spatial-audio system?**

This repository is an experimental research environment for sculptures in which
spatial perception emerges from physical materials and acoustic processes rather
than conventional speaker panning. Software supports experiments; it should not
predetermine their outcomes.

Research may involve water, air, resonant metal, ceramic cavities, membranes,
strings, droplets, mechanical impulses, acoustic feedback, modal behavior, and
spatial perception. Blender is the first visualization environment. Numerical
simulation, FEM/modal analysis, SuperCollider, measurements, recordings,
fabrication, and hardware control can be added as concrete experiments need them.

## Layout and boundaries

| Location | Purpose |
| --- | --- |
| `src/spatial_sculptures/` | Reusable Blender helpers, wave math, field/sensor vocabulary, and future audio tools |
| `prototypes/` | Complete sculpture ideas, each with its own configuration, geometry, experiments, assets, and outputs |
| `studies/` | Isolated investigations into physical/acoustic phenomena that may inform several sculptures |
| `tools/` | Small command-line launch, still-render, and mesh-export helpers |
| `data/` | Local measurements, recordings, and FEM results |
| `docs/` | Concepts, fabrication notes, and research references |

Keep basin dimensions, sensor placement, drip design, and scene composition in
the prototype. Move a function into `src/` when it already makes sense independently
of one sculpture. There is no prototype registry or configuration framework.

The first sculpture is [001_resonant_surface](prototypes/001_resonant_surface/README.md):
a shallow metal basin with water, underside contact exciters, hydrophones, and
controlled dripping. Its initial animation is an **artistic wave/interference
approximation**, not CFD, FEM, or calibrated fluid/acoustic simulation.

## Run the first prototype

Install Blender separately and make `blender` available on PATH. The initial
prototype targets Blender 4.x or newer with bundled Python 3.11+, and has been
checked in Blender 4.5.9. It uses only Blender and Python's standard library;
installing this Python package into Blender is unnecessary.

```bash
python tools/run_blender.py 001_resonant_surface
python tools/run_blender.py 001_resonant_surface --background
python tools/run_blender.py 001_resonant_surface --experiment 002_close_frequencies
```

The first command opens Blender; press Space in the timeline to play. The
background command builds and exits. Set `BLENDER_BIN` to an executable name or
path to select another installation:

```bash
BLENDER_BIN=/path/to/blender python tools/run_blender.py 001_resonant_surface
```

Launch paths are resolved relative to the repository, so an absolute invocation
of `tools/run_blender.py` works from any working directory. Blender starts with
factory settings for reproducibility. The launcher returns Blender's exit status
and makes script exceptions produce a nonzero exit code.

Render a single frame or explicitly save a generated scene:

```bash
python tools/render.py 001_resonant_surface prototypes/001_resonant_surface/renders/frame_100.png --frame 100
python tools/run_blender.py 001_resonant_surface --background --save-blend prototypes/001_resonant_surface/blender/generated/baseline.blend
```

Runtime frame handlers are Python session state. Reopening a saved `.blend` alone
does not reinstall the simulation; rebuild with the entry script to animate it.
Saved scenes remain useful as geometry/presentation snapshots.

## Ordinary Python development

Use Python 3.11+ for tooling and pure field/sensor experiments. Runtime
dependencies are empty; development tools are optional.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
pytest
python -m compileall -q src prototypes tools tests
```

The numerical and launcher tests also run without pytest or package installation:

```bash
PYTHONPATH=src python -m unittest discover -s tests
blender --background --factory-startup --python-exit-code 1 --python tests/validate_blender.py
```

The Blender check builds twice, checks callback and object counts, scrubs frames
backwards, and verifies droplet timing and stored base coordinates. These checks
are software validation. The parameter variations in `experiments/` are artistic
and research investigations, not unit tests.

## Adding another sculpture

Create `prototypes/002_your_idea/` with a readable `build.py`, explicit
configuration, and a README recording the question and assumptions. Let its
geometry and simulation remain local. Reuse only appropriate helpers from `src/`.
Follow the first prototype's file-relative import bootstrap for direct Blender
execution; relative imports avoid collisions between generic module names such
as `geometry` and `simulation`.

Record experiment changes in small Python modules, and keep parameter sets
independent. Document measured units, calibration, and provenance when physical
data becomes available. Introduce NumPy/SciPy or a solver as an optional dependency
only when an actual study calls for it.

## Outputs and version control

Renders and raw `data/{measurements,recordings,fem}/` contents are ignored, with
`.gitkeep` placeholders retained. Automatic `.blend` outputs belong in each
prototype's ignored `blender/generated/` directory. Selected curated `.blend`
scenes elsewhere can be intentionally committed; `.blend` is not globally
ignored. Blender backup files and Python build/cache files are ignored.

Treat mesh exports as geometry studies. STL contains no units metadata; the export
helper writes metre coordinates. Check scale, watertightness, material, and
manufacturing constraints when preparing actual fabrication files.
