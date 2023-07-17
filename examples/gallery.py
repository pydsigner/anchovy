from pathlib import Path

from anchovy import (
    DirectCopyStep,
    InputBuildSettings,
    JinjaMarkdownStep,
    OptipngStep,
    OutputDirPathCalc,
    PillowStep,
    REMatcher,
    Rule,
    WorkingDirPathCalc,
)


# Optional, and can be overridden with CLI arguments.
SETTINGS = InputBuildSettings(
    input_dir=Path(__file__).parent / 'gallery',
    output_dir=Path('output/gallery'),
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
    # Convert JPG files to WebP...
    Rule(
        REMatcher(r'.*\.jpg'),
        [OutputDirPathCalc('.webp')],
        PillowStep()
    ),
    # ...thumbnail them as PNGs, and stop processing them.
    Rule(
        REMatcher(r'.*\.jpg'),
        [WorkingDirPathCalc('.thumb.png'), None],
        PillowStep(thumbnail=(300, 300))
    ),
    # Optimize PNG files, then stop processing them.
    Rule(
        REMatcher(r'.*\.png'),
        [OutputDirPathCalc(), None],
        OptipngStep()
    ),
    # Copy everything else in static/ directories through.
    Rule(
        REMatcher(r'(.*/)*static/.*', parent_dir='input_dir'),
        OutputDirPathCalc(),
        DirectCopyStep()
    ),
]
