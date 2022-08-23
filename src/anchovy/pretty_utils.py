import sys
import typing as t

try:
    import rich.progress as _rich_progress
except ImportError:
    _rich_progress = None
try:
    import rich.console
    _rich_consoles = {
        sys.stdout: rich.console.Console(file=sys.stdout),
        sys.stderr: rich.console.Console(file=sys.stderr),
    }
except ImportError:
    _rich_consoles = {}
try:
    import tqdm as _tqdm
except ImportError:
    _tqdm = None


T = t.TypeVar('T')


def track_progress(iterable: t.Iterable[T], desc: str) -> t.Iterable[T]:
    """
    Progress tracker which supports rich and tqdm progress bars and gracefully
    devolves to no progress tracking.
    """
    if _rich_progress:
        yield from _rich_progress.track(iterable, desc)
    elif _tqdm:
        yield from _tqdm.tqdm(iterable, desc)
    else:
        print(desc)
        yield from iterable


def print_with_style(*args, sep=' ', end='\n', file=sys.stdout, style=None):
    """
    Enhanced print() function which supports rich console styles and gracefully
    devolves to standard print().
    """
    if file in _rich_consoles:
        _rich_consoles[file].print(*args, sep=sep, end=end, style=style)
    else:
        print(*args, sep=sep, end=end, file=file)
