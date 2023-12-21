import pathlib

import pytest

from anchovy.test_harness import (
    load_artifact, run_example, run_example_cli, compare_artifacts,
    MTIME_MODE_EQ, MTIME_MODE_NE,
)


EXAMPLE_LIST = [
    'basic_site',
    'gallery',
    'code_index',
]
EXAMPLE_PATHS = {
    name: (pathlib.Path(__file__).parent.parent / 'examples/' / f'{name}').with_suffix('.py')
    for name in EXAMPLE_LIST
}


@pytest.mark.parametrize('name', EXAMPLE_LIST)
def test_example(name: str, tmp_path: pathlib.Path):
    old_artifact_path = (pathlib.Path(__file__).parent / 'artifacts' / name).with_suffix('.json')
    old_artifact = load_artifact(old_artifact_path)

    context = run_example(EXAMPLE_PATHS[name], tmp_path)
    if not (new_artifact_path := context['custody_cache']):
        raise RuntimeError(f'No custody artifact generated for {name}')
    new_artifact = load_artifact(new_artifact_path)

    compare_artifacts(old_artifact, new_artifact, context)


@pytest.mark.parametrize('name', EXAMPLE_LIST)
def test_example_rerun(name: str, tmp_path: pathlib.Path):
    """
    Run an example twice without purging, and check that the runs have
    identical output and unchanged mtimes.
    """
    context_one = run_example(EXAMPLE_PATHS[name], tmp_path)
    if not (first_artifact_path := context_one['custody_cache']):
        raise RuntimeError(f'No custody artifact generated for {name} #1')
    first_artifact = load_artifact(first_artifact_path)

    context_two = run_example(EXAMPLE_PATHS[name], tmp_path)
    if not (second_artifact_path := context_two['custody_cache']):
        raise RuntimeError(f'No custody artifact generated for {name} #2')
    second_artifact = load_artifact(second_artifact_path)

    compare_artifacts(first_artifact, second_artifact, context_two, mtime_mode=MTIME_MODE_EQ)


@pytest.mark.parametrize('name', EXAMPLE_LIST)
def test_example_purge(name: str, tmp_path: pathlib.Path):
    """
    Run an example twice while purging, and check that the runs have
    identical output and different mtimes.
    """
    context_one = run_example(EXAMPLE_PATHS[name], tmp_path, purge_dirs=True)
    if not (first_artifact_path := context_one['custody_cache']):
        raise RuntimeError(f'No custody artifact generated for {name} #1')
    first_artifact = load_artifact(first_artifact_path)

    context_two = run_example(EXAMPLE_PATHS[name], tmp_path, purge_dirs=True)
    if not (second_artifact_path := context_two['custody_cache']):
        raise RuntimeError(f'No custody artifact generated for {name} #2')
    second_artifact = load_artifact(second_artifact_path)

    compare_artifacts(first_artifact, second_artifact, context_two, mtime_mode=MTIME_MODE_NE)


@pytest.mark.parametrize('name', EXAMPLE_LIST)
def test_example_cli(name, tmp_path):
    """
    Run an example using the CLI, and check that run has the expected output.
    """
    old_artifact_path = (pathlib.Path(__file__).parent / 'artifacts' / name).with_suffix('.json')
    old_artifact = load_artifact(old_artifact_path)

    # TODO: Figure out why code_index doesn't work with purge_dirs=False.
    context = run_example_cli(EXAMPLE_PATHS[name], tmp_path, purge_dirs=True)
    if not (new_artifact_path := context['custody_cache']):
        raise RuntimeError(f'No custody artifact generated for {name}')
    new_artifact = load_artifact(new_artifact_path)

    compare_artifacts(old_artifact, new_artifact, context)
