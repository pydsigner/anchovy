"""
Simple Steps and a base class for Steps that invoke external commandline tools.
"""
from __future__ import annotations

import abc
import contextlib
import shutil
import subprocess
import typing as t
from pathlib import Path

from .core import Step

if t.TYPE_CHECKING:
    from _typeshed import StrOrBytesPath


class DirectCopyStep(Step):
    """
    A simple Step which only copies a file to the output directory without
    renaming or extension changes.
    """
    def __call__(self, path: Path, output_paths: list[Path]):
        for target_path in output_paths:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(path, target_path)


class BaseStandardStep(Step):
    """
    A base class providing helper behaviors for typical steps creating one file
    and copying to others.
    """
    encoding = 'utf-8'
    newline = '\n'

    def ensure_output_dirs(self, output_paths: list[Path]):
        for o_path in output_paths:
            o_path.parent.mkdir(parents=True, exist_ok=True)

    def duplicate_output_paths(self, output_paths: list[Path]):
        for o_path in output_paths[1:]:
            shutil.copy(output_paths[0], o_path)

    @contextlib.contextmanager
    def ensure_outputs(self, output_paths: list[Path]):
        self.ensure_output_dirs(output_paths)
        yield
        self.duplicate_output_paths(output_paths)


class BaseCommandStep(Step):
    """
    A base class for steps that run an external command to generate a file.
    """
    @abc.abstractmethod
    def get_command(self, input_path: Path, output_path: Path) -> StrOrBytesPath | list[StrOrBytesPath]:
        """
        Abstract method that must return a commandline ready for subprocess.
        """

    def group_outputs(self, output_paths: list[Path]) -> list[list[Path]]:
        """
        Overridable method which determines which outputs must be generated
        separately. Default behavior groups outputs by extension.
        """
        groups = {}
        for path in output_paths:
            groups.setdefault(path.suffix, []).append(path)
        return list(groups.values())

    def __call__(self, path: Path, output_paths: list[Path]):
        for egroup in self.group_outputs(output_paths):
            first = None
            for opath in egroup:
                opath.parent.mkdir(parents=True, exist_ok=True)
                if first:
                    shutil.copy(first, opath)
                else:
                    subprocess.check_output(
                        self.get_command(path, opath),
                        stderr=subprocess.STDOUT
                    )
                    first = opath
