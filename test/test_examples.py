import json
import pathlib
import runpy
import typing as t

import pytest

from anchovy.core import BuildSettings, Context, Rule


def load_example(name: str):
    path = (pathlib.Path(__file__).parent.parent / 'examples/' / f'{name}').with_suffix('.py')
    return runpy.run_path(str(path))


def run_example(module_items: dict[str, t.Any], tmp_dir: pathlib.Path):
    input_dir: pathlib.Path = module_items['SETTINGS']['input_dir']
    artifact_path = tmp_dir / 'artifact.json'

    rules: list[Rule] = module_items['RULES']
    settings = BuildSettings(
        input_dir=input_dir,
        output_dir=tmp_dir / 'output',
        working_dir=tmp_dir / 'working',
        custody_cache=artifact_path,
        purge_dirs=False
    )
    context = Context(settings, rules)
    context.run()
    return artifact_path


def compare_artifacts(old: dict, new: dict):
    assert new['graph'] == old['graph']
    assert new['meta'].keys() == old['meta'].keys()
    for key in new['meta']:
        n_type, n_dict = new['meta'][key]
        o_type, o_dict = old['meta'][key]
        print(f'{key}:\n new={n_dict}\n old={o_dict}')
        assert n_type == o_type
        if n_type == 'path':
            assert n_dict['sha1'] == o_dict['sha1']
            assert n_dict['size'] == o_dict['size']
        else:
            assert n_dict.keys() == o_dict.keys()


@pytest.mark.parametrize('name', [
    'basic_site',
    'gallery',
])
def test_example(name, tmp_path):
    module_items = load_example(name)
    old_artifact_path = (pathlib.Path(__file__).parent / 'artifacts' / name).with_suffix('.json')
    with open(old_artifact_path) as file:
        old_artifact = json.load(file)
    new_artifact_path = run_example(module_items, tmp_path)
    with open(new_artifact_path) as file:
        new_artifact = json.load(file)
    compare_artifacts(old_artifact, new_artifact)
