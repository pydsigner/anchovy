import json
import pathlib
import runpy
import typing as t

import anchovy.cli
from anchovy.core import BuildSettings, Context, ContextDir, Rule
from anchovy.custody import CONTEXT_DIR_KEYS


MTIME_MODE_NONE = 0
MTIME_MODE_NE = 1
MTIME_MODE_EQ = 2


def get_context_dir(context: Context, key: str):
    path = pathlib.Path(key)
    if key in CONTEXT_DIR_KEYS:
        return key
    return t.cast('ContextDir', str(path.parents[-2]))


def load_example(path: pathlib.Path):
    return runpy.run_path(str(path))


def load_artifact(path: pathlib.Path):
    with path.open() as file:
        return json.load(file)


def load_context(path: pathlib.Path, tmp_dir: pathlib.Path, purge_dirs: bool = False):
    module_items = load_example(path)
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


def run_example(path: pathlib.Path, tmp_dir: pathlib.Path, purge_dirs: bool = False):
    context = load_context(path, tmp_dir, purge_dirs)
    context.run()
    return context


def run_example_cli(path: pathlib.Path, tmp_dir: pathlib.Path, purge_dirs: bool = False):
    context = load_context(path, tmp_dir, purge_dirs)
    context.custodian.bind(context)

    arguments = [
        str(path),
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
