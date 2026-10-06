"""Solve/cache the dry basin and export synchronized model audio and visuals."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def radial_mesh(surface, rings: int, segments: int):
    """Prototype visualization sampling, separate from the structural spline discretization."""
    import numpy as np

    xy = [(0.0, 0.0)] + [
        (
            surface.radius_x * ring / rings * math.cos(2 * math.pi * j / segments),
            surface.radius_y * ring / rings * math.sin(2 * math.pi * j / segments),
        )
        for ring in range(1, rings + 1)
        for j in range(segments)
    ]
    x, y = np.array(xy).T
    vertices = np.column_stack((x, y, surface.geometry(x, y)[0]))
    faces = [(0, 1 + j, 1 + (j + 1) % segments) for j in range(segments)]
    for ring in range(1, rings):
        inner = 1 + (ring - 1) * segments
        outer = inner + segments
        faces.extend(
            (inner + j, outer + j, outer + (j + 1) % segments, inner + (j + 1) % segments)
            for j in range(segments)
        )
    return vertices, faces


def export_run(config, output: Path, *, preview=False, inspection_speed=1.0, rebuild=False):
    """Sample one modal response for audio and all visual frames; Blender receives arrays only."""
    import numpy as np

    from spatial_sculptures.audio.synthesis import write_pickup_wav

    model = importlib.import_module("prototypes.001_resonant_surface.dry.model")
    config = deepcopy(config)
    model.validate_config(config)
    if not math.isfinite(inspection_speed) or not 0 < inspection_speed <= 1:
        raise ValueError("Inspection speed must lie in (0,1]")
    requested_duration = config.duration
    frame_count = max(1, round(config.duration / inspection_speed * config.fps))
    config.duration = frame_count * inspection_speed / config.fps
    if preview:
        config.resolution, config.rings, config.segments = (480, 360), 8, 48
    modes, cache_path, reused = model.get_modes(
        config, ROOT / "data/fem/001_resonant_surface", rebuild=rebuild
    )
    simulation = model.DryBasinSimulation(config, modes)
    frequency_max = max(
        max(modes.frequencies),
        max(e.frequency_hz for e in config.exciters if e.force_n)
        if any(e.force_n for e in config.exciters)
        else 0,
    )
    if frequency_max >= config.sample_rate / 2:
        raise ValueError("Audio sample rate must exceed twice every retained/drive frequency")
    output.mkdir(parents=True, exist_ok=True)
    configuration = output / "configuration.json"
    configuration.write_text(json.dumps(asdict(config), indent=2, allow_nan=False))
    sample_count = max(1, round(config.duration * config.sample_rate))
    audio_times = np.arange(sample_count) / config.sample_rate
    _, velocities = simulation.trace(audio_times)
    channels = simulation.pickup_velocities(velocities)
    audio_path = output / "contact_pickups.wav"
    gain = write_pickup_wav(audio_path, channels, config.sample_rate)
    frame_times = np.arange(frame_count) * inspection_speed / config.fps
    positions, frame_velocities = simulation.trace(frame_times)
    energies = np.sum(
        0.5
        * np.asarray([m.mass_kg for m in simulation.modes])[:, None]
        * (
            frame_velocities**2
            + np.asarray([m.omega for m in simulation.modes])[:, None] ** 2 * positions**2
        ),
        axis=0,
    )
    visual_positions = positions
    exposure_samples = 1
    if config.exposure_fraction:
        span = config.exposure_fraction * inspection_speed / config.fps
        exposure_samples = max(config.exposure_samples, math.ceil(4 * frequency_max * span))
        sample_times = (
            frame_times[:, None] + (np.arange(exposure_samples) + 0.5) * span / exposure_samples
        )
        visual_positions = (
            simulation.trace(sample_times.ravel())[0]
            .reshape(len(simulation.modes), frame_count, exposure_samples)
            .mean(axis=2)
        )
    vertices, faces = radial_mesh(config.surface, config.rings, config.segments)
    weights = modes.weights(vertices[:, 0], vertices[:, 1])
    displacements = np.einsum("pcm,mf->fpc", weights, visual_positions).astype(np.float32)
    marker_xy = np.array([(e.patch.x, e.patch.y) for e in config.exciters] + list(config.pickups))
    marker_reference = np.column_stack((marker_xy, config.surface.geometry(*marker_xy.T)[0]))
    marker_displacements = np.einsum(
        "pcm,mf->fpc", modes.weights(*marker_xy.T), visual_positions
    ).astype(np.float32)
    support_xy = np.array([(s.patch.x, s.patch.y) for s in config.supports]).reshape(-1, 2)
    support_reference = np.column_stack(
        (
            support_xy,
            config.surface.geometry(*support_xy.T)[0],
        )
    )
    bundle = output / "frames.npz"
    metadata = {
        "frame_count": frame_count,
        "fps": config.fps,
        "physical_seconds_per_visual_second": inspection_speed,
        "visual_gain": config.visual_gain,
        "audio_path": str(audio_path.resolve()),
        "exposure_fraction": config.exposure_fraction,
        "exposure_samples": exposure_samples,
        "presentation": "exposure-averaged displacement, not full optical motion blur"
        if config.exposure_fraction
        else "instantaneous sampled displacement; high-frequency motion aliases at video rates",
    }
    np.savez_compressed(
        bundle,
        vertices=vertices,
        face_sizes=np.array([len(f) for f in faces]),
        face_indices=np.array([i for f in faces for i in f]),
        displacements=displacements,
        marker_reference=marker_reference,
        marker_displacements=marker_displacements,
        support_reference=support_reference,
        times=frame_times,
        energies=energies,
        metadata=json.dumps(metadata),
    )
    source_names = (
        "src/spatial_sculptures/simulation/mode_bank.py",
        "src/spatial_sculptures/audio/synthesis.py",
        "prototypes/001_resonant_surface/dry/config.py",
        "prototypes/001_resonant_surface/dry/model.py",
        "prototypes/001_resonant_surface/dry/build.py",
        "tools/run_dry_basin.py",
    )
    report = {
        "model": (
            "linear dry Kirchhoff-Love graph shell; compliant patch supports; rigid attached masses"
        ),
        "parameters": asdict(config),
        "requested_duration_s": requested_duration,
        "physical_duration_s": config.duration,
        "visual_duration_s": frame_count / config.fps,
        "frame_count": frame_count,
        "audio_samples": sample_count,
        "audio_gain_per_m_per_s": gain,
        "mode_frequencies_hz": modes.frequencies.tolist(),
        "modal_masses_kg": modes.masses.tolist(),
        "cache_key": modes.metadata["cache_key"],
        "cache_path": str(cache_path.relative_to(ROOT)),
        "cache_reused": reused,
        "diagnostics": modes.metadata["diagnostics"],
        "structural_provenance": modes.metadata["source_sha256"],
        "source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_names
        },
        "initial_retained_energy_j": simulation.step(0).energy_joules,
        "final_retained_energy_j": simulation.step(config.duration).energy_joules,
        "pickup_peak_velocity_m_per_s": np.max(np.abs(channels), axis=1).tolist(),
        "pickup_units": (
            "global vertical contact velocity m/s; not hydrophone pressure or radiated sound"
        ),
        "presentation": metadata,
        "measurements": "none; all supports/masses/damping and profile are provisional",
        "validation": (
            "plate verification and separate shell refinement; "
            "no specimen/pressure/radiation validation"
        ),
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    return report, bundle, configuration


def blender_command(bundle: Path, configuration: Path, output: Path, *, render=False):
    """Invoke the visualization adapter; no structural solve runs in Blender."""
    command = [os.environ.get("BLENDER_BIN", "blender"), "--factory-startup"]
    if render:
        command.append("--background")
    command += [
        "--python-exit-code",
        "1",
        "--python",
        str(ROOT / "prototypes/001_resonant_surface/dry/build.py"),
        "--",
        "--bundle",
        str(bundle.resolve()),
        "--config",
        str(configuration.resolve()),
    ]
    if render:
        command += ["--render-directory", str((output / "frames").resolve())]
    return command


def mux_command(output: Path, fps: int, duration: float):
    """Encode normal-speed frames and model-derived WAV with a common zero-time origin."""
    return [
        os.environ.get("FFMPEG_BIN", "ffmpeg"),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-framerate",
        str(fps),
        "-start_number",
        "1",
        "-i",
        str(output / "frames/frame_%04d.png"),
        "-i",
        str(output / "contact_pickups.wav"),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-vf",
        "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-t",
        str(duration),
        "-movflags",
        "+faststart",
        str(output / "dry_basin.mp4"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--config", type=Path)
    source.add_argument("--experiment")
    parser.add_argument("--duration", type=float)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "prototypes/001_resonant_surface/renders/dry"
    )
    parser.add_argument(
        "--preview", action="store_true", help="Reduce visual mesh and image resolution only"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--view", action="store_true", help="Open Blender; press Space for audio/visual playback"
    )
    mode.add_argument(
        "--render", action="store_true", help="Render PNG frames and mux a synchronized MP4"
    )
    parser.add_argument(
        "--inspection-speed",
        type=float,
        default=1,
        help="Slow-motion inspection; cannot mux normal-speed audio",
    )
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    if args.render and args.inspection_speed != 1:
        parser.error(
            "Synchronized render requires --inspection-speed 1; use --view for slow inspection"
        )
    try:
        module = importlib.import_module("prototypes.001_resonant_surface.dry.config")
        config = module.load_config(args.config, args.experiment)
        if args.duration is not None:
            config.duration = args.duration
        output = args.output.resolve()
        report, bundle, configuration = export_run(
            config,
            output,
            preview=args.preview,
            inspection_speed=args.inspection_speed,
            rebuild=args.rebuild,
        )
        print(
            f"{'Reused' if report['cache_reused'] else 'Solved'} "
            f"{config.mode_count} dry modes; files: {output}",
            flush=True,
        )
        if args.render or args.view:
            result = subprocess.run(
                blender_command(bundle, configuration, output, render=args.render), check=False
            )
            if result.returncode:
                return result.returncode
        if args.render:
            result = subprocess.run(
                mux_command(output, config.fps, report["physical_duration_s"]), check=False
            )
            if result.returncode:
                return result.returncode
            print(f"Synchronized movie: {output / 'dry_basin.mp4'}")
    except ImportError:
        parser.error(
            "Dry structural simulation requires NumPy: python -m pip install -e '.[numerical]'"
        )
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(str(error))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
