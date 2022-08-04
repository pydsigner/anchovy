from pathlib import Path

from anchovy.core import InputBuildSettings, Rule
from anchovy.jinja import JinjaMarkdownStep
from anchovy.simple import direct_copy_step


# Optional, and can be overridden with CLI arguments.
SETTINGS = InputBuildSettings(
    input_dir=Path(__file__).parent / 'basic_site',
    output_dir=Path('output/basic_site'),
)
RULES: list[Rule] = [
    # Ignore dotfiles.
    (r'(.*/)*\..*', None),
    # Render markdown files, then stop processing them.
    (r'.*\.md', JinjaMarkdownStep()),
    (r'.*\.md', None),
    # Copy everything else in static/ directories through.
    (r'.*/static/.*', direct_copy_step),
]
