from __future__ import annotations

import re
import shutil
import typing as t
from pathlib import Path

from . import helpers
if t.TYPE_CHECKING:
    from .core import Context


def direct_copy_step(path: Path, match: re.Match[str], context: Context):
    target_path = helpers.to_output(context, path, match)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(path, target_path)
    yield target_path
