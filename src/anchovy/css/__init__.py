from __future__ import annotations

import re
import typing as t
from pathlib import Path

from .. import helpers
from ..step import Step
from .parser import process
if t.TYPE_CHECKING:
    from ..context import Context


def anchovy_css_step(path: Path, match: re.Match[str], context: Context):
    processed = process(path.read_text())
    target_path = helpers.to_output(context, path, match, '.css')
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(processed)
    yield target_path
