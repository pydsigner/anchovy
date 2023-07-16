from __future__ import annotations

import shutil
import typing as t
from pathlib import Path

from .core import Context, Step
from .dependencies import pip_dependency

if t.TYPE_CHECKING:
    import commonmark
    import commonmark.render.renderer
    from jinja2 import Environment


class JinjaRenderStep(Step):
    """
    Abstract base class for Steps using Jinja rendering.
    """
    env: Environment

    @classmethod
    def get_dependencies(cls):
        return super().get_dependencies() | {
            pip_dependency('jinja2'),
        }

    def __init__(self,
                 env: Environment | None = None,
                 extra_globals: dict[str, t.Any] | None = None):
        self._temporary_env = env
        self._extra_globals = extra_globals

    def bind(self, context: Context):
        """
        Bind this Step to a specific context. Also initializes a Jinja
        environment if none is set up already.
        """
        super().bind(context)

        if self._temporary_env:
            self.env = self._temporary_env
        else:
            from jinja2 import Environment, FileSystemLoader, select_autoescape
            self.env = Environment(
                loader=FileSystemLoader(context['input_dir']),
                autoescape=select_autoescape()
            )
        if self._extra_globals:
            self.env.globals.update(self._extra_globals)

    def render_template(self, template_name: str, meta: dict[str, t.Any], output_paths: list[Path]):
        """
        Look up a Jinja template by name and render it with @meta as
        parameters, then save the result to each of the provided @output_paths.
        """
        if not output_paths:
            return

        template = self.env.get_template(template_name)
        for path in output_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
        template.stream(**meta).dump(str(output_paths[0]), encoding='utf-8')
        for path in output_paths[1:]:
            shutil.copy(output_paths[0], path)


class JinjaMarkdownStep(JinjaRenderStep):
    """
    A Step for rendering Markdown using Jinja templates. Parses according to
    CommonMark and Renders to HTML by default.
    """
    encoding = 'utf-8'

    @classmethod
    def get_dependencies(cls):
        return super().get_dependencies() | {
            pip_dependency('commonmark'),
        }

    def __init__(self,
                 default_template: str | None = None,
                 md_parser: commonmark.Parser | None = None,
                 md_renderer: commonmark.render.renderer.Renderer | None = None,
                 jinja_env: Environment | None = None,
                 jinja_globals: dict[str, t.Any] | None = None):
        super().__init__(jinja_env, jinja_globals)
        self.default_template = default_template

        self._md_parser = md_parser
        self._md_renderer = md_renderer

    @property
    def md_parser(self):
        if not self._md_parser:
            import commonmark
            self._md_parser = commonmark.Parser()
        return self._md_parser

    @property
    def md_renderer(self):
        if not self._md_renderer:
            import commonmark
            self._md_renderer = commonmark.HtmlRenderer()
        return self._md_renderer


    def __call__(self, path: Path, output_paths: list[Path]):
        meta, content = self.extract_metadata(path.read_text(self.encoding))
        ast = self.md_parser.parse(content.strip())
        meta |= {'rendered_markdown': self.md_renderer.render(ast).strip()}

        self.render_template(
            meta.get('template', self.default_template),
            meta,
            output_paths
        )

    def extract_metadata(self, text: str):
        """
        Read metadata from the front of a markdown-formatted text.
        """
        meta = {}
        lines = text.splitlines()

        i = 0
        for line in lines:
            if ':' not in line:
                break
            key, value = line.split(':', 1)
            if not key.isidentifier():
                break

            meta[key.strip()] = value.strip()
            i += 1

        return meta, '\n'.join(lines[i:])
