from __future__ import annotations

import shutil
from pathlib import Path

from .core import Step


class DirectCopyStep(Step):
    """
    A simple Step which only copies a file to the output directory without
    renaming or extension changes.
    """
    def __call__(self, path: Path, output_paths: list[Path]):
        for target_path in output_paths:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(path, target_path)
