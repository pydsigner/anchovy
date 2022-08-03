from __future__ import annotations

import re
import typing as t
from pathlib import Path

import commonmark
import commonmark.render.renderer
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import helpers
from .core import Context, Step


class JinjaRenderStep(Step):
    env: Environment

    def __init__(self, env: Environment | None):
        self._temporary_env = env

    def bind(self, context: Context):
        super().bind(context)

        if self._temporary_env:
            self.env = self._temporary_env
        else:
            self.env = Environment(
                loader=FileSystemLoader(context['input_dir']),
                autoescape=select_autoescape()
            )

    def render_template(self, template_name: str, meta: dict[str, t.Any], target_path: Path):
        template = self.env.get_template(template_name)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        template.stream(**meta).dump(str(target_path), encoding='utf-8')
        # Returning the path makes for easier composition.
        return target_path


class JinjaMarkdownStep(JinjaRenderStep):
    def __init__(self,
                 default_template: str | None = None,
                 md_parser: commonmark.Parser | None = None,
                 md_renderer: commonmark.render.renderer.Renderer | None = None,
                 jinja_env: Environment | None = None):
        super().__init__(jinja_env)
        self.default_template = default_template
        self.md_parser = md_parser or commonmark.Parser()
        self.md_renderer = md_renderer or commonmark.HtmlRenderer()

    def __call__(self, path: Path, match: re.Match[str]) -> t.Iterable[Path]:
        meta, content = self.extract_metadata(path.read_text())
        ast = self.md_parser.parse(content.strip())
        meta |= {'rendered_markdown': self.md_renderer.render(ast).strip()}

        target_path = helpers.to_output(self.context, path, match, '.html')

        yield self.render_template(
            meta.get('template', self.default_template),
            meta,
            target_path
        )

    def extract_metadata(self, text: str):
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
