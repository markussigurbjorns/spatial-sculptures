"""Small feed-forward processing pieces for future explicit feedback experiments."""


def bounded_gain(value: float, gain: float = 1.0, limit: float = 1.0) -> float:
    """Scale and clamp a sample. This alone supplies no closed-loop stability guarantee."""
    if limit <= 0:
        raise ValueError("Feedback limit must be positive")
    return max(-limit, min(limit, gain * value))
