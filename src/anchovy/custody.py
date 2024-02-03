"""
Explicit chain of custody management and intelligent rebuilds for Anchovy.
"""
from __future__ import annotations

import hashlib
import json
import typing as t
from importlib.metadata import version
from pathlib import Path

from .pretty_utils import print_with_style

if t.TYPE_CHECKING:
    from collections.abc import Sequence
    from .core import Context, ContextDir


_JsonSerializable: t.TypeAlias = 'str | int | float | bool | None | _JsonDict | Sequence[_JsonSerializable]'
_JsonDict = dict[str, _JsonSerializable]

CONTEXT_DIR_KEYS: set[ContextDir] = {'input_dir', 'output_dir', 'working_dir'}


def checksum(path: Path, hashname: str = 'sha1', _bufsize=2**18):
    """
    Calculate a checksum for a `Path`. Directories result in empty checksums.
    """
    if path.is_dir():
        return ''
    digest = hashlib.new(hashname)

    buf = bytearray(_bufsize)
    view = memoryview(buf)
    with path.open('rb') as file:
        while True:
            size = file.readinto(buf)
            if size == 0:
                break  # EOF
            digest.update(view[:size])

    return digest.hexdigest()


class CustodyEntry:
    """
    Class holding custody info for a single input or output path.
    """
    def __init__(self, entry_type: str, key: str, meta: dict | None = None):
        self.entry_type = entry_type
        self.key = key
        self.meta = meta or {}

    def __str__(self):
        return f'{self.entry_type}:{self.key}'

    def __getitem__(self, key):
        return self.meta[key]


