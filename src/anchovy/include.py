"""
Steps to add files from network resources and archives into an Anchovy build.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from anchovy.core import Context

from .core import Step
from .custody import CustodyEntry
from .dependencies import PipDependency


class RequestsFetchStep(Step):
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
        if not output_paths:
            return
        for o_path in output_paths:
            o_path.parent.mkdir(parents=True, exist_ok=True)

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
        with output_paths[0].open('wb') as file:
            for chunk in response.iter_content(self.chunk_size):
                file.write(chunk)
            for o_path in output_paths[1:]:
                shutil.copy(output_paths[0], o_path)

        centry = CustodyEntry('requests', url, {'etag': response.headers['ETag']})
        return [path, centry], output_paths


class URLLibFetchStep(Step):
    """
    A step using urllib to fetch a resource from a URL in a config file into
    the build.
    """
    @classmethod
    def get_dependencies(cls):
        return {PipDependency('tomli')} if sys.version_info < (3, 11) else {}

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
        if not output_paths:
            return
        for o_path in output_paths:
            o_path.mkdir(parents=True, exist_ok=True)

        import urllib.request
        if sys.version_info < (3, 11):
            import tomli as tomllib
        else:
            import tomllib

        with path.open('rb') as file:
            config = tomllib.load(file)
        url: str = config.pop('url')

        _path, msg = urllib.request.urlretrieve(url, output_paths[0], **config)

        for o_path in output_paths[1:]:
            shutil.copy(output_paths[0], o_path)

        centry = CustodyEntry('urllib', url, {'etag': msg['ETag']})
        return [path, centry], output_paths


class UnpackArchiveStep(Step):
    """
    A step for extracting files from an archive.
    """
    def __init__(self, archive_format: str | None = None):
        self.archive_format = archive_format
    def __call__(self, path: Path, output_paths: list[Path]):
        if not output_paths:
            return
        for o_path in output_paths:
            o_path.mkdir(parents=True, exist_ok=True)

        first = output_paths[0]
        shutil.unpack_archive(path, first, format=self.archive_format)
        all_outputs = list(self.context.find_inputs(first))
        for o_path in output_paths[1:]:
            shutil.copytree(first, o_path, dirs_exist_ok=True)
            all_outputs.extend(self.context.find_inputs(o_path))
        return [path], all_outputs
