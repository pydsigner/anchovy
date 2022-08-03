import re
from pathlib import Path

from .context import Context


def trim_ext_prefix(path: Path, match: re.Match[str]):
    _groups = match.groupdict()
    if 'stem' in _groups:
        return path.with_stem(_groups['stem'])
    if 'ext' in _groups:
        return Path(match.string[:match.start('ext')])
    return path


def to_dir(dest: Path, context: Context, path: Path, match: re.Match[str], ext: str | None = None):
    path = trim_ext_prefix(path, match) if ext else path

    rel = path.relative_to(
        context['input_dir']
        if path.is_relative_to(context['input_dir'])
        else context['working_dir']
    )
    new_path = dest / rel

    if ext:
        new_path = new_path.with_suffix(ext)

    return new_path


def to_output(context: Context, path: Path, match: re.Match[str], ext: str | None = None):
    return to_dir(context['output_dir'], context, path, match, ext)


def to_working(context: Context, path: Path, match: re.Match[str], ext: str | None = None):
    return to_dir(context['working_dir'], context, path, match, ext)
