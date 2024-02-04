from __future__ import annotations

import re
import typing as t
from pathlib import Path

import pytest

from anchovy.core import BuildSettings, Context, Matcher, PathCalc, Rule, Step
from anchovy.paths import DirPathCalc, OutputDirPathCalc, REMatcher, WebIndexPathCalc, WorkingDirPathCalc


INPUT_PATH = Path('input')
WORKING_PATH = Path('working')
OUTPUT_PATH = Path('output')
EXTERNAL_PATH = Path('external')


@pytest.fixture
def dummy_context():
    return Context(
        BuildSettings(
            input_dir=INPUT_PATH,
            output_dir=OUTPUT_PATH,
            working_dir=WORKING_PATH,
            custody_cache=EXTERNAL_PATH / 'custody.json',
            purge_dirs=False
        ),
        []
    )


@pytest.mark.parametrize('config,input,expected', [
    (('output_dir',), INPUT_PATH / 'foo.txt', OUTPUT_PATH / 'foo.txt'),
    ((OUTPUT_PATH,), INPUT_PATH / 'foo.txt', OUTPUT_PATH / 'foo.txt'),
    ((EXTERNAL_PATH,), WORKING_PATH / 'foo.txt', EXTERNAL_PATH / 'foo.txt'),
    (('working_dir',), INPUT_PATH / 'foo.txt', WORKING_PATH / 'foo.txt'),
    (('working_dir',), WORKING_PATH / 'foo.txt', WORKING_PATH / 'foo.txt'),
    (('working_dir', '.html'), WORKING_PATH / 'foo.txt', WORKING_PATH / 'foo.html'),
    (('working_dir', '.html'), WORKING_PATH / 'foo.j.txt', WORKING_PATH / 'foo.j.html'),
])
def test_dir_path_calc(config: tuple, input: Path, expected: Path, dummy_context: Context):
    calc = DirPathCalc(*config)
    assert calc(dummy_context, input, None) == expected


@pytest.mark.parametrize('config,input,regex,expected', [
    (('output_dir',), INPUT_PATH / 'foo.j.html', r'.*(?P<ext>\.j\.html)', OUTPUT_PATH / 'foo.j.html'),
    (('output_dir', '.zip'), INPUT_PATH / 'foo.j.html', r'.*(?P<ext>\.j\.html)', OUTPUT_PATH / 'foo.zip'),
])
def test_dir_path_calc_regex(config: tuple, input: Path, regex: str, expected: Path, dummy_context: Context):
    calc = DirPathCalc(*config)
    match = re.match(regex, input.as_posix())
    assert calc(dummy_context, input, match) == expected


@pytest.mark.parametrize('config,input,regex,expected', [
    (('output_dir', None, lambda p: p), INPUT_PATH / 'foo.j.html', r'.*(?P<ext>\.j\.html)', OUTPUT_PATH / 'foo.j.html'),
    (('output_dir', '.zip', lambda p: (p.with_suffix('') / 'index').with_suffix(p.suffix)), INPUT_PATH / 'foo.j.html', r'.*(?P<ext>\.j\.html)', OUTPUT_PATH / 'foo' / 'index.zip'),
])
def test_dir_path_calc_transform(config: tuple, input: Path, regex: str, expected: Path, dummy_context: Context):
    calc = DirPathCalc(*config)
    match = re.match(regex, input.as_posix())
    assert calc(dummy_context, input, match) == expected


@pytest.mark.parametrize('config,input,expected', [
    ((), INPUT_PATH / 'foo.txt', OUTPUT_PATH / 'foo.txt'),
    ((), WORKING_PATH / 'foo.txt', OUTPUT_PATH / 'foo.txt'),
    (('.html',), WORKING_PATH / 'foo.txt', OUTPUT_PATH / 'foo.html'),
    (('.html',), WORKING_PATH / 'foo.j.txt', OUTPUT_PATH / 'foo.j.html'),
])
def test_output_dir_path_calc(config: tuple, input: Path, expected: Path, dummy_context: Context):
    calc = OutputDirPathCalc(*config)
    assert calc(dummy_context, input, None) == expected


@pytest.mark.parametrize('config,input,expected', [
    (('output_dir', None), INPUT_PATH / 'foo.html', OUTPUT_PATH / 'foo' / 'index.html'),
    (('output_dir', '.zip', lambda p: p.with_stem(p.stem * 2)), INPUT_PATH / 'foo.html', OUTPUT_PATH / 'foofoo' / 'index.zip'),
])
def test_web_index_path_calc(config: tuple, input: Path, expected: Path, dummy_context: Context):
    calc = WebIndexPathCalc(*config)
    assert calc(dummy_context, input, None) == expected


@pytest.mark.parametrize('config,input,expected', [
    ((), (INPUT_PATH / 'foo.txt', None), WORKING_PATH / 'foo.txt'),
    ((), (WORKING_PATH / 'foo.txt', None), WORKING_PATH / 'foo.txt'),
    (('.html',), (WORKING_PATH / 'foo.txt', None), WORKING_PATH / 'foo.html'),
    (('.html',), (WORKING_PATH / 'foo.j.txt', None), WORKING_PATH / 'foo.j.html'),
])
def test_working_dir_path_calc(config: tuple, input: tuple[Path, t.Any], expected: Path, dummy_context: Context):
    calc = WorkingDirPathCalc(*config)
    assert calc(dummy_context, *input) == expected


@pytest.mark.parametrize('config,input,expected', [
    ((r'.*\.html',), INPUT_PATH / 'foo.html', {}),
    ((r'f.*\.html',), INPUT_PATH / 'foo.html', None),
    ((r'f.*\.html', 0, 'input_dir'), INPUT_PATH / 'foo.html', {}),
    ((r'.*(?P<ext>\.j\.html)', 0, 'input_dir'), INPUT_PATH / 'foo.j.html', {'ext': '.j.html'}),
    ((r'.*(?P<ext>\.j\.html)', 0, 'input_dir'), INPUT_PATH / 'foo.html', None),
    ((r'.*(?P<ext>\.j\.html)', 0, 'working_dir'), INPUT_PATH / 'foo.j.html', None),
    ((r'.*(?P<ext>\.j\.html)', 0, 'working_dir'), WORKING_PATH / 'foo.j.html', {'ext': '.j.html'}),
])
def test_re_matcher(config: tuple, input: Path, expected: dict | None, dummy_context: Context):
    matcher = REMatcher(*config)
    result = matcher(dummy_context, input)
    if result:
        assert result.groupdict() == expected
    else:
        assert result is expected
