from __future__ import annotations

import shutil
import typing as t
from pathlib import Path

import commonmark
import commonmark.render.renderer
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .core import Context, Step


class JinjaRenderStep(Step):
    """
    Abstract base class for Steps using Jinja rendering.
    """
    env: Environment

    def __init__(self, env: Environment | None):
        self._temporary_env = env

    def bind(self, context: Context):
        """
        Bind this Step to a specific context. Also initializes a Jinja
        environment if none is set up already.
        """
        super().bind(context)

        if self._temporary_env:
            self.env = self._temporary_env
        else:
            self.env = Environment(
                loader=FileSystemLoader(context['input_dir']),
                autoescape=select_autoescape()
            )

    def render_template(self, template_name: str, meta: dict[str, t.Any], output_paths: list[Path]):
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

    def __init__(self,
                 default_template: str | None = None,
                 md_parser: commonmark.Parser | None = None,
                 md_renderer: commonmark.render.renderer.Renderer | None = None,
                 jinja_env: Environment | None = None):
        super().__init__(jinja_env)
        self.default_template = default_template
        self.md_parser = md_parser or commonmark.Parser()
        self.md_renderer = md_renderer or commonmark.HtmlRenderer()

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
