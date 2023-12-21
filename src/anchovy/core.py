"""
Core classes and types for the Anchovy processing pipeline.
"""
from __future__ import annotations

import abc
import shutil
import typing as t
from pathlib import Path

from .custody import CustodyEntry, Custodian
from .dependencies import Dependency
from .pretty_utils import track_progress

if t.TYPE_CHECKING:
    from collections.abc import Sequence, Set


T = t.TypeVar('T')
T2 = t.TypeVar('T2')
ContextDir = t.Literal['input_dir', 'output_dir', 'working_dir']
BuildSettingsKey = t.Literal[ContextDir, 'custody_cache', 'purge_dirs']


class InputBuildSettings(t.TypedDict, total=False):
    """
    TypedDict for defining build settings in an Anchovy config file.
    """
    input_dir: Path
    output_dir: Path
    working_dir: Path | None
    custody_cache: Path | None
    purge_dirs: bool | None

class BuildSettings(t.TypedDict):
    """
    TypedDict for processed build settings ready for passing to Context.
    """
    input_dir: Path
    output_dir: Path
    working_dir: Path
    custody_cache: Path | None
    purge_dirs: bool | None


def _rm_children(path: Path):
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _rm_orphans(path: Path, exclude: set[Path]):
    if not path.exists():
        return False
    removed_all = True
    for child in path.iterdir():
        if child in exclude:
            removed_all = False
            continue
        if child.is_dir():
            if _rm_orphans(child, exclude):
                child.rmdir()
            else:
                removed_all = False
        else:
            child.unlink()
    return removed_all


class Context:
    """
    A context and configuration class for building Anchovy projects.
    """
    def __init__(self,
                 settings: BuildSettings,
                 rules: list[Rule],
                 custodian: Custodian | None = None):
        self.settings = settings
        # Must set up the Custodian before the Rules so the Rules can install
        # checkers when they're bound.
        self.custodian = custodian or Custodian()
        self.rules: list[Rule] = []
        for rule in rules:
            self.rules.append(rule)
            self.bind(rule.step)

    @t.overload
    def __getitem__(self, key: ContextDir) -> Path: ...
    @t.overload
    def __getitem__(self, key: t.Literal['custody_cache']) -> Path | None: ...
    @t.overload
    def __getitem__(self, key: t.Literal['purge_dirs']) -> bool | None: ...
    def __getitem__(self, key):
        return self.settings[key]

    def bind(self, step: Step | None):
        """
        Bind a Step to this Context, checking to ensure its availability.
        """
        if step:
            if not step.is_available():
                raise StepUnavailableException(step)
            step.bind(self)

    def find_inputs(self, path: Path):
        """
        Overridable function to get paths to process based on a given @path.
        Default behavior is to recursively search for files but exclude the
        directories themselves.
        """
        for candidate in path.iterdir():
            if candidate.is_dir():
                yield from self.find_inputs(candidate)
            else:
                yield candidate

    def match_paths(self, input_paths: list[Path]):
        """
        Match a set of input paths against the Context's defined Rules, and
        associate them with the Steps of those Rules.
        """
        # We want to handle tasks in the order they're defined!
        tasks: dict[Step, list[tuple[Path, list[Path]]]]
        tasks = {r.step: [] for r in self.rules if r.step}

        for path in track_progress(input_paths, 'Planning...'):
            for rule in self.rules:
                if match := rule.matcher(self, path):
                    # None can be used to halt further rule processing.
                    if not rule.step:
                        break
                    output_paths: list[Path] = []
                    for pathcalc in rule.path_calcs:
                        # None can be used to halt further rule processing in
                        # paths as well. This allows a single rule to both do
                        # processing and also halt further processing.
                        if not pathcalc:
                            break
                        output_paths.append(pathcalc(self, path, match))
                    else:
                        tasks[rule.step].append((path, output_paths))
                        # We didn't break above, avoid the break below!
                        continue
                    tasks[rule.step].append((path, output_paths))
                    # We need two breaks because we're trying to get out of the
                    # surrounding for loop.
                    break

        return tasks

    def process(self, input_paths: list[Path] | None = None):
        """
        Process a set of files using the Context's defined rules. If
        @input_paths is empty or None, `self.find_inputs()` will be used to get
        a tree of files to process. If intermediate files are produced,
        `self.process()` will be called recursively with them.
        """
        input_paths = input_paths or list(self.find_inputs(self.settings['input_dir']))

        tasks = self.match_paths(input_paths)

        flattened: list[tuple[Step, Path, list[Path]]] = []
        for step, paths in tasks.items():
            flattened.extend((step, p, ops) for p, ops in paths)

        further_processing: list[Path] = []
        for step, path, output_paths in track_progress(flattened, 'Processing...'):
            stale, msg = self.custodian.refresh_needed(path, output_paths)
            if stale:
                explicit_chain = step(path, output_paths)
                if explicit_chain:
                    sources, output_paths = explicit_chain
                else:
                    sources = [path]
                self.custodian.add_step(sources, output_paths, msg)
            else:
                output_paths = self.custodian.skip_step(path, output_paths)

            further_processing.extend(
                p for p in output_paths
                if p.is_relative_to(self['working_dir'])
            )

        if further_processing:
            self.process(further_processing)

    def run(self, input_paths: list[Path] | None = None):
        """
        Execute pre-run hooks (currently only the baked-in directory purge),
        then call `self.process()` with @input_paths.
        TODO: Support custom pre/post hooks.
        """
        if self['purge_dirs']:
            _rm_children(self['output_dir'])
            _rm_children(self['working_dir'])
        self.custodian.bind(self)
        if cache_file := self['custody_cache']:
            self.custodian.load_file(cache_file)
        self.process(input_paths)
        if cache_file:
            self.custodian.dump_file(cache_file)
            if self['purge_dirs'] is None:
                touched = set(self.custodian.get_all_paths())
                _rm_orphans(self['output_dir'], touched)
                _rm_orphans(self['working_dir'], touched)


