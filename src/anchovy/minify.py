import shutil
from pathlib import Path

from .core import ContextDir, Step
from .dependencies import pip_dependency


class ResourcePackerStep(Step):
    def __init__(self, source_dir: ContextDir = 'input_dir'):
        self.source_dir: ContextDir = source_dir

    def __call__(self, path: Path, output_paths: list[Path]):
        parent_dir = self.context[self.source_dir]
        data = '\n\n'.join(
            (parent_dir / filename.strip()).read_text('utf-8')
            for filename in path.open() if filename
        )

        for o_path in output_paths:
            o_path.parent.mkdir(parents=True, exist_ok=True)
        output_paths[0].write_text(data, 'utf-8')
        for o_path in output_paths[1:]:
            shutil.copy(output_paths[0], o_path)


class CSSMinifierStep(Step):
    @classmethod
    def get_dependencies(cls):
        return {
            pip_dependency('csscompressor'),
        }

    def __call__(self, path: Path, output_paths: list[Path]):
        import csscompressor
        data = csscompressor.compress(path.read_text('utf-8'))
        for o_path in output_paths:
            o_path.parent.mkdir(parents=True, exist_ok=True)
        output_paths[0].write_text(data, 'utf-8')
        for o_path in output_paths[1:]:
            shutil.copy(output_paths[0], o_path)


class HTMLMinifierStep(Step):
    @classmethod
    def get_dependencies(cls):
        return {
            pip_dependency('minify-html-onepass', check_name='minify_html_onepass'),
        }

    def __call__(self, path: Path, output_paths: list[Path]):
        import minify_html_onepass
        data = minify_html_onepass.minify(path.read_text('utf-8'))
        for o_path in output_paths:
            o_path.parent.mkdir(parents=True, exist_ok=True)
        output_paths[0].write_text(data, 'utf-8')
        for o_path in output_paths[1:]:
            shutil.copy(output_paths[0], o_path)
