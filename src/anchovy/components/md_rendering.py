"""
An extended commonmark renderer based on markdown-it-py.
"""
from __future__ import annotations

import typing as t

from markdown_it.common.utils import escapeHtml, unescapeAll
from markdown_it.renderer import RendererHTML

from .md_frontmatter import simple_frontmatter_parser, FrontMatterParser

if t.TYPE_CHECKING:
    from collections.abc import Sequence
    from markdown_it.token import Token
    from markdown_it.utils import EnvType, OptionsDict


def get_container_renderer(container_name: str, html_tag: str):
    """
    Factory function for markdown container renderers.

    Unnecessary internal `<p>` wrapper tags will be eliminated.

    :param container_name: The name of the container. Will be included as a
        `class` in the output HTML container.
    :param html_tag: The HTML tag for the container.
    """
    def render(
        self: RendererHTML,
        tokens: Sequence[Token],
        idx: int,
        _options: OptionsDict,
        env: EnvType,
    ) -> str:
        tokens[idx].tag = html_tag
        # add a class to the opening tag
        if tokens[idx].nesting == 1:
            tokens[idx].attrJoin("class", container_name)
            next_token = tokens[idx+1]
            if next_token.type == 'paragraph_open':
                next_token.hidden = True
                counter = idx + 2
                while tokens[counter].type != 'paragraph_close' or tokens[counter].level != next_token.level:
                    counter += 1
                tokens[counter].hidden = True

        return self.renderToken(tokens, idx, _options, env)

    render.__name__ = f'render_{container_name}_to_{html_tag}'
    return render


class AnchovyRendererHTML(RendererHTML):
    """
    A customized markdown-it-py HTML renderer, with hooks for better pygments
    integration and toml frontmatter support.
    """
    def __init__(self, parser: t.Any = None):
        super().__init__(parser)
        self.front_matter_parser: FrontMatterParser = simple_frontmatter_parser

    # https://github.com/executablebooks/markdown-it-py/issues/256
    def fence(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType):
        """
        Handles rendering a markdown code fence, with optional syntax
        highlighting.
        """
        token = tokens[idx]
        info = unescapeAll(token.info).strip() if token.info else ''
        lang_name = info.split(maxsplit=1)[0] if info else ''

        return (
            options.highlight
            and options.highlight(token.content, lang_name, '')
            or escapeHtml(token.content)
        )

    def set_front_matter_parser(self, parser: FrontMatterParser):
        self.front_matter_parser = parser

    def front_matter(self, tokens: Sequence[Token], idx: int, _options: OptionsDict, env: EnvType):
        """
        Handles parsing markdown frontmatter using TOML.
        """
        parsed = self.front_matter_parser(tokens[idx].content)
        env['anchovy_meta'].update(parsed)
        return ''
