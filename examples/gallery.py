from pathlib import Path

from anchovy import (
    DirectCopyStep,
    InputBuildSettings,
    JinjaMarkdownStep,
    OutputDirPathCalc,
    PillowStep,
    REMatcher,
    Rule,
)


# Optional, and can be overridden with CLI arguments.
SETTINGS = InputBuildSettings(
    input_dir=Path(__file__).parent / 'gallery',
    working_dir=Path('working/gallery'),
    output_dir=Path('output/gallery'),
    custody_cache=Path('output/gallery.json'),
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
    # ...thumbnail them, and stop processing them.
    Rule(
        REMatcher(r'.*\.jpg'),
        [OutputDirPathCalc('.thumb.webp'), None],
        PillowStep(thumbnail=(300, 300))
    ),
    # Copy everything else in static/ directories through.
    Rule(
        REMatcher(r'(.*/)*static/.*', parent_dir='input_dir'),
        OutputDirPathCalc(),
        DirectCopyStep()
    ),
]
