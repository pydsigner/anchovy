from __future__ import annotations

import sys
import typing as t
if sys.version_info < (3, 11):
    import tomli as tomllib
else:
    import tomllib

from markdown_it.common.utils import escapeHtml, unescapeAll
from markdown_it.renderer import RendererHTML
if t.TYPE_CHECKING:
    from collections.abc import Sequence
    from markdown_it.token import Token
    from markdown_it.utils import EnvType, OptionsDict


def get_container_renderer(container_name, html_tag):
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
            nt = tokens[idx+1]
            if nt.type == 'paragraph_open':
                nt.hidden = True
                counter = idx + 2
                while tokens[counter].type != 'paragraph_close' or tokens[counter].level != nt.level:
                    counter += 1
                tokens[counter].hidden = True

        return self.renderToken(tokens, idx, _options, env)

    render.__name__ = f'render_{container_name}_to_{html_tag}'
    return render


class AnchovyRendererHTML(RendererHTML):
    # https://github.com/executablebooks/markdown-it-py/issues/256
    def fence(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType):
        token = tokens[idx]
        info = unescapeAll(token.info).strip() if token.info else ''
        langName = info.split(maxsplit=1)[0] if info else ''

        return (
            options.highlight
            and options.highlight(token.content, langName, '')
            or escapeHtml(token.content)
        )

    def front_matter(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType):
        parsed = tomllib.loads(tokens[idx].content)
        env['anchovy_meta'].update(parsed)
        return ''
