from pathlib import Path

from anchovy import (
    DirectCopyStep,
    InputBuildSettings,
    JinjaMarkdownStep,
    OutputDirPathCalc,
    REMatcher,
    Rule,
)


# Optional, and can be overridden with CLI arguments.
SETTINGS = InputBuildSettings(
    input_dir=Path(__file__).parent / 'basic_site',
    output_dir=Path('output/basic_site'),
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
    # Render markdown files, then stop processing them.
    Rule(
        REMatcher(r'.*\.md'),
        [OutputDirPathCalc('.html'), None],
        JinjaMarkdownStep()
    ),
    # Copy everything else in static/ directories through.
    Rule(
        REMatcher(r'(.*/)*static/.*', parent_dir='input_dir'),
        OutputDirPathCalc(),
        DirectCopyStep()
    ),
]
