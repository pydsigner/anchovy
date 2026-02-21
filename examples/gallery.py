from pathlib import Path

from anchovy import (
    DirectCopyStep,
    HashSuffixPathCalc,
    InputBuildSettings,
    JinjaMarkdownStep,
    OutputDirPathCalc,
    PillowStep,
    REMatcher,
    Rule,
    WorkingDirPathCalc,
)
from anchovy.rewrite import HTMLRewriteStep


def chooser(reference: str, options: set[str]):
    if reference.endswith('?thumb'):
        subset = (o for o in options if '.thumb.' in o)
    else:
        subset = (o for o in options if '.thumb.' not in o)
    return next(subset)


# Optional, and can be overridden with CLI arguments.
SETTINGS = InputBuildSettings(
    input_dir=Path(__file__).parent / 'gallery',
    working_dir=Path('working/gallery'),
    output_dir=Path('output/gallery'),
    custody_cache=Path('output/gallery.json'),
)
RULES = [
    # Ignore dotfiles found in either the input_dir or the working dir, as well
    # as any jinja templates.
    Rule(
        (
            REMatcher(r'(.*/)*\..*', parent_dir='input_dir')
            | REMatcher(r'(.*/)*\..*', parent_dir='working_dir')
            | REMatcher(r'.*\.jinja\.html')
        ),
        None
    ),
    # Render markdown files, then stop processing them.
    Rule(
        REMatcher(r'.*\.md'),
        [WorkingDirPathCalc('.html'), None],
        JinjaMarkdownStep(frontmatter_parser='toml')
    ),
    # Convert JPG files to WebP...
    Rule(
        REMatcher(r'.*\.jpg'),
        [HashSuffixPathCalc('output_dir', '.webp')],
        PillowStep()
    ),
    # ...thumbnail them, and stop processing them.
    Rule(
        REMatcher(r'.*\.jpg'),
        [HashSuffixPathCalc('output_dir', '.thumb.webp'), None],
        PillowStep(thumbnail=(300, 300))
    ),
    # Copy everything else in static/ directories through.
    Rule(
        REMatcher(r'(.*/)*static/.*', parent_dir='input_dir'),
        OutputDirPathCalc(),
        DirectCopyStep()
    ),
    Rule(
        REMatcher(r'.*\.html'),
        [OutputDirPathCalc(), None],
        HTMLRewriteStep(
            chooser=chooser,
            preprocess=lambda s: 'input_dir/' + s.rsplit('?', 1)[0],
            postprocess=lambda s: s.replace('output_dir/', '', 1)
        )
    ),
]
