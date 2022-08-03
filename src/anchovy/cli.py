from __future__ import annotations

import argparse
import contextlib
import importlib
import tempfile
import typing as t
from pathlib import Path

from .core import BuildSettings, Context, InputBuildSettings, Rule


class BuildNamespace:
    input_dir: Path
    output_dir: Path
    working_dir: Path | None
    purge_dirs: bool

    def __init__(self, settings: InputBuildSettings | None = None):
        if settings:
            self.__dict__.update(settings)

    # FIXME: Gross :(
    def to_build_settings(self, working_dir: Path):
        return BuildSettings(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            working_dir=working_dir,
            purge_dirs=self.purge_dirs
        )


@contextlib.contextmanager
def _wrap_temp(path: Path | None):
    if path:
        yield path
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)


def parse_settings_args(settings: InputBuildSettings | None = None, argv: list[str] | None = None, **kw):
    namespace = BuildNamespace(settings)

    parser = argparse.ArgumentParser(**kw)
    parser.add_argument('-i', '--input',
                        help='input directory with raw files to process',
                        type=Path,
                        dest='input_dir',
                        default=Path('site'))
    parser.add_argument('-o', '--output',
                        help='output directory for final built files',
                        type=Path,
                        dest='output_dir',
                        default=Path('output'))

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-w', '--working',
                       help='directory for intermediate files; defaults to a new temporary directory',
                       type=Path,
                       dest='working_dir')
    group.add_argument('--use-temporary',
                       help='force use of a temporary directory for intermediate files',
                       action='store_const',
                       dest='working_dir',
                       const=None)

    parser.add_argument('--purge',
                        help='purge the output directory before building',
                        action=argparse.BooleanOptionalAction,
                        dest='purge_dirs',
                        default=True)

    return parser.parse_args(argv, namespace=namespace)


def run_from_rules(settings: InputBuildSettings | None, rules: list[Rule], **kw):
    final_settings = parse_settings_args(settings, **kw)
    with _wrap_temp(final_settings.working_dir) as working_dir:
        context = Context(final_settings.to_build_settings(working_dir), rules)
        context.run()


def main():
    parser = argparse.ArgumentParser(description='Build an anchovy project.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-m',
                       help='import path of a config file to build',
                       type=importlib.import_module,
                       dest='module',
                       default=None)
    group.add_argument('config_file',
                       nargs='?',
                       help='file path to a config file to build',
                       type=Path,
                       default=None)

    args, remaining = parser.parse_known_args()

    if args.config_file:
        label: str = str(args.config_file)

        namespace: dict[str, t.Any] = {'__file__': label}
        with open(args.config_file) as file:
            # We're basically emulating the python command line here.
            # pylint: disable=exec-used
            exec(file.read(), namespace)

        settings: InputBuildSettings | None = namespace.get('SETTINGS')
        rules: list[Rule] | None = namespace.get('RULES')
        context: Context | None = namespace.get('CONTEXT')
    else:
        label: str = f'-m {args.module.__name__}'
        settings: InputBuildSettings | None = getattr(args.module, 'SETTINGS')
        rules: list[Rule] | None = getattr(args.module, 'RULES')
        context: Context | None = getattr(args.module, 'CONTEXT')

    if context:
        context.run()
    else:
        if not rules:
            raise RuntimeError('Anchovy config files must have a RULES or CONTEXT attribute!')
        run_from_rules(settings, rules, argv=remaining, prog=f'anchovy {label}')
