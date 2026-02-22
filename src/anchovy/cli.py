"""
This is the toolkit for Anchovy's own CLI, but offers an accessible API for
building project-specific CLIs.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import runpy
import sys
import tempfile
import typing as t
from pathlib import Path

from .core import BuildSettings, Context, InputBuildSettings, Rule, Step, StepUnavailableException
from .custody import Custodian
from .pretty_utils import print_with_style


DEFAULT_SETTINGS = InputBuildSettings(
    input_dir=Path('site'),
    output_dir=Path('output'),
    working_dir=None,
    custody_cache=None,
    purge_dirs=None,
)


class BuildNamespace:
    """
    Internal used to preserve typing between InputBuildSettings, argparse, and
    BuildSettings.
    """
    input_dir: Path
    output_dir: Path
    working_dir: Path | None
    custody_cache: Path | None
    purge_dirs: bool | None

    def __init__(self, settings: InputBuildSettings | None = None):
        if settings:
            self.load_settings(settings)

    def __repr__(self):
        return f'{self.__class__.__name__}({", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())})'

    def load_settings(self, settings: InputBuildSettings):
        """
        Load settings from an InputBuildSettings into this namespace. Any
        settings already present will be preserved.
        """
        for k, v in settings.items():
            if k not in self.__dict__:
                self.__dict__[k] = v

    def to_build_settings(self, resolved_working_dir: Path):
        """
        Convert this argparse-oriented namespace into a Context-ready
        BuildSettings.
        """
        purge_dirs = self.purge_dirs
        if purge_dirs is None and self.custody_cache is None:
            purge_dirs = True
        return BuildSettings(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            working_dir=resolved_working_dir,
            custody_cache=self.custody_cache,
            purge_dirs=purge_dirs
        )


class CLINamespace(BuildNamespace):
    """
    A BuildNamespace with additional attributes for CLI arguments.
    """
    help: bool
    audit_steps: bool
    module: t.Any
    config_file: Path | None
    serve: bool
    port: int


@contextlib.contextmanager
def _wrap_temp(path: Path | None):
    if path:
        yield path
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)


def install_settings_args(parser: argparse.ArgumentParser):
    """
    Add arguments for the standard Anchovy settings to the given ArgumentParser.
    """
    parser.add_argument('-i', '--input',
                        help='input directory with raw files to process',
                        type=Path,
                        dest='input_dir',
                        default=argparse.SUPPRESS)
    parser.add_argument('-o', '--output',
                        help='output directory for final built files',
                        type=Path,
                        dest='output_dir',
                        default=argparse.SUPPRESS)

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-w', '--working',
                       help='directory for intermediate files; defaults to a new temporary directory',
                       type=Path,
                       dest='working_dir',
                       default=argparse.SUPPRESS)
    group.add_argument('--use-temporary',
                       help='force use of a temporary directory for intermediate files',
                       action='store_const',
                       dest='working_dir',
                       const=None,
                       default=argparse.SUPPRESS)

    parser.add_argument('--custody-cache',
                        help='path to a cache file for chain of custody and change detection',
                        type=Path,
                        default=argparse.SUPPRESS)
    parser.add_argument('--purge',
                        help='purge the output directory before building',
                        action=argparse.BooleanOptionalAction,
                        dest='purge_dirs',
                        default=argparse.SUPPRESS)


def parse_settings_args(settings: InputBuildSettings | None = None, argv: list[str] | None = None, **kw):
    """
    Internal function used by `run_from_rules()` to combine an instance of
    InputBuildSettings with CLI arguments to produce a BuildNamespace, which
    can be easily turned into BuildSettings.
    """
    namespace = BuildNamespace(settings)
    parser = argparse.ArgumentParser(**kw)
    install_settings_args(parser)
    return parser.parse_args(argv, namespace=namespace)


def run_from_rules(settings: InputBuildSettings | BuildNamespace | None,
                   rules: list[Rule],
                   custodian: Custodian | None = None,
                   context_cls: t.Type[Context] = Context,
                   **kw):
    """
    Build a new Context from Settings, Rules, and command line arguments. Then,
    execute a build using the new Context. A Custodian and a custom Context
    class may be additionally supplied.
    """
    if not isinstance(settings, BuildNamespace):
        settings = parse_settings_args(settings, **kw)
    settings.load_settings(DEFAULT_SETTINGS)
    with _wrap_temp(settings.working_dir) as working_dir:
        context = context_cls(settings.to_build_settings(working_dir), rules, custodian)
        context.run()


def run_from_context(context: Context, args: BuildNamespace | None = None):
    """
    Update the given Context with command line arguments, then execute a build
    using it.
    """
    if args:
        context.settings.update(**args.__dict__)
    with _wrap_temp(context.settings['working_dir']) as working_dir:
        context.settings['working_dir'] = working_dir
        context.run()


def pprint_step(step: t.Type[Step]):
    """
    Prettily display dependency information for the given Step class.
    """
    missing = [
        str(d) for d in step.get_dependencies()
        if d.needed and not d.satisfied

    ]
    if missing:
        text = ', '.join(missing)
        print_with_style(f'✗ {step.__name__} (missing: {text})', style='red')
    else:
        print_with_style(f'✓ {step.__name__}', style='green')


def pprint_missing_deps(step: Step):
    """
    Prettily display an error for the given Step with missing dependencies.
    """
    print_with_style(
        f'{step} is unavailable due to missing dependencies!',
        file='stderr',
        style='red'
    )
    for dep in step.get_dependencies():
        missing = False
        if not dep.needed:
            style = None
        elif dep.satisfied:
            style = 'green'
        else:
            missing = True
            style = 'red'

        text = f'✗ {dep}: {dep.install_hint}' if missing else f'✓ {dep}'
        print_with_style(text, style=style)


def main(arguments: list[str] | None = None):
    """
    Anchovy main function. Finds or creates a Context using an Anchovy config
    file and command line arguments, then executes a build using it.
    """
    parser = argparse.ArgumentParser(description='Build an anchovy project.')
    parser.add_argument('--audit-steps',
                        help=('show information about available, unavailable, '
                              'and used steps, instead of building the project'),
                        action='store_true')
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
    parser.add_argument('-s', '--serve',
                       help='serve the output directory over HTTP after building',
                       action='store_true')
    parser.add_argument('-p', '--port',
                       help='port to serve from',
                       type=int,
                       default=8080)
    install_settings_args(parser)
    args = parser.parse_args(arguments, namespace=CLINamespace())

    if args.config_file:
        label: str = str(args.config_file)
        namespace = runpy.run_path(label)

        settings: InputBuildSettings | None = namespace.get('SETTINGS')
        rules: list[Rule] | None = namespace.get('RULES')
        custodian: Custodian | None = namespace.get('CUSTODIAN')
        context: Context | None = namespace.get('CONTEXT')
    else:
        label: str = f'-m {args.module.__name__}'
        settings: InputBuildSettings | None = getattr(args.module, 'SETTINGS', None)
        rules: list[Rule] | None = getattr(args.module, 'RULES', None)
        custodian: Custodian | None = getattr(args.module, 'CUSTODIAN', None)
        context: Context | None = getattr(args.module, 'CONTEXT', None)

    if args.audit_steps:
        audit_rules = context.rules if context else rules
        if not audit_rules:
            raise RuntimeError('Anchovy config files must have a RULES or CONTEXT attribute!')

        all_steps = set(Step.get_all_steps())
        available_steps = set(Step.get_available_steps())
        unavailable_steps = all_steps - available_steps
        used_steps = {r.step.__class__ for r in audit_rules if r.step}

        groups = {
            'Available steps': available_steps,
            'Unavailable steps': unavailable_steps,
            'Used steps': used_steps,
        }
        for group_label, step_group in groups.items():
            print(f'{group_label} ({len(step_group)})')
            for step in step_group:
                pprint_step(step)

    elif context or rules:
        try:
            if context:
                run_from_context(context, args)
            elif rules:
                if settings:
                    args.load_settings(settings)
                run_from_rules(args, rules, custodian)
        except StepUnavailableException as e:
            pprint_missing_deps(e.step)
            sys.exit(1)

    else:
        print_with_style(
            'Anchovy config files must have a RULES or CONTEXT attribute!',
            file='stderr',
            style='red'
        )
        sys.exit(1)

    if args.serve:
        from .server import serve
        serve(args.port, args.output_dir)
