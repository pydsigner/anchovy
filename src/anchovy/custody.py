from __future__ import annotations

import hashlib
from pathlib import Path


def checksum(path: Path, hashname: str = 'sha1', _bufsize=2**18):
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
    def __init__(self, type: str, key: str, meta: dict | None = None):
        self.type = type
        self.key = key
        self.meta = meta or {}

    def __str__(self):
        return f'{self.type}:{self.key}'

    def __getitem__(self, key):
        return self.meta[key]
