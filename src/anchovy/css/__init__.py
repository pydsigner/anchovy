from __future__ import annotations

from pathlib import Path

from ..core import Context
from .parser import process


def anchovy_css_step(context: Context, path: Path, output_paths: list[Path]):
    """
    Simple Step to preprocess an Anchovy CSS file into compliant CSS.
    """
    if not output_paths:
        return
    processed = process(path.read_text())
    for target_path in output_paths:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(processed)
