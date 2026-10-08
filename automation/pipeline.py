"""Composition of provider-neutral automation stages.

Pipeline functions are ordinary library interfaces.  Command adapters and forge
adapters call them directly instead of spawning sibling executables.
"""

from .artifacts import write_push_artifacts
from .policy import classify_push
from .push import collect_push


def prepare_push(repository_path, envelope, output_dir):
    """Collect, classify, route, and render one push event locally."""

    manifest = classify_push(collect_push(repository_path, envelope))
    write_push_artifacts(manifest, output_dir)
    return manifest
