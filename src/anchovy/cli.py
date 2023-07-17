from __future__ import annotations

import argparse
import contextlib
import importlib
import sys
import tempfile
import typing as t
from pathlib import Path

from .core import BuildSettings, Context, InputBuildSettings, Rule, Step, StepUnavailableException
from .pretty_utils import print_with_style


class BuildNamespace:
    """
    Internal used to preserve typing between InputBuildSettings, argparse, and
    BuildSettings.
    """
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
    """
    Internal function used by `run_from_rules()` to combine an instance of
    InputBuildSettings with CLI arguments to produce a BuildNamespace, which
    can be easily turned into BuildSettings.
    """
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


def run_from_rules(settings: InputBuildSettings | None,
                   rules: list[Rule],
                   context_cls: t.Type[Context] = Context,
                   **kw):
    """
    Build a new Context from Settings, Rules, and command line arguments. Then,
    execute a build using the new Context.
    """
    final_settings = parse_settings_args(settings, **kw)
    with _wrap_temp(final_settings.working_dir) as working_dir:
        context = context_cls(final_settings.to_build_settings(working_dir), rules)
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
        file=sys.stderr,
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


def main():
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
                context.run()
            elif rules:
                run_from_rules(settings, rules, argv=remaining, prog=f'anchovy {label}')
        except StepUnavailableException as e:
            pprint_missing_deps(e.step)
            sys.exit(1)

    else:
        print_with_style(
            'Anchovy config files must have a RULES or CONTEXT attribute!',
            file=sys.stderr,
            style='red'
        )
        sys.exit(1)
