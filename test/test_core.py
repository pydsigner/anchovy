from pathlib import Path

import pytest

from anchovy.core import BuildSettings, Context, Matcher, PathCalc, Rule, Step


class DummyStep(Step):
    def __call__(self, path: Path, output_paths: list[Path]):
        pass


class AllMatcher(Matcher[Path]):
    def __call__(self, context: Context, path: Path):
        return path


class BMatcher(Matcher[Path]):
    def __call__(self, context: Context, path: Path):
        if path.name.startswith('b'):
            return path


class DummyPathCalc(PathCalc[Path]):
    def __call__(self, context: Context, path: Path, match: Path) -> Path:
        return context['output_dir'] / path.relative_to(context['input_dir'])


@pytest.fixture
def build_settings(tmp_path):
    return BuildSettings(
        input_dir=tmp_path / 'input',
        output_dir=tmp_path / 'output',
        working_dir=tmp_path / 'working',
        custody_cache=tmp_path / 'custody.json',
        purge_dirs=False
    )


def test_context_match_paths(build_settings: BuildSettings):
    i_a = build_settings['input_dir'] / 'a'
    i_b = build_settings['input_dir'] / 'b'
    i_c = build_settings['input_dir'] / 'c'
    o_a = build_settings['output_dir'] / 'a'
    o_b = build_settings['output_dir'] / 'b'
    o_c = build_settings['output_dir'] / 'c'

    paths = [i_a, i_b, i_c]
    b_step = DummyStep()
    all_step = DummyStep()
    context = Context(build_settings, [
        Rule(BMatcher(), DummyPathCalc(), b_step),
        Rule(AllMatcher(), DummyPathCalc(), all_step),
    ])
    tasks = context.match_paths(paths)
    assert tasks == {
        b_step: [
            (i_b, [o_b]),
        ],
        all_step: [
            (i_a, [o_a]),
            (i_b, [o_b]),
            (i_c, [o_c]),
        ],
    }

def test_context_match_paths_stop_matching(build_settings: BuildSettings):
    i_a = build_settings['input_dir'] / 'a'
    i_b = build_settings['input_dir'] / 'b'
    i_c = build_settings['input_dir'] / 'c'
    o_a = build_settings['output_dir'] / 'a'
    o_b = build_settings['output_dir'] / 'b'
    o_c = build_settings['output_dir'] / 'c'

    paths = [i_a, i_b, i_c]

    b_step = DummyStep()
    all_step = DummyStep()
    context = Context(build_settings, [
        Rule(BMatcher(), [DummyPathCalc(), None], b_step),
        Rule(AllMatcher(), DummyPathCalc(), all_step),
    ])
    tasks = context.match_paths(paths)
    assert tasks == {
        b_step: [
            (i_b, [o_b]),
        ],
        all_step: [
            (i_a, [o_a]),
            (i_c, [o_c]),
        ],
    }
