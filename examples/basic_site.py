from pathlib import Path

from anchovy.core import InputBuildSettings, Rule
from anchovy.helpers import match_re, to_output
from anchovy.jinja import JinjaMarkdownStep
from anchovy.simple import direct_copy_step


# Optional, and can be overridden with CLI arguments.
SETTINGS = InputBuildSettings(
    input_dir=Path(__file__).parent / 'basic_site',
    output_dir=Path('output/basic_site'),
)
RULES = [
    # Ignore dotfiles.
    Rule(match_re(r'(.*/)*\..*'), None),
    # Render markdown files, then stop processing them.
    Rule(match_re(r'.*\.md'), [to_output('.html'), None], JinjaMarkdownStep()),
    # Copy everything else in static/ directories through.
    Rule(match_re(r'.*/static/.*'), to_output(), direct_copy_step),
]
