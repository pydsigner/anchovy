from __future__ import annotations

from pathlib import Path

from ..core import Step
from ..dependencies import Dependency, import_install_check


class AnchovyCSSStep(Step):
    """
    Simple Step to preprocess an Anchovy CSS file into compliant CSS.
    """
    @classmethod
    def get_dependencies(cls) -> set[Dependency]:
        return super().get_dependencies() | {
            Dependency('tinycss2', 'pip', import_install_check),
        }

    def __call__(self, path: Path, output_paths: list[Path]):
        if not output_paths:
            return
        from .parser import process
        processed = process(path.read_text('utf-8'))
        for target_path in output_paths:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(processed, 'utf-8')
