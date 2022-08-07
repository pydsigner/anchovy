from __future__ import annotations

import shutil
import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
    from .core import Context


def direct_copy_step(context: Context, path: Path, output_paths: list[Path]):
    """
    A simple Step which only copies a file to the output directory without
    renaming or extension changes.
    """
    for target_path in output_paths:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, target_path)
