import re
import typing as t
from pathlib import Path

from .core import Context


def _trim_ext_prefix(path: Path, match: re.Match[str]):
    _groups = match.groupdict()
    if 'stem' in _groups:
        return path.with_stem(_groups['stem'])
    if 'ext' in _groups:
        return Path(match.string[:match.start('ext')])
    return path


def to_dir(dest: Path, ext: str | None = None):
    """
    Factory for PathCalculators that make their input paths children of @dest.
    If @ext is specified, it will replace the extension of input paths. If the
    matcher produced an re.Match, it will be checked for explicitly defined
    extension information for the input paths, allowing for extensions like
    `.tar.gz`.
    """
    def inner(context: Context, path: Path, match: t.Any):
        path = _trim_ext_prefix(path, match) if ext and isinstance(match, re.Match) else path

        rel = path.relative_to(
            context['input_dir']
            if path.is_relative_to(context['input_dir'])
            else context['working_dir']
        )
        new_path = dest / rel

        if ext:
            new_path = new_path.with_suffix(ext)

        return new_path
    return inner


def to_output(ext: str | None = None):
    """
    Factory for PathCalculators that make their input paths children of their
    Context's output dir. If @ext is specified, it will replace the extension
    of input paths. If the matcher produced an re.Match, it will be checked for
    explicitly defined extension information for the input paths, allowing for
    extensions like `.tar.gz`.
    """
    def inner(context: Context, path: Path, match: t.Any):
        path = _trim_ext_prefix(path, match) if ext and isinstance(match, re.Match) else path

        rel = path.relative_to(
            context['input_dir']
            if path.is_relative_to(context['input_dir'])
            else context['working_dir']
        )
        new_path = context['output_dir'] / rel

        if ext:
            new_path = new_path.with_suffix(ext)

        return new_path
    return inner


def to_working(ext: str | None = None):
    """
    Factory for PathCalculators that make their input paths children of their
    Context's working dir. If @ext is specified, it will replace the extension
    of input paths. If the matcher produced an re.Match, it will be checked for
    explicitly defined extension information for the input paths, allowing for
    extensions like `.tar.gz`.
    """
    def inner(context: Context, path: Path, match: t.Any):
        path = _trim_ext_prefix(path, match) if ext and isinstance(match, re.Match) else path

        rel = path.relative_to(
            context['input_dir']
            if path.is_relative_to(context['input_dir'])
            else context['working_dir']
        )
        new_path = context['working_dir'] / rel

        if ext:
            new_path = new_path.with_suffix(ext)

        return new_path
    return inner


def match_re(re_string: str):
    """
    Simple path matcher using regular expressions.
    """
    regex = re.compile(re_string)
    def match_func(path: Path):
        return regex.match(path.as_posix())
    return match_func
