"""Export verified gravity/capillary water, metal motion and hydrophone-pressure audio."""

import argparse
import hashlib
import importlib
import json
import math
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def load_verified_model(evidence):
    """Load shared water/metal coordinates only when source and artifact hashes agree."""
    from tools.validate_free_surface import check_sources

    report = json.loads(evidence.read_text())
    check_sources(report)
    if not report["passed"]:
        raise ValueError("Free-surface response gates failed; verified playback is unavailable")
    config_module = importlib.import_module("prototypes.001_resonant_surface.dry.config")
    free_module = importlib.import_module("prototypes.001_resonant_surface.free_surface.config")
    model_module = importlib.import_module("prototypes.001_resonant_surface.free_surface.model")
    physical = config_module.from_dict(report["physical_parameters"])
    values = dict(report["free_surface_parameters"])
    values["hydrophones"] = tuple(tuple(p) for p in values["hydrophones"])
    settings = free_module.FreeSurfaceConfig(**values)
    if settings.output_stop_hz != report["tested_stop_hz"]:
        raise ValueError("Free-surface output bandwidth does not match the checked band")
    paths = {}
    for name, record in report["playback_artifacts"].items():
        path = evidence.parent / record["filename"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Free-surface playback artifact changed: {path}")
        paths[name] = path
    bank = model_module.load_bank(paths["modes"], paths["fluid"])
    if len(bank.metal.frequencies) != settings.playback_count or len(bank.pressure_a) != len(
        settings.hydrophones
    ):
        raise ValueError("Coupled bank disagrees with the checked observation dimensions")
    return physical, settings, bank, report


def export_run(evidence, output, *, duration=None, preview=False):
    """One physical response drives Pa samples and both meshes; no fluid solver in Blender."""
    import numpy as np

    from spatial_sculptures.audio.filtering import filter_zero_phase, lowpass_kernel
    from spatial_sculptures.audio.synthesis import write_pickup_wav
    from tools.run_dry_basin import radial_mesh
    from tools.run_wet_basin import water_mesh

    physical, settings, bank, validation = load_verified_model(evidence)
    modes, basis = bank.metal, bank.potential_basis
    model_module = importlib.import_module("prototypes.001_resonant_surface.free_surface.model")
    if duration is not None:
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Duration must be finite and positive")
        physical.duration = duration
    if preview:
        physical.resolution, physical.rings, physical.segments = (480, 360), 8, 48
    frames = max(1, round(physical.duration * physical.fps))
    physical.duration = frames / physical.fps
    frequency_max = max(modes.frequencies[-1], max(e.frequency_hz for e in physical.exciters))
    if frequency_max >= physical.sample_rate / 2:
        raise ValueError("Sample rate must exceed twice every retained/drive frequency")
    if any(e.force_n and e.frequency_hz > settings.output_stop_hz for e in physical.exciters):
        raise ValueError("Drive frequency exceeds verified free-surface observation band")
    simulation = model_module.FreeSurfaceSimulation(physical, settings, bank)
    output.mkdir(parents=True, exist_ok=True)
    configuration = output / "configuration.json"
    # The reusable presentation expects contact markers; wet adapter substitutes fixed probes.
    physical.pickups = tuple((x, y) for x, y, _ in settings.hydrophones)
    configuration.write_text(json.dumps(asdict(physical), indent=2, allow_nan=False))
    kernel = lowpass_kernel(physical.sample_rate, settings.output_stop_hz)
    count, guard = round(physical.duration * physical.sample_rate), len(kernel) // 2
    audio_times = np.arange(count + guard) / physical.sample_rate
    raw = simulation.pressure_trace(audio_times)
    filtered = filter_zero_phase(raw, kernel, output_samples=count)
    audio_path = output / "hydrophones.wav"
    gain = write_pickup_wav(audio_path, filtered, physical.sample_rate)
    np.savez_compressed(
        output / "pressure.npz",
        time_s=audio_times[:count],
        pressure_pa=raw[:, :count],
        filtered_pressure_pa=filtered,
    )
    times = np.arange(frames) / physical.fps
    q, v = simulation.response.trace(times, use_numpy=True)
    accelerations = simulation.engine.accelerations(times, q, v)
    energy = 0.5 * np.sum(
        modes.masses[:, None] * (v**2 + (2 * np.pi * modes.frequencies[:, None]) ** 2 * q**2),
        axis=0,
    )
    visual_q = q
    exposure_samples = 1
    if physical.exposure_fraction:
        span = physical.exposure_fraction / physical.fps
        exposure_samples = max(physical.exposure_samples, math.ceil(4 * frequency_max * span))
        sample_times = (
            times[:, None] + (np.arange(exposure_samples) + 0.5) * span / exposure_samples
        )
        visual_q = (
            simulation.response.trace(sample_times.ravel(), use_numpy=True)[0]
            .reshape(len(modes.frequencies), frames, exposure_samples)
            .mean(axis=2)
        )
    vertices, faces = radial_mesh(physical.surface, physical.rings, physical.segments)
    displacements = np.einsum("pcm,mf->fpc", modes.weights(*vertices[:, :2].T), visual_q).astype(
        np.float32
    )
    water_vertices, water_faces = water_mesh(
        physical.surface, basis, physical.rings, physical.segments
    )
    surface_weights = bank.surface_weights(water_vertices[:, :2])
    water_displacements = (surface_weights @ visual_q).T.astype(np.float32)
    exciter_xy = np.array([(e.patch.x, e.patch.y) for e in physical.exciters])
    exciter_reference = np.column_stack((exciter_xy, physical.surface.geometry(*exciter_xy.T)[0]))
    hydrophones = np.array([(x, y, basis.level - d) for x, y, d in settings.hydrophones])
    marker_reference = np.concatenate((exciter_reference, hydrophones))
    exciter_displacements = np.einsum("pcm,mf->fpc", modes.weights(*exciter_xy.T), visual_q)
    marker_displacements = np.concatenate(
        (exciter_displacements, np.zeros((frames, len(hydrophones), 3))), axis=1
    )
    support_xy = np.array([(s.patch.x, s.patch.y) for s in physical.supports]).reshape(-1, 2)
    support_reference = np.column_stack((support_xy, physical.surface.geometry(*support_xy.T)[0]))
    metadata = {
        "frame_count": frames,
        "fps": physical.fps,
        "physical_seconds_per_visual_second": 1.0,
        "visual_gain": physical.visual_gain,
        "audio_path": str(audio_path.resolve()),
        "exposure_fraction": physical.exposure_fraction,
        "exposure_samples": exposure_samples,
        "presentation": (
            "Common exposure-averaged modal displacement; fixed wet footprint; magnified"
        ),
        "water_level_m": basis.level,
        "stop_hz": settings.output_stop_hz,
    }
    bundle = output / "frames.npz"
    np.savez_compressed(
        bundle,
        vertices=vertices,
        face_sizes=np.array([len(f) for f in faces]),
        face_indices=np.array([i for f in faces for i in f]),
        displacements=displacements,
        water_vertices=water_vertices,
        water_face_sizes=np.array([len(f) for f in water_faces]),
        water_face_indices=np.array([i for f in water_faces for i in f]),
        water_displacements=water_displacements,
        marker_reference=marker_reference,
        marker_displacements=marker_displacements,
        support_reference=support_reference,
        times=times,
        energies=energy,
        hydrophone_pressure_pa=(bank.pressure_a @ accelerations + bank.pressure_q @ q).T,
        surface_displacements_m=(surface_weights @ q).T,
        metadata=json.dumps(metadata),
    )
    report = {
        "model": "linear frozen shell + reciprocally coupled gravity/capillary free surface",
        "physical_parameters": asdict(physical),
        "free_surface_parameters": asdict(settings),
        "mode_frequencies_hz": modes.frequencies.tolist(),
        "modal_masses_kg": modes.masses.tolist(),
        "modal_damping_ratios": bank.damping.tolist(),
        "duration_s": physical.duration,
        "physical_duration_s": physical.duration,
        "frame_count": frames,
        "audio_samples": count,
        "hydrophone_positions_m": hydrophones.tolist(),
        "raw_peak_pressure_pa": np.max(abs(raw[:, :count]), axis=1).tolist(),
        "filtered_peak_pressure_pa": np.max(abs(filtered), axis=1).tolist(),
        "wav_common_gain_per_pa": gain,
        "units": "pressure perturbation Pa, normalized for listening",
        "output_filter": {
            "type": "offline common-channel zero-phase Kaiser FIR",
            "taps": len(kernel),
            "passband_hz": 0.8 * settings.output_stop_hz,
            "stopband_hz": settings.output_stop_hz,
            "stopband_target_db": 80,
            "continuation_samples": guard,
            "timing": "Noncausal; may ring before impacts; common time origin",
        },
        "validation_path": str(evidence.resolve()),
        "validation_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
        "source_sha256": validation["source_sha256"],
        "presentation": metadata,
        "limitations": validation["limitations"],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report, bundle, configuration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence", type=Path, default=ROOT / "docs/research/free_surface/validation.json"
    )
    parser.add_argument("--duration", type=float)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "prototypes/001_resonant_surface/renders/free_surface"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--view", action="store_true")
    mode.add_argument("--render", action="store_true")
    args = parser.parse_args()
    try:
        report, bundle, configuration = export_run(
            args.evidence,
            args.output,
            duration=args.duration,
            preview=args.preview,
        )
        print(f"Free-surface hydrophone pressure and frames: {args.output}", flush=True)
        from tools.run_dry_basin import blender_command, mux_command

        if args.view or args.render:
            command = blender_command(bundle, configuration, args.output, render=args.render)
            command[command.index("--python") + 1] = str(
                ROOT / "prototypes/001_resonant_surface/free_surface/build.py"
            )
            result = subprocess.run(command, check=False)
            if result.returncode:
                return result.returncode
        if args.render:
            command = mux_command(args.output, report["presentation"]["fps"], report["duration_s"])
            command[command.index("-i", command.index("-i") + 1) + 1] = str(
                args.output / "hydrophones.wav"
            )
            command[-1] = str(args.output / "free_surface.mp4")
            result = subprocess.run(command, check=False)
            if result.returncode:
                return result.returncode
            print(f"Synchronized free-surface movie: {args.output / 'free_surface.mp4'}")
    except (OSError, ImportError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
