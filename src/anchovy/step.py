from __future__ import annotations

import abc
import re
import shutil
import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
    from .context import Context


class Step(abc.ABC):
    context: Context

    def bind(self, context: Context):
        self.context = context

    @abc.abstractmethod
    def __call__(self, path: Path, match: re.Match[str]) -> t.Iterable[Path]:
        ...


def direct_copy_step(path: Path, match: re.Match[str], context: Context):
    target_path = context['output_dir'] / path.relative_to(context['input_dir'])
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(path, target_path)
    yield target_path
