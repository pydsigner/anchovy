import typing as t

try:
    import rich.progress as _rich_progress
except ImportError:
    _rich_progress = None

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
