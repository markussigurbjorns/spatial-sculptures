"""Small explicit configuration variations; research experiments, not unit tests."""

from importlib import import_module
from pathlib import Path

from ..config import StudyConfig


def experiment_names() -> tuple[str, ...]:
    """List the numbered experiment files in a stable order."""
    return tuple(sorted(path.stem for path in Path(__file__).parent.glob("[0-9]*.py")))


def configure_experiment(name: str, config: StudyConfig) -> StudyConfig:
    """Apply one repository-owned Python configuration function to fresh defaults."""
    if name not in experiment_names():
        raise ValueError(f"Unknown experiment {name!r}; available: {', '.join(experiment_names())}")
    return import_module(f"{__name__}.{name}").configure(config)
