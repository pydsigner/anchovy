"""
Steps to add files from network resources and archives into an Anchovy build.
"""
from __future__ import annotations

import shutil
import sys
import typing as t
from pathlib import Path

from anchovy.core import Context

from .core import Context
from .custody import CustodyEntry
from .dependencies import Dependency, PipDependency
from .simple import BaseStandardStep

if t.TYPE_CHECKING:
    from _typeshed.dbapi import DBAPIConnection


class RequestsFetchStep(BaseStandardStep):
    """
    A step using requests to fetch a resource from a URL in a config file into
    the build.
    """
    chunk_size = 8192
    timeout = 300

    @classmethod
    def get_dependencies(cls):
        deps = {
            PipDependency('requests'),
        }
        if sys.version_info < (3, 11):
            deps.add(PipDependency('tomli'))
        return deps

    def bind(self, context: Context):
        super().bind(context)
        @context.custodian.register_checker('requests', override=False)
        def requests_resource_stale(entry: CustodyEntry):
            import requests
            response = requests.head(
                entry.key,
                allow_redirects=True,
                headers={'If-None-Match': entry['etag']},
                timeout=self.timeout
            )
            return response.status_code == 304

    def __call__(self, path: Path, output_paths: list[Path]):
        import requests
        if sys.version_info < (3, 11):
            import tomli as tomllib
        else:
            import tomllib

        with path.open('rb') as file:
            config = tomllib.load(file)
        url: str = config.pop('url')
        config.setdefault('stream', True)
        config.setdefault('timeout', self.timeout)

        response = requests.get(url, **config)
        if not response:
            response.raise_for_status()
        with self.ensure_outputs(output_paths), output_paths[0].open('wb') as file:
            for chunk in response.iter_content(self.chunk_size):
                file.write(chunk)

        centry = CustodyEntry('requests', url, {'etag': response.headers['ETag']})
        return [path, centry], output_paths


class URLLibFetchStep(BaseStandardStep):
    """
    A step using urllib to fetch a resource from a URL in a config file into
    the build.
    """
    @classmethod
    def get_dependencies(cls):
        return {PipDependency('tomli')} if sys.version_info < (3, 11) else set[Dependency]()

    def bind(self, context: Context):
        super().bind(context)
        @context.custodian.register_checker('urllib', override=False)
        def urllib_resource_stale(entry: CustodyEntry):
            import urllib.request
            request = urllib.request.Request(
                entry.key,
                headers={'If-None-Match': entry['etag']},
                method='HEAD'
            )
            try:
                with urllib.request.urlopen(request):
                    return False
            except urllib.request.HTTPError as e:
                if e.code == 304:
                    return True
                raise

    def __call__(self, path: Path, output_paths: list[Path]):
        import urllib.request
        if sys.version_info < (3, 11):
            import tomli as tomllib
        else:
            import tomllib

        with path.open('rb') as file:
            config = tomllib.load(file)
        url: str = config.pop('url')

        with self.ensure_outputs(output_paths):
            _path, msg = urllib.request.urlretrieve(url, output_paths[0], **config)

        centry = CustodyEntry('urllib', url, {'etag': msg['ETag']})
        return [path, centry], output_paths


class UnpackArchiveStep(BaseStandardStep):
    """
    A step for extracting files from an archive.
    """
    def __init__(self, archive_format: str | None = None):
        self.archive_format = archive_format
    def __call__(self, path: Path, output_paths: list[Path]):
        self.ensure_output_dirs(output_paths)
        first = output_paths[0]
        shutil.unpack_archive(path, first, format=self.archive_format)
        all_outputs = [first]
        all_outputs.extend(self.context.find_inputs(first))
        for o_path in output_paths[1:]:
            shutil.copytree(first, o_path, dirs_exist_ok=True)
            all_outputs.append(o_path)
            all_outputs.extend(self.context.find_inputs(o_path))
        return [path], all_outputs


class SQLExtractStep(BaseStandardStep):
    """
    A step for extracting files from a SQL database. The query should return
    two columns: first, the name of the output file and second, the content of
    the file. The output PathCalc used with this step should resolve to a
    directory where output files will be placed.
    """
    def __init__(self,
                 connection_factory: t.Callable[[], DBAPIConnection],
                 ext: str = '',
                 binary: bool = False):
        """
        :param connection_factory: A callable that returns a new DB-API 2.0
            database connection.
        :param ext: An optional extension to add to the name of the output
            files.
        :param binary: Whether the output data should be treated as text or as
            binary.
        """
        self.connection_factory = connection_factory
        self.ext = ext
        self.binary = binary

    def __call__(self, path: Path, output_paths: list[Path]):
        self.ensure_output_dirs(output_paths)
        conn = self.connection_factory()
        curr = conn.cursor()
        with path.open(encoding=self.encoding) as f:
            curr.execute(f.read())

        outputs = []
        for name, data in curr.fetchall():
            for o_base in output_paths:
                out_path = o_base / (name + self.ext)
                with (out_path.open('wb') if self.binary else out_path.open('w', encoding=self.encoding)) as f:
                    f.write(data)
                outputs.append(out_path)

        conn.close()
        return [path], outputs
