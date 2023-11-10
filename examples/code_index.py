from __future__ import annotations

from pathlib import Path
import typing as t

from anchovy import (
    AnchovyCSSStep,
    AssetMinifierStep,
    CSSMinifierStep,
    DirectCopyStep,
    Matcher,
    InputBuildSettings,
    JinjaExtendedMarkdownStep,
    JinjaRenderStep,
    OutputDirPathCalc,
    PathCalc,
    REMatcher,
    ResourcePackerStep,
    Rule,
    Step,
    UnpackArchiveStep,
    WorkingDirPathCalc,
)
from anchovy.custody import CustodyEntry

if t.TYPE_CHECKING:
    from jinja2 import Environment


MARKDOWN_TEMPLATE = """---
template = "base.jinja.html"
footnote = "Generated from {path} by Anchovy."
---
# {path}

```py
{code}
```
"""


class Code2MarkdownStep(Step):
    encoding = 'utf-8'
    newline = '\n'
    template = MARKDOWN_TEMPLATE
    def __call__(self, path: Path, output_paths: list[Path]):
        code = path.read_text(self.encoding)
        processed = self.template.format(path=path.name, code=code)
        for target_path in output_paths:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(processed, self.encoding, newline=self.newline)


class CodeIndexStep(JinjaRenderStep):
    encoding = 'utf-8'

    def __init__(self,
                 leaf_matcher: Matcher,
                 leaf_calc: PathCalc,
                 env: Environment | None = None,
                 extra_globals: dict[str, t.Any] | None = None):
        super().__init__(env, extra_globals)
        self.leaf_matcher = leaf_matcher
        self.leaf_calc = leaf_calc

    @classmethod
    def get_dependencies(cls):
        return super().get_dependencies()

    def __call__(self, path: Path, output_paths: list[Path]):
        matched_paths: list[Path] = [path]
        leaves: list[tuple[Path, Path]] = []
        for sibling in path.parent.iterdir():
            print('sibling:', sibling)
            if sibling == path or sibling.is_dir():
                continue
            print('sibling matched thus')
            if match := self.leaf_matcher(self.context, sibling):
                print('sibling matched', match)
                matched_paths.append(sibling)
                leaves.append((
                    sibling,
                    self.leaf_calc(self.context, sibling, match).relative_to(self.context['output_dir']),
                ))

        print('leaves:', leaves)
        self.render_template(
            path.relative_to(self.context['working_dir']).as_posix(),
            {'leaves': leaves},
            output_paths
        )
        return matched_paths, output_paths


# Optional, and can be overridden with CLI arguments.
SETTINGS = InputBuildSettings(
    input_dir=Path(__file__).parent / 'code_index',
    working_dir=Path('working/code_index'),
    output_dir=Path('output/code_index'),
    custody_cache=Path('output/code_index.json'),
)
RULES = [
    # Ignore dotfiles found in either the input_dir or the working dir.
    Rule(
        (
            REMatcher(r'(.*/)*\..*', parent_dir='input_dir')
            | REMatcher(r'(.*/)*\..*', parent_dir='working_dir')
        ),
        None
    ),
    # Unpack archives.
    Rule(
        REMatcher(r'.*\.zip'),
        [WorkingDirPathCalc(transform=lambda p: p.parent), None],
        UnpackArchiveStep()
    ),
    # Embed Python files in Markdown.
    Rule(
        REMatcher(r'.*\.py'),
        [WorkingDirPathCalc('.md')],
        Code2MarkdownStep()
    ),
    # Render markdown files and stop processing.
    Rule(
        REMatcher(r'.*\.md'),
        [WorkingDirPathCalc('.html'), None],
        JinjaExtendedMarkdownStep(
            default_template='base.j.html',
            pygments_params={'classprefix': 'pyg-'},
        )
    ),
    # Render Jinja indices through working dir (so there's time for the archive
    # to unpack) and stop processing.
    Rule(
        REMatcher(r'index\.jinja\.html', parent_dir='input_dir'),
        [WorkingDirPathCalc(), None],
        DirectCopyStep()
    ),
    Rule(
        REMatcher(r'index(?P<ext>\.jinja\.html)', parent_dir='working_dir'),
        [WorkingDirPathCalc('.html'), None],
        CodeIndexStep(
            REMatcher(r'.*\.py'),
            OutputDirPathCalc('.html')
        )
    ),
    # Ignore all other Jinja templates.
    Rule(REMatcher(r'.*\.jinja\.html'), None),
    # Preprocess Anchovy CSS and stop processing.
    Rule(
        REMatcher(r'.*(?P<ext>\.anchovy\.css)'),
        [WorkingDirPathCalc('.css'), None],
        AnchovyCSSStep()
    ),
    # Pack CSS. Have to wait for working dir so Anchovy CSS processing is done.
    Rule(
        REMatcher(r'.*/css_pack.txt', parent_dir='input_dir'),
        [WorkingDirPathCalc(), None],
        DirectCopyStep()
    ),
    Rule(
        REMatcher(r'.*/css_pack.txt', parent_dir='working_dir'),
        [WorkingDirPathCalc('.css'), None],
        ResourcePackerStep('working_dir')
    ),
    # Minify packed CSS and stop processing.
    Rule(
        REMatcher(r'.*/css_pack\.css', parent_dir='working_dir'),
        [OutputDirPathCalc(), None],
        CSSMinifierStep()
    ),
    # Minify HTML/JS and stop processing.
    Rule(
        REMatcher(r'.*\.(html|js)', parent_dir='working_dir'),
        [OutputDirPathCalc(), None],
        AssetMinifierStep()
    ),
]