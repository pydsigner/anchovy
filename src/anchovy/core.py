from __future__ import annotations

import abc
import functools
import shutil
import typing as t
from pathlib import Path

try:
    import rich.progress as _rich_progress
except ImportError:
    _rich_progress = None
try:
    import tqdm as _tqdm
except ImportError:
    _tqdm = None


T = t.TypeVar('T')
StepFunc = t.Callable[['Context', Path, list[Path]], t.Any]
UnboundStep = t.Union[StepFunc, 'Step'] | None
PathCalc = t.Callable[['Context', Path, T], Path] | None
BoundStep = t.Callable[[Path, list[Path]], t.Any]
BuildSettingsKey = t.Literal['input_dir', 'output_dir', 'working_dir', 'purge_dirs']


class InputBuildSettings(t.TypedDict, total=False):
    """
    TypedDict for defining build settings in an Anchovy config file.
    """
    input_dir: Path
    output_dir: Path
    working_dir: Path | None
    purge_dirs: bool

class BuildSettings(t.TypedDict):
    """
    TypedDict for processed build settings ready for passing to Context.
    """
    input_dir: Path
    output_dir: Path
    working_dir: Path
    purge_dirs: bool


def _progress(iterable: t.Iterable[T], desc: str) -> t.Iterable[T]:
    if _rich_progress:
        yield from _rich_progress.track(iterable, desc)
    elif _tqdm is not None:
        yield from _tqdm.tqdm(iterable, desc)
    else:
        print(desc)
        yield from iterable


def _rm_children(path: Path):
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


class Context:
    """
    A context and configuration class for building Anchovy projects.
    """
    def __init__(self,
                 settings: BuildSettings,
                 rules: list[Rule]):
        self.settings = settings
        self.rules = [(r, self.bind(r.step)) for r in rules]

    @t.overload
    def __getitem__(self, key: t.Literal['input_dir', 'output_dir', 'working_dir']) -> Path: ...
    @t.overload
    def __getitem__(self, key: t.Literal['purge_dirs']) -> bool: ...
    def __getitem__(self, key):
        return self.settings[key]

    def bind(self, step: UnboundStep) -> BoundStep | None:
        """
        Bind a Step to this Context. Calls the `bind()` method on class Steps,
        and creates a partial for function Steps.
        """
        if not step:
            return

        if isinstance(step, Step):
            step.bind(self)
            return step

        @functools.wraps(step)
        def bound(path: Path, output_paths: list[Path]):
            return step(self, path, output_paths)
        return bound

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

    def process(self, input_paths: list[Path] | None = None):
        """
        Process a set of files using the Context's defined rules. If
        @input_paths is empty or None, `self.find_inputs()` will be used to get
        a tree of files to process. If intermediate files are produced,
        `self.process()` will be called recursively with them.
        """
        input_paths = input_paths or list(self.find_inputs(self.settings['input_dir']))
        # We want to handle tasks in the order they're defined!
        tasks: dict[BoundStep, list[tuple[Path, list[Path]]]]
        tasks = {step: [] for rule, step in self.rules if step}

        for path in _progress(input_paths, 'Planning...'):
            for rule, step in self.rules:
                if match := rule.match(self, path):
                    # None can be used to halt further rule processing.
                    if not step:
                        break
                    output_paths: list[Path] = []
                    for pathcalc in rule.pathcalcs:
                        # None can be used to halt further rule processing in
                        # paths as well. This allows a single rule to both do
                        # processing and also halt further processing.
                        if not pathcalc:
                            break
                        output_paths.append(pathcalc(self, path, match))
                    else:
                        tasks[step].append((path, output_paths))
                        # We didn't break above, avoid the break below!
                        continue
                    tasks[step].append((path, output_paths))
                    # We need two breaks because we're trying to get out of the
                    # surrounding for loop.
                    break

        flattened: list[tuple[BoundStep, Path, list[Path]]] = []
        for step, paths in tasks.items():
            flattened.extend((step, p, ops) for p, ops in paths)

        further_processing: list[Path] = []
        for step, path, output_paths in _progress(flattened, 'Processing...'):
            print(f'{path} ⇒ {", ".join(str(p) for p in output_paths)}')
            step(path, output_paths)
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
        self.process(input_paths)


class Rule(t.Generic[T]):
    """
    A single rule for Anchovy file processing, with a matcher, output path
    calculators, and an optional Step to run.
    """
    match: t.Callable[[Context, Path], T | None]
    pathcalcs: list[PathCalc[T] ]
    step: UnboundStep

    def __init__(self,
                 match: t.Callable[[Context, Path], T | None],
                 pathcalc: t.Sequence[PathCalc[T] | Path ] | PathCalc[T] | Path,
                 step: UnboundStep = None):
        self.match = match
        self.step = step
        if not isinstance(pathcalc, t.Sequence):
            pathcalc = [pathcalc]
        self.pathcalcs = [self._path_to_pathcalc(p) if isinstance(p, Path) else p for p in pathcalc]

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

    def bind(self, context: Context):
        """
        Bind this Step to a Context.
        """
        self.context = context

    @abc.abstractmethod
    def __call__(self, path: Path, output_paths: list[Path]):
        ...
