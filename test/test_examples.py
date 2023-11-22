import json
import pathlib
import runpy
import typing as t

import pytest

import anchovy.cli
from anchovy.core import BuildSettings, Context, ContextDir, Rule
from anchovy.custody import CONTEXT_DIR_KEYS


EXAMPLE_LIST = [
    'basic_site',
    'gallery',
    'code_index',
]
MTIME_MODE_NONE = 0
MTIME_MODE_NE = 1
MTIME_MODE_EQ = 2


def get_context_dir(context: Context, key: str):
    path = pathlib.Path(key)
    if key in CONTEXT_DIR_KEYS:
        return key
    return t.cast('ContextDir', str(path.parents[-2]))


def get_example_path(name: str):
    return (pathlib.Path(__file__).parent.parent / 'examples/' / f'{name}').with_suffix('.py')


def load_example(name: str):
    return runpy.run_path(str(get_example_path(name)))


def load_context(name: str, tmp_dir: pathlib.Path, purge_dirs: bool = False):
    module_items = load_example(name)
    input_dir: pathlib.Path = module_items['SETTINGS']['input_dir']
    artifact_path = tmp_dir / 'artifact.json'

    rules: list[Rule] = module_items['RULES']
    settings = BuildSettings(
        input_dir=input_dir,
        output_dir=tmp_dir / 'output',
        working_dir=tmp_dir / 'working',
        custody_cache=artifact_path,
        purge_dirs=purge_dirs,
    )
    return Context(settings, rules)


def run_example(name: str, tmp_dir: pathlib.Path, purge_dirs: bool = False):
    context = load_context(name, tmp_dir, purge_dirs)
    context.run()
    return context


def run_example_cli(name: str, tmp_dir: pathlib.Path, purge_dirs: bool = False):
    context = load_context(name, tmp_dir, purge_dirs)
    context.custodian.bind(context)

    arguments = [
        str(get_example_path(name)),
        '--custody-cache', str(context['custody_cache'])
    ]
    if purge_dirs:
        arguments.append('--purge')

    anchovy.cli.main(arguments)

    return context


def canonicalize_graph(graph: dict):
    for key, val in graph.items():
        if isinstance(val, list):
            val.sort()
        elif isinstance(val, dict):
            canonicalize_graph(val)

    return graph


def compare_artifacts(old: dict, new: dict, context: Context, mtime_mode=MTIME_MODE_NONE):
    assert canonicalize_graph(new['graph']) == canonicalize_graph(old['graph'])
    assert new['meta'].keys() == old['meta'].keys()
    for key in new['meta']:
        n_type, n_dict = new['meta'][key]
        o_type, o_dict = old['meta'][key]
        print(f'{key}:\n new={n_dict}\n old={o_dict}')
        assert n_type == o_type
        if n_type == 'path':
            context_dir = get_context_dir(context, key)
            path = context.custodian.degenericize_path(key)
            if path.is_dir():
                continue
            try:
                assert n_dict['sha1'] == o_dict['sha1']
                assert n_dict['size'] == o_dict['size']
                if mtime_mode == MTIME_MODE_NE and context_dir != 'input_dir':
                    assert n_dict['m_time'] != o_dict['m_time']
                elif mtime_mode == MTIME_MODE_EQ:
                    assert n_dict['m_time'] == o_dict['m_time']
            except AssertionError:
                print(path.read_bytes())
                raise
        else:
            assert n_dict.keys() == o_dict.keys()


@pytest.mark.parametrize('name', EXAMPLE_LIST)
def test_example(name: str, tmp_path: pathlib.Path):
    old_artifact_path = (pathlib.Path(__file__).parent / 'artifacts' / name).with_suffix('.json')
    with open(old_artifact_path) as file:
        old_artifact = json.load(file)
    context = run_example(name, tmp_path)
    if not (new_artifact_path := context['custody_cache']):
        raise RuntimeError(f'No custody artifact generated for {name}')
    with open(new_artifact_path) as file:
        new_artifact = json.load(file)
    compare_artifacts(old_artifact, new_artifact, context)


@pytest.mark.parametrize('name', EXAMPLE_LIST)
def test_example_rerun(name: str, tmp_path: pathlib.Path):
    """
    Run an example twice without purging, and check that the runs have
    identical output and unchanged mtimes.
    """
    context_one = run_example(name, tmp_path)
    if not (first_artifact_path := context_one['custody_cache']):
        raise RuntimeError(f'No custody artifact generated for {name} #1')
    with open(first_artifact_path) as file:
        first_artifact = json.load(file)
    context_two = run_example(name, tmp_path)
    if not (second_artifact_path := context_two['custody_cache']):
        raise RuntimeError(f'No custody artifact generated for {name} #2')
    with open(second_artifact_path) as file:
        second_artifact = json.load(file)
    compare_artifacts(first_artifact, second_artifact, context_two, mtime_mode=MTIME_MODE_EQ)


@pytest.mark.parametrize('name', EXAMPLE_LIST)
def test_example_purge(name: str, tmp_path: pathlib.Path):
    """
    Run an example twice while purging, and check that the runs have
    identical output and different mtimes.
    """
    context_one = run_example(name, tmp_path, purge_dirs=True)
    if not (first_artifact_path := context_one['custody_cache']):
        raise RuntimeError(f'No custody artifact generated for {name} #1')
    with open(first_artifact_path) as file:
        first_artifact = json.load(file)

    context_two = run_example(name, tmp_path, purge_dirs=True)
    if not (second_artifact_path := context_two['custody_cache']):
        raise RuntimeError(f'No custody artifact generated for {name} #2')
    with open(second_artifact_path) as file:
        second_artifact = json.load(file)
    compare_artifacts(first_artifact, second_artifact, context_two, mtime_mode=MTIME_MODE_NE)


@pytest.mark.parametrize('name', EXAMPLE_LIST)
def test_example_cli(name, tmp_path):
    """
    Run an example using the CLI, and check that run has the expected output.
    """
    old_artifact_path = (pathlib.Path(__file__).parent / 'artifacts' / name).with_suffix('.json')
    with open(old_artifact_path) as file:
        old_artifact = json.load(file)
    # TODO: Figure out why code_index doesn't work with purge_dirs=False.
    context = run_example_cli(name, tmp_path, purge_dirs=True)
    if not (new_artifact_path := context['custody_cache']):
        raise RuntimeError(f'No custody artifact generated for {name}')
    with open(new_artifact_path) as file:
        new_artifact = json.load(file)
    compare_artifacts(old_artifact, new_artifact, context)