class Matcher(t.Generic[T], abc.ABC):
    """
    Abstract base class for Path Matchers. Provides pre-baked ability to
    combine Matchers with | and &.
    """
    @abc.abstractmethod
    def __call__(self, context: Context, path: Path) -> T:
        ...

    def __or__(self, other: Matcher[T2]):
        return _OrMatcher(self, other)

    def __and__(self, other: Matcher[T2]):
        return _AndMatcher(self, other)


class _OrMatcher(Matcher[T | T2]):
    def __init__(self, left: Matcher[T], right: Matcher[T2]):
        self.left = left
        self.right = right

    def __call__(self, context: Context, path: Path):
        return self.left(context, path) or self.right(context, path)


class _AndMatcher(Matcher[T | T2]):
    def __init__(self, left: Matcher[T], right: Matcher[T2]):
        self.left = left
        self.right = right

    def __call__(self, context: Context, path: Path):
        return self.left(context, path) and self.right(context, path)


class PathCalc(t.Generic[T], abc.ABC):
    """
    Abstract base class for path calculators which use `Matcher` match data to
    determine output paths from input paths.
    """
    @abc.abstractmethod
    def __call__(self, context: Context, path: Path, match: T) -> Path:
        ...


class Rule(t.Generic[T]):
    """
    A single rule for Anchovy file processing, with a matcher, output path
    calculators, and an optional Step to run.
    """
    def __init__(self,
                 matcher: Matcher[T],
                 path_calc: t.Sequence[PathCalc[T] | Path | None] | PathCalc[T] | Path | None,
                 step: Step | None = None):
        self.matcher = matcher
        self.step = step
        if not isinstance(path_calc, t.Sequence):
            path_calc = [path_calc]
        self.path_calcs = [self._path_to_pathcalc(p) if isinstance(p, Path) else p for p in path_calc]

    def _path_to_pathcalc(self, path: Path):
        # pylint: disable=unused-argument
        def wrapper(context: Context, input_path: Path, match: t.Any):
            return path
        return wrapper


class Step(abc.ABC):
    """
    Abstract base class for Steps, individual processing stages used to build a
    full Anchovy ruleset.
    """
    context: Context
    _step_registry: list[t.Type[Step]] = []

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        cls._step_registry.append(cls)

    @classmethod
    def get_all_steps(cls):
        """
        Return a list of all currently known Steps.
        """
        return list(cls._step_registry)

    @classmethod
    def get_available_steps(cls):
        """
        Return a list of all currently known Steps whose requirements are met.
        """
        return [s for s in cls._step_registry if s.is_available()]

    @classmethod
    def is_available(cls) -> bool:
        """
        Return whether this Step's requirements are installed, making it
        available for use.
        """
        return all(d.satisfied for d in cls.get_dependencies())

    @classmethod
    def get_dependencies(cls) -> Set[Dependency]:
        """
        Return the requirements for this Step.
        """
        return set()

    def bind(self, context: Context):
        """
        Bind this Step to a Context.
        """
        self.context = context

    @abc.abstractmethod
    def __call__(
        self,
        path: Path,
        output_paths: list[Path]
    ) -> None | tuple[Sequence[Path | CustodyEntry], list[Path]]:
        ...


class StepUnavailableException(Exception):
    """
    Exception raised with a step to be used is unavailable due to missing
    dependencies.
    """
    def __init__(self, step: Step, *args: t.Any):
        self.step = step
        super().__init__(*args)