class Custodian:
    """
    Class for managing custody info and intelligent rebuilds.
    """
    encoding = 'utf-8'
    newline = '\n'
    context: 'Context'

    def __init__(self,
                 parameters: _JsonDict | None = None,
                 info: dict[str, str] | None = None):
        self.checkers: dict[str, t.Callable[[CustodyEntry], bool]] = {'path': self.check_path}

        self.parameters: _JsonDict = {'anchovy_version': version('anchovy')}
        if parameters:
            self.parameters.update(parameters)
        self.prior_parameters: _JsonDict = {}
        self.stale_parameters = True

        self.info = info or {}

        # output_key: {input_key: [sibling_keys]}
        self.graph: dict[str, dict[str, list[str]]] = {}
        self.prior_graph: dict[str, dict[str, list[str]]] = {}

        # key: (type, meta) (i.e. the parts of a CustodyEntry)
        self.meta: dict[str, tuple[str, _JsonDict]] = {}
        self.prior_meta: dict[str, tuple[str, _JsonDict]] = {}

    def bind(self, context: 'Context'):
        """
        Bind this `Custodian` to a `Context` and update info using the
        `Context`'s settings.
        """
        self.context = context
        for key in context.settings:
            if key not in self.info:
                self.info[key] = str(context.settings[key])

    # Default behaviors for Paths

    def genericize_path(self, path: Path):
        """
        Genericize a path, removing run-specific folder references and
        converting to a key.
        """
        for dir_key in CONTEXT_DIR_KEYS:
            parent = self.context[dir_key]
            if path.is_relative_to(parent):
                path = dir_key / path.relative_to(parent)
                break
        return path.as_posix()

    def degenericize_path(self, key: str):
        """
        Undo `genericize_path()` to turn a key back into a Path.
        """
        # https://github.com/pydsigner/anchovy/issues/66
        if key in CONTEXT_DIR_KEYS:
            return self.context[key]

        path = Path(key)
        # -2 because path.parents walks upward (parents[0] is the same as
        # path.parent) and -1 is the root (in our case, '.')
        dir_key = t.cast('ContextDir', str(path.parents[-2]))
        return self.context[dir_key] / path.relative_to(dir_key)

    def get_all_paths(self):
        """
        Generator of every output key in the graph as a Path.
        """
        return (self.degenericize_path(key) for key in self.graph)

    def entry_from_path(self, path: Path):
        """
        Create a `CustodyEntry` for a path. Provides a sha1 checksum along with
        stat modified time and size for path checkers.
        """
        # The default checker only looks at a checksum, but it's not much added
        # cost to also stat, and doing so means that an end user can switch to
        # m_time testing by registering a new checker and does not need to
        # subclass CustodyManager for this common case.
        stat = path.stat()
        meta = {'sha1': checksum(path), 'm_time': stat.st_mtime, 'size': stat.st_size}
        return CustodyEntry('path', self.genericize_path(path), meta)

    def check_path(self, entry: CustodyEntry) -> bool:
        """
        Default sha1-based checker for path staleness.
        """
        path = self.degenericize_path(entry.key)
        return path.exists() and entry['sha1'] == checksum(path)

    def ensure_entry(self, record: Path | CustodyEntry):
        """
        Create a `CustodyEntry` if the parameter is a Path, otherwise just
        return the existing `CustodyEntry`.
        """
        if isinstance(record, CustodyEntry):
            return record
        return self.entry_from_path(record)

    def register_checker(self, entry_type: str, override: bool = True):
        """
        Decorator for registering a staleness checker for a specific type of
        `CustodyEntry`.
        """
        def register(func: t.Callable[[CustodyEntry], bool]):
            if override or entry_type not in self.checkers:
                self.checkers[entry_type] = func
        return register

    def load_file(self, path: Path):
        """
        Load prior custody data and metadata from a JSON file and evaluate
        parameter staleness.
        """
        if not path.exists():
            return
        data = json.loads(path.read_text(self.encoding))
        self.prior_parameters = data['parameters']
        self.stale_parameters = self.parameters != self.prior_parameters
        self.prior_graph = data['graph']
        self.prior_meta = data['meta']

    def dump_file(self, path: Path):
        """
        Dump all custody data and metadata from the current run into a JSON
        file.
        """
        data = {
            'info': self.info,
            'parameters': self.parameters,
            'graph': self.graph,
            'meta': self.meta,
        }
        with path.open('w', encoding=self.encoding, newline=self.newline) as file:
            json.dump(data, file, indent=2)

    def update_meta(self, entry: CustodyEntry):
        """
        Store a `CustodyEntry` in serializable form.
        """
        self.meta[entry.key] = (entry.entry_type, entry.meta)

    def add_step(self,
                 sources: Sequence[Path | CustodyEntry],
                 outputs: Sequence[Path],
                 stale_msg: str):
        """
        Mark a Step as run, updating custody data and logging accordingly.
        """
        self.log_step(sources, outputs, stale=True, stale_msg=stale_msg)

        keys = []
        for o_entry in map(self.ensure_entry, outputs):
            keys.append(o_entry.key)
            self.update_meta(o_entry)

        for i_entry in map(self.ensure_entry, sources):
            self.update_meta(i_entry)
            for o_key in keys:
                self.graph.setdefault(o_key, {})[i_entry.key] = keys

    def skip_step(self, source: Path, outputs: list[Path]):
        """
        Mark a Step as skipped, updating custody data and logging accordingly.
        """
        prior_outputs = [self.degenericize_path(p) for p in self.find_downstream(source, outputs)]

        self.log_step([source], prior_outputs, stale=False)

        self.update_meta(self.entry_from_path(source))
        for o_entry in map(self.entry_from_path, prior_outputs):
            self.update_meta(o_entry)
            self.graph.setdefault(o_entry.key, {}).update(self.prior_graph[o_entry.key])
            for s_key in self.prior_graph[o_entry.key]:
                self.meta.setdefault(s_key, self.prior_meta[s_key])
        return prior_outputs

    def log_step(self,
                 sources: Sequence[Path | CustodyEntry],
                 outputs: Sequence[Path],
                 *,
                 stale: bool = True,
                 stale_msg: str = ''):
        """
        Log custody information for a step according to its staleness.
        """
        if len(sources) == 1:
            msg = f'{sources[0]} ⇒ {", ".join(str(p) for p in outputs)}'
        else:
            msg = ''.join([
                '{\n\t',
                ',\n\t'.join(str(s) for s in sources),
                '\n} ⇒ {\n\t',
                ',\n\t'.join(str(p) for p in outputs),
                '\n}',
            ])
        if stale:
            print_with_style(f'{stale_msg}...\n{msg}')
        else:
            print_with_style('Skipped', msg, style='yellow')

    def check_prior(self, key: str):
        """
        Check whether the current resource corresponding to the given key
        matches its historical fingerprint.

        :param key: A `CustodyEntry.key`.
        """
        try:
            ptype, pmeta = self.prior_meta[key]
        except KeyError:
            return False

        try:
            checker = self.checkers[ptype]
        except KeyError as e:
            raise KeyError(f'No checker found for type {ptype!r}!') from e

        return checker(CustodyEntry(ptype, key, pmeta))

    def find_upstream(self, paths: list[Path]):
        """
        Find all input paths one step upstream of any of the specified paths.

        Relies only on historical data; combine with the
        `Custodian.stale_parameters` attribute and the `Custodian.check_prior()`
        method to ensure the historical data is still accurate.
        """
        return {
            s
            for p in paths
            for s in self.prior_graph.get(self.genericize_path(p), ())
        }

    def find_downstream(self, source: Path, outputs: list[Path]):
        """
        Find all output paths one step downstream of the specified source path
        and output path combination.

        Relies only on historical data; combine with the
        `Custodian.stale_parameters` attribute and the `Custodian.check_prior()`
        method to ensure the historical data is still accurate.
        """
        g_source = self.genericize_path(source)
        g_output = self.genericize_path(outputs[0])
        return iter(self.prior_graph[g_output][g_source])

    def refresh_needed(self, source: Path, outputs: list[Path]):
        """
        Determines whether a refresh is needed for the result of processing a
        pair of Step parameters.

        :return: Whether the step should be rerun and a message explaining why
            or why not.
        """
        if self.stale_parameters:
            return True, 'Stale parameters'

        for path in outputs:
            if not path.exists():
                return True, f'Missing output ({path})'

        upstreams = self.find_upstream(outputs)
        if self.genericize_path(source) not in upstreams:
            return True, f'Missing upstream record ({source})'

        for up_key in upstreams:
            if not self.check_prior(up_key):
                return True, f'Stale upstream ({up_key})'

        for down_key in self.find_downstream(source, outputs):
            if not self.check_prior(down_key):
                return True, f'Stale downstream ({down_key})'

        return False, 'Up to date'
