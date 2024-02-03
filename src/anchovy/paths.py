"""
Practical implementations of Matchers and PathCalcs.
"""
import re
import typing as t
from pathlib import Path

from .core import Context, ContextDir, Matcher, PathCalc
from .custody import CONTEXT_DIR_KEYS


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

    if ext is not None:
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
    def __init__(self,
                 dest: Path | ContextDir,
                 ext: str | None = None,
                 transform: t.Callable[[Path], Path] | None = None):
        self.dest = dest
        self.ext = ext
        self.transform = transform

    def __call__(self, context: Context, path: Path, match: T) -> Path:
        if self.dest in CONTEXT_DIR_KEYS:
            dest = context[self.dest]
        else:
            dest = Path(self.dest)
        return _to_dir_inner(dest, self.ext, context, path, match, self.transform)


class OutputDirPathCalc(DirPathCalc[T]):
    """
    PathCalc which makes its input paths children of the Context's output
    directory. If @ext is specified, it will replace the extension of input
    paths. If the matcher produced an re.Match, it will be checked for
    explicitly defined extension information for the input paths, allowing for
    meaningful work with extensions that `pathlib.Path` does not reflect, like
    `.tar.gz`.
    """
    def __init__(self,
                 ext: str | None = None,
                 transform: t.Callable[[Path], Path] | None = None):
        super().__init__('output_dir', ext, transform)


class WorkingDirPathCalc(DirPathCalc[T]):
    """
    PathCalc which makes its input paths children of the Context's working
    directory. If @ext is specified, it will replace the extension of input
    paths. If the matcher produced an re.Match, it will be checked for
    explicitly defined extension information for the input paths, allowing for
    meaningful work with extensions that `pathlib.Path` does not reflect, like
    `.tar.gz`.
    """
    def __init__(self,
                 ext: str | None = None,
                 transform: t.Callable[[Path], Path] | None = None):
        super().__init__('working_dir', ext, transform)


class WebIndexPathCalc(DirPathCalc[T]):
    """
    DirPathCalc which additionally nests its input paths into an index
    structure so that file extensions can be omitted in URLs.
    """
    index_base = 'index'

    def __init__(self,
                 dest: Path | ContextDir,
                 ext: str | None = None,
                 transform: t.Callable[[Path], Path] | None = None,
                 index_base: str | None = None):
        if transform:
            def full_transform(path: Path):
                return self._web_transform(transform(path))
        else:
            full_transform = self._web_transform
        super().__init__(dest, ext, full_transform)
        self.index_base = index_base or self.index_base

    def _web_transform(self, path: Path) -> Path:
        """
        Transform a/b.c to a/b/index.c, while leaving a/index.c as-is.
        """
        if path.stem == self.index_base:
            return path
        return (path.with_suffix('') / self.index_base).with_suffix(path.suffix)


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
