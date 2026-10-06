"""Numerical mode matching and unnormalized contact-response comparisons (optional NumPy)."""

import numpy as np


def assignment(scores):
    """Globally maximize a rectangular score matrix with one distinct column per row.

    Short augmenting-path Hungarian algorithm; no SciPy dependency. Mode order,
    sign and scale do not determine correspondence.
    """
    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 2 or not np.all(np.isfinite(scores)):
        raise ValueError("Finite two-dimensional matching scores required")
    rows, columns = scores.shape
    if not 0 < rows <= columns:
        raise ValueError("At least as many candidate modes as reference modes required")
    cost = -scores
    u, v = np.zeros(rows + 1), np.zeros(columns + 1)
    owner, previous = np.zeros(columns + 1, dtype=int), np.zeros(columns + 1, dtype=int)
    for row in range(1, rows + 1):
        owner[0], current = row, 0
        minimum, visited = np.full(columns + 1, np.inf), np.zeros(columns + 1, dtype=bool)
        while True:
            visited[current] = True
            active = owner[current]
            delta, next_column = np.inf, 0
            for column in range(1, columns + 1):
                if visited[column]:
                    continue
                reduced = cost[active - 1, column - 1] - u[active] - v[column]
                if reduced < minimum[column]:
                    minimum[column], previous[column] = reduced, current
                if minimum[column] < delta:
                    delta, next_column = minimum[column], column
            for column in range(columns + 1):
                if visited[column]:
                    u[owner[column]] += delta
                    v[column] -= delta
                else:
                    minimum[column] -= delta
            current = next_column
            if owner[current] == 0:
                break
        while current:
            last = previous[current]
            owner[current] = owner[last]
            current = last
    result = np.empty(rows, dtype=int)
    for column in range(1, columns + 1):
        if owner[column]:
            result[owner[column] - 1] = column - 1
    return result


def compare_modes(
    reference_frequencies,
    reference_shapes,
    candidate_frequencies,
    candidate_shapes,
    weights,
    *,
    cluster_gap=0.002,
):
    """Match weighted vector shapes; compare nearly degenerate subspaces by principal angles.

    Shapes are point x Cartesian component x mode; weights are physical area.
    A group's worst squared principal cosine is invariant to signs, scaling,
    order and orthogonal mixing. Frequencies within a group are compared sorted.
    """
    rf, cf = np.asarray(reference_frequencies), np.asarray(candidate_frequencies)
    r, c, w = np.asarray(reference_shapes), np.asarray(candidate_shapes), np.asarray(weights)
    if (
        not np.isfinite(cluster_gap)
        or cluster_gap < 0
        or r.ndim != 3
        or c.ndim != 3
        or r.shape[:2] != c.shape[:2]
        or r.shape[-1] != len(rf)
        or c.shape[-1] != len(cf)
        or w.shape != (len(r),)
        or np.any(w <= 0)
        or not all(np.all(np.isfinite(a)) for a in (rf, cf, r, c, w))
        or np.any(rf <= 0)
        or np.any(cf <= 0)
        or np.any(np.diff(rf) < 0)
    ):
        raise ValueError("Finite positive frequencies, matching shapes and area weights required")
    a = (r * np.sqrt(w)[:, None, None]).reshape(-1, len(rf))
    b = (c * np.sqrt(w)[:, None, None]).reshape(-1, len(cf))
    an, bn = np.linalg.norm(a, axis=0), np.linalg.norm(b, axis=0)
    if np.any(an == 0) or np.any(bn == 0):
        raise ValueError("Mode shapes cannot vanish on the comparison grid")
    mac = np.minimum(1.0, (a.T @ b / (an[:, None] * bn[None, :])) ** 2)
    matched = assignment(mac)
    groups, start = [], 0
    for end in range(1, len(rf) + 1):
        if end < len(rf) and rf[end] / rf[end - 1] - 1 <= cluster_gap:
            continue
        indexes = np.arange(start, end)
        selected = matched[indexes]
        qa, ra = np.linalg.qr(a[:, indexes], mode="reduced")
        qb, rb = np.linalg.qr(b[:, selected], mode="reduced")
        for factor in (ra, rb):
            if np.min(np.abs(np.diag(factor))) < np.max(np.abs(factor)) * 1e-10:
                raise ValueError("Dependent mode shapes on the comparison grid")
        singular = np.linalg.svd(qa.T @ qb, compute_uv=False)
        groups.append(
            {
                "reference_indices": indexes.tolist(),
                "candidate_indices": selected.tolist(),
                "minimum_subspace_MAC": float(min(1.0, singular.min() ** 2)),
                "maximum_relative_frequency_difference": float(
                    np.max(np.abs(np.sort(cf[selected]) / rf[indexes] - 1))
                ),
                "individual_MAC": mac[indexes, selected].tolist(),
            }
        )
        start = end
    return {
        "groups": groups,
        "matched_indices": matched.tolist(),
        "cluster_relative_gap": cluster_gap,
    }


def contact_transfer(frequencies_hz, masses, pickup_weights, force_weights, damping, sample_hz):
    """Velocity/force transfer in (m/s)/N, shape pickup x exciter x frequency.

    No listening normalization: modal residue, phase and resonances affect errors.
    Zero frequency has zero velocity response. This is the retained linear model,
    not hydrophone pressure or a calibrated transducer transfer function.
    """
    frequencies, masses = np.asarray(frequencies_hz), np.asarray(masses)
    pickups, forces = np.asarray(pickup_weights), np.asarray(force_weights)
    samples = np.asarray(sample_hz)
    if (
        frequencies.ndim != 1
        or not len(frequencies)
        or masses.shape != frequencies.shape
        or pickups.ndim != 2
        or forces.ndim != 2
        or pickups.shape[1] != len(frequencies)
        or forces.shape[1] != len(frequencies)
        or samples.ndim != 1
        or not len(samples)
        or np.any(samples < 0)
        or np.any(frequencies <= 0)
        or np.any(masses <= 0)
        or not 0 < damping < 1
        or not all(np.all(np.isfinite(a)) for a in (frequencies, masses, pickups, forces, samples))
    ):
        raise ValueError("Positive modal data, finite weights and damped sampling required")
    omega, natural = 2 * np.pi * samples, 2 * np.pi * frequencies
    denominator = masses[:, None] * (
        natural[:, None] ** 2
        - omega[None, :] ** 2
        + 2j * damping * natural[:, None] * omega[None, :]
    )
    return np.einsum("pm,em,mf->pef", pickups, forces, 1j * omega[None, :] / denominator)


def relative_response_error(reference, candidate):
    """Relative complex L2 error per contact/exciter path, with explicit silent-path handling."""
    reference, candidate = np.asarray(reference), np.asarray(candidate)
    if reference.shape != candidate.shape or reference.ndim < 1 or not reference.shape[-1]:
        raise ValueError("Matching sampled response arrays required")
    if not np.all(np.isfinite(reference)) or not np.all(np.isfinite(candidate)):
        raise ValueError("Finite response arrays required")
    denominator = np.linalg.norm(reference, axis=-1)
    numerator = np.linalg.norm(candidate - reference, axis=-1)
    return np.divide(
        numerator, denominator, out=np.where(numerator == 0, 0.0, np.inf), where=denominator > 0
    )
