"""
Steps for reducing the load cost of webpages by combining and minifying
resources.
"""
import mimetypes
from pathlib import Path
from collections.abc import Sequence

from .core import ContextDir
from .dependencies import PipDependency
from .simple import BaseStandardStep


class ResourcePackerStep(BaseStandardStep):
    """
    A simple resource packing Step, using a config file with a list of files to
    join into one.
    """
    def __init__(self, source_dir: ContextDir = 'input_dir'):
        self.source_dir: ContextDir = source_dir

    def __call__(self, path: Path, output_paths: list[Path]):
        parent_dir = self.context[self.source_dir]
        input_paths = [
            (parent_dir / cleaned)
            for filename in path.open()
            if (cleaned := filename.strip()) and not cleaned.startswith('#')
        ]
        data = '\n\n'.join(f.read_text(self.encoding) for f in input_paths)

        with self.ensure_outputs(output_paths):
            output_paths[0].write_text(data, self.encoding, newline=self.newline)

        input_paths.insert(0, path)
        return input_paths, output_paths


class CSSMinifierStep(BaseStandardStep):
    """
    A powerful CSS minification Step, using lightningcss to offer intelligent
    CSS reduction based on browsers supported and unused styles.
    """
    @classmethod
    def get_dependencies(cls):
        return {
            PipDependency('lightningcss')
        }

    def __init__(self,
                 error_recovery: bool = False,
                 parser_flags: dict[str, bool] | None = None,
                 unused_symbols: set[str] | None = None,
                 browsers_list: Sequence[str] | None = ('defaults',),
                 minify: bool = True):

        self.error_recovery = error_recovery
        self.parser_flags = parser_flags or {}
        self.unused_symbols = unused_symbols
        self.browsers_list = list(browsers_list) if browsers_list else None
        self.minify = minify

    def __call__(self, path: Path, output_paths: list[Path]):
        import lightningcss
        data = lightningcss.process_stylesheet(
            path.read_text(self.encoding),
            filename=str(path),
            error_recovery=self.error_recovery,
            parser_flags=lightningcss.calc_parser_flags(**self.parser_flags),
            unused_symbols=self.unused_symbols,
            browsers_list=self.browsers_list,
            minify=self.minify
        )
        with self.ensure_outputs(output_paths):
            output_paths[0].write_text(data, self.encoding, newline=self.newline)


class HTMLMinifierStep(BaseStandardStep):
    """
    A simple but fast HTML minification Step.
    """
    minify_css = False
    minify_js = False

    @classmethod
    def get_dependencies(cls):
        return {
            (
                PipDependency('minify-html-onepass', check_name='minify_html_onepass')
                | PipDependency('minify-html', check_name='minify_html')
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
        with self.ensure_outputs(output_paths):
            output_paths[0].write_text(data, self.encoding, newline=self.newline)


class AssetMinifierStep(BaseStandardStep):
    """
    A fast and powerful web minifier supporting CSS, HTML, JS, JSON, SVG, and
    XML. Uses MIME type detection to determine which minifier to use.

    NOTE: Not supported on macOS.
    """
    @classmethod
    def get_dependencies(cls):
        return {
            PipDependency('tdewolff-minify', check_name='minify')
        }

    def __init__(self, mimetype: str | None = None):
        """
        @mimetype is an optional MIME type string to override MIME type
        detection.
        """
        self.mimetype = mimetype

    def detect_mime(self, path: Path):
        """
        Detect the MIME type of the specified path.
        """
        return mimetypes.guess_type(path)[0]

    def __call__(self, path: Path, output_paths: list[Path]):
        import minify

        if not (mime := self.mimetype or self.detect_mime(path)):
            raise ValueError(f'Could not detect MIME type for {path}!')

        with self.ensure_outputs(output_paths):
            minify.file(mime, str(path), str(output_paths[0]))
