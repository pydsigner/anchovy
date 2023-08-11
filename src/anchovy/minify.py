import shutil
from pathlib import Path

from .core import ContextDir, Step
from .dependencies import pip_dependency


class ResourcePackerStep(Step):
    encoding = 'utf-8'

    def __init__(self, source_dir: ContextDir = 'input_dir'):
        self.source_dir: ContextDir = source_dir

    def __call__(self, path: Path, output_paths: list[Path]):
        parent_dir = self.context[self.source_dir]
        data = '\n\n'.join(
            (parent_dir / f).read_text(self.encoding)
            for filename in path.open() if (f := filename.strip()) and not f.startswith('#')
        )

        for o_path in output_paths:
            o_path.parent.mkdir(parents=True, exist_ok=True)
        output_paths[0].write_text(data, self.encoding)
        for o_path in output_paths[1:]:
            shutil.copy(output_paths[0], o_path)


class CSSMinifierStep(Step):
    encoding = 'utf-8'
    @classmethod
    def get_dependencies(cls):
        return {
            pip_dependency('csscompressor'),
        }

    def __call__(self, path: Path, output_paths: list[Path]):
        import csscompressor
        data = csscompressor.compress(path.read_text(self.encoding))
        for o_path in output_paths:
            o_path.parent.mkdir(parents=True, exist_ok=True)
        output_paths[0].write_text(data, self.encoding)
        for o_path in output_paths[1:]:
            shutil.copy(output_paths[0], o_path)


class HTMLMinifierStep(Step):
    encoding = 'utf-8'
    minify_css = False
    minify_js = False

    @classmethod
    def get_dependencies(cls):
        return {
            (
                pip_dependency('minify-html-onepass', check_name='minify_html_onepass')
                | pip_dependency('minify-html', check_name='minify_html')
            ),
        }

    def __call__(self, path: Path, output_paths: list[Path]):
        params = {'minify_css': self.minify_css, 'minify_js': self.minify_js}
        try:
            from minify_html_onepass import minify
        except ImportError:
            from minify_html import minify
            params |= {
                'do_not_minify_doctype': True,
                'ensure_spec_compliant_unquoted_attribute_values': True,
                'keep_spaces_between_attributes': True,
            }
        data = minify(path.read_text(self.encoding), **params)
        for o_path in output_paths:
            o_path.parent.mkdir(parents=True, exist_ok=True)
        output_paths[0].write_text(data, self.encoding)
        for o_path in output_paths[1:]:
            shutil.copy(output_paths[0], o_path)
