"""
Steps for pre-processing the Anchovy CSS format.
"""
from __future__ import annotations

from pathlib import Path

from .simple import BaseStandardStep
from .dependencies import PipDependency


class AnchovyCSSStep(BaseStandardStep):
    """
    Simple Step to preprocess an Anchovy CSS file into compliant CSS.
    """
    @classmethod
    def get_dependencies(cls):
        return {
            PipDependency('anchovy_css'),
        }

    def __call__(self, path: Path, output_paths: list[Path]):
        from anchovy_css import process
        processed = process(path.read_text(self.encoding))
        with self.ensure_outputs(output_paths):
            output_paths[0].write_text(processed, self.encoding, newline=self.newline)
