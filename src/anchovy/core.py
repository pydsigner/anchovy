from __future__ import annotations

import abc
import functools
import re
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
StepFunc = t.Callable[[Path, re.Match[str], 'Context'], t.Iterable[Path]]
UnboundStep = t.Union[StepFunc, 'Step', None]
Rule = tuple[str, UnboundStep]
BoundStep = t.Callable[[Path, re.Match[str]], t.Iterable[Path]]
BuildSettingsKey = t.Literal['input_dir', 'output_dir', 'working_dir', 'purge_dirs']


class InputBuildSettings(t.TypedDict, total=False):
    input_dir: Path
    output_dir: Path
    working_dir: Path | None
    purge_dirs: bool

class BuildSettings(t.TypedDict):
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
    def __init__(self,
                 settings: BuildSettings,
                 rules: list[Rule]):
        self.settings = settings
        self.rules = [(re.compile(r), self.bind(f)) for r, f in rules]

    @t.overload
    def __getitem__(self, key: t.Literal['input_dir', 'output_dir', 'working_dir']) -> Path: ...
    @t.overload
    def __getitem__(self, key: t.Literal['purge_dirs']) -> bool: ...
    def __getitem__(self, key):
        return self.settings[key]

    def bind(self, step: UnboundStep) -> BoundStep | None:
        if not step:
            return

        if isinstance(step, Step):
            step.bind(self)
            return step

        @functools.wraps(step)
        def bound(path: Path, match: re.Match[str]):
            return step(path, match, self)
        return bound

    def find_inputs(self, path: Path):
        for candidate in path.iterdir():
            if candidate.is_dir():
                yield from self.find_inputs(candidate)
            else:
                yield candidate

    def process(self, input_paths: list[Path] | None = None):
        input_paths = input_paths or list(self.find_inputs(self.settings['input_dir']))
        # We want to handle tasks in the order they're defined!
        tasks: dict[BoundStep, list[tuple[Path, re.Match[str]]]]
        tasks = {step: [] for test, step in self.rules if step}

        for path in _progress(input_paths, 'Planning...'):
            for test, step in self.rules:
                if match := test.match(str(path)):
                    # None can be used to halt further rule processing.
                    if not step:
                        break
                    tasks[step].append((path, match))

        flattened: list[tuple[BoundStep, Path, re.Match[str]]] = []
        for step, paths in tasks.items():
            flattened.extend((step, p, m) for p, m in paths)

        further_processing: list[Path] = []
        for step, path, match in _progress(flattened, 'Processing...'):
            new_paths = list(step(path, match))
            print(f'{path} ⇒ {", ".join(str(p) for p in new_paths)}')
            further_processing.extend(p for p in new_paths if p.is_relative_to(self['working_dir']))

        if further_processing:
            self.process(further_processing)

    def run(self, input_paths: list[Path] | None = None):
        if self['purge_dirs']:
            _rm_children(self['output_dir'])
            _rm_children(self['working_dir'])
        self.process(input_paths)


class Step(abc.ABC):
    context: Context

    def bind(self, context: Context):
        self.context = context

    @abc.abstractmethod
    def __call__(self, path: Path, match: re.Match[str]) -> t.Iterable[Path]:
        ...
