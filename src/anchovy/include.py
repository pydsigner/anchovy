from __future__ import annotations

import shutil
import sys
from pathlib import Path

from .core import Step
from .custody import CustodyEntry
from .dependencies import PipDependency


class RequestsFetchStep(Step):
    """
    A step using requests to fetch a resource from a URL in a config file into
    the build.
    """
    chunk_size = 8192
    @classmethod
    def get_dependencies(cls):
        deps = {
            PipDependency('requests'),
        }
        if sys.version_info < (3, 11):
            deps.add(PipDependency('tomli'))
        return deps

    def __call__(self, path: Path, output_paths: list[Path]):
        if not output_paths:
            return

        import requests
        if sys.version_info < (3, 11):
            import tomli as tomllib
        else:
            import tomllib

        with path.open('rb') as f:
            config = tomllib.load(f)
        url: str = config.pop('url')
        config.setdefault('stream', True)

        response = requests.get(url, **config)
        if response.status_code >= 400:
            # FIXME: Rather ugly and incomplete...
            import urllib.error
            import http.client
            raise urllib.error.HTTPError(
                url,
                response.status_code,
                response.text,
                http.client.HTTPMessage(),
                None
            )
        with output_paths[0].open('wb') as f:
            for chunk in response.iter_content(self.chunk_size):
                f.write(chunk)
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

    def __call__(self, path: Path, output_paths: list[Path]):
        if not output_paths:
            return
        for p in output_paths:
            p.parent.mkdir(parents=True, exist_ok=True)

        import urllib.request
        if sys.version_info < (3, 11):
            import tomli as tomllib
        else:
            import tomllib

        with path.open('rb') as f:
            config = tomllib.load(f)
        url: str = config.pop('url')

        _path, msg = urllib.request.urlretrieve(url, output_paths[0], **config)

        for o_path in output_paths[1:]:
            shutil.copy(output_paths[0], o_path)

        centry = CustodyEntry('urllib', url, {'etag': msg['ETag']})
        return [path, centry], output_paths


class UnpackArchiveStep(Step):
    def __init__(self, format: str | None = None):
        self.format = format
    def __call__(self, path: Path, output_paths: list[Path]):
        if not output_paths:
            return
        for p in output_paths:
            p.mkdir(parents=True, exist_ok=True)

        first = output_paths[0]
        shutil.unpack_archive(path, first, format=self.format)
        all_outputs = list(self.context.find_inputs(first))
        for p in output_paths[1:]:
            shutil.copytree(first, p, dirs_exist_ok=True)
            all_outputs.extend(self.context.find_inputs(p))

        return [path], all_outputs
