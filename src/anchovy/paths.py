import re
import typing as t
from pathlib import Path

from .core import Context, ContextDir, Matcher, PathCalc


T = t.TypeVar('T')


def _trim_ext_prefix(path: Path, match: re.Match[str]):
    _groups = match.groupdict()
    if 'stem' in _groups:
        return path.with_stem(_groups['stem'])
    if 'ext' in _groups and _groups['ext']:
        return path.with_name(path.name[:-len(_groups['ext'])])
    return path


def _to_dir_inner(dest: Path,
                  ext: str | None,
                  context: Context,
                  path: Path,
                  match: t.Any,
                  transform: t.Callable[[Path], Path] | None = None):
    path = _trim_ext_prefix(path, match) if ext and isinstance(match, re.Match) else path

    rel = path.relative_to(
        context['input_dir']
        if path.is_relative_to(context['input_dir'])
        else context['working_dir']
    )
    if transform:
        rel = transform(rel)
    new_path = dest / rel

    if ext:
        new_path = new_path.with_suffix(ext)

    return new_path


class DirPathCalc(PathCalc[T]):
    """
    PathCalc which makes its input paths children of a specified directory.
    If @ext is specified, it will replace the extension of input paths. If the
    matcher produced an re.Match, it will be checked for explicitly defined
    extension information for the input paths, allowing for meaningful work
    with extensions that `pathlib.Path` does not reflect, like `.tar.gz`.
    """
    def __init__(self, dest: Path, ext: str | None = None, transform: t.Callable[[Path], Path] | None = None):
        self.dest = dest
        self.ext = ext
        self.transform = transform

    def __call__(self, context: Context, path: Path, match: T) -> Path:
        return _to_dir_inner(self.dest, self.ext, context, path, match, self.transform)


class OutputDirPathCalc(PathCalc[T]):
    """
    PathCalc which makes its input paths children of the Context's output
    directory. If @ext is specified, it will replace the extension of input
    paths. If the matcher produced an re.Match, it will be checked for
    explicitly defined extension information for the input paths, allowing for
    meaningful work with extensions that `pathlib.Path` does not reflect, like
    `.tar.gz`.
    """
    def __init__(self, ext: str | None = None, transform: t.Callable[[Path], Path] | None = None):
        self.ext = ext
        self.transform = transform

    def __call__(self, context: Context, path: Path, match: T) -> Path:
        return _to_dir_inner(context['output_dir'], self.ext, context, path, match, self.transform)


class WorkingDirPathCalc(PathCalc[T]):
    """
    PathCalc which makes its input paths children of the Context's working
    directory. If @ext is specified, it will replace the extension of input
    paths. If the matcher produced an re.Match, it will be checked for
    explicitly defined extension information for the input paths, allowing for
    meaningful work with extensions that `pathlib.Path` does not reflect, like
    `.tar.gz`.
    """
    def __init__(self, ext: str | None = None, transform: t.Callable[[Path], Path] | None = None):
        self.ext = ext
        self.transform = transform

    def __call__(self, context: Context, path: Path, match: T) -> Path:
        return _to_dir_inner(context['working_dir'], self.ext, context, path, match, self.transform)


class REMatcher(Matcher[re.Match | None]):
    """
    Path Matcher using regular expressions. @re_flags will be passed to
    `re.compile()`. @parent_dir, if specified, should be a key to a configured
    directory, not a Path, and will be used to handle matching the beginning of
    Paths; this can be used to avoid pitfalls with unexpected characters in
    input or working directories.
    """
    def __init__(self, re_string: str, re_flags: int = 0, parent_dir: ContextDir | None = None):
        self.regex = re.compile(re_string, re_flags)
        self.parent_dir: ContextDir | None = parent_dir

    def __call__(self, context: Context, path: Path):
        if self.parent_dir:
            # Handle this part of matching outside the regex.
            if not path.is_relative_to(context[self.parent_dir]):
                return None
            path = path.relative_to(context[self.parent_dir])
        return self.regex.match(path.as_posix())
