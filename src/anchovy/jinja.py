from __future__ import annotations

import shutil
import typing as t
from functools import reduce
from pathlib import Path

from .core import Context, Step
from .dependencies import pip_dependency, Dependency

if t.TYPE_CHECKING:
    from jinja2 import Environment


MDProcessor = t.Callable[[str], str]


class JinjaRenderStep(Step):
    """
    Abstract base class for Steps using Jinja rendering.
    """
    env: Environment

    @classmethod
    def get_dependencies(cls):
        return {
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
    def _build_markdownit(cls):
        import markdown_it
        processor = markdown_it.MarkdownIt()

        def convert(md_string: str) -> str:
            return processor.render(md_string)

        return convert

    @classmethod
    def _build_mistletoe(cls):
        import mistletoe
        processor = mistletoe.HTMLRenderer()

        def convert(md_string: str) -> str:
            return processor.render(mistletoe.Document(md_string))

        return convert

    @classmethod
    def _build_markdown(cls):
        import markdown
        processor = markdown.Markdown()

        def convert(md_string: str):
            return processor.convert(md_string)

        return convert

    @classmethod
    def _build_commonmark(cls):
        import commonmark
        parser = commonmark.Parser()
        renderer = commonmark.HtmlRenderer()

        def convert(md_string: str) -> str:
            return renderer.render(parser.parse(md_string))

        return convert

    @classmethod
    def get_options(cls):
        return [
            (pip_dependency('markdown-it-py', None, 'markdown_it'), cls._build_markdownit),
            (pip_dependency('mistletoe'), cls._build_mistletoe),
            (pip_dependency('markdown'), cls._build_markdown),
            (pip_dependency('commonmark'), cls._build_commonmark),
        ]

    @classmethod
    def get_dependencies(cls):
        deps = [option[0] for option in cls.get_options()]
        dep_set = {reduce(lambda x, y: x | y, deps)} if deps else set[Dependency]()

        return super().get_dependencies() | dep_set

    def __init__(self,
                 default_template: str | None = None,
                 md_processor: MDProcessor | None = None,
                 jinja_env: Environment | None = None,
                 jinja_globals: dict[str, t.Any] | None = None):
        super().__init__(jinja_env, jinja_globals)
        self.default_template = default_template
        self._md_processor = md_processor

    @property
    def md_processor(self):
        if not self._md_processor:
            for dep, factory in self.get_options():
                if dep.satisfied:
                    self._md_processor = factory()
                    break
            else:
                raise RuntimeError('Markdown processor could not be initialized!')
        return self._md_processor


    def __call__(self, path: Path, output_paths: list[Path]):
        meta, content = self.extract_metadata(path.read_text(self.encoding))
        meta |= {'rendered_markdown': self.md_processor(content.strip()).strip()}

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
