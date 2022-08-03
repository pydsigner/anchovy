from __future__ import annotations

import re
from pathlib import Path

from .. import helpers
from ..core import Context
from .parser import process


def anchovy_css_step(path: Path, match: re.Match[str], context: Context):
    processed = process(path.read_text())
    target_path = helpers.to_output(context, path, match, '.css')
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(processed)
    yield target_path
