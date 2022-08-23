from __future__ import annotations

import importlib
import shutil
import typing as t


# TODO: I'm not a huge fan of this system. Might be better to have a
# DependencyType class that uses __init_subclass__ to register its children.
DEPENDENCY_TYPES: dict[str, tuple[str, t.Callable[[], bool]]] = {
    'pip': (
        'pip install {source}',
        lambda: True
    ),
    'web': (
        '{source}',
        lambda: True
    ),
    'npm': (
        'npm install -g {source}',
        lambda: True
    ),
}


def import_install_check(dependency: Dependency):
    try:
        importlib.import_module(dependency.name)
    except ImportError:
        return False
    return True


def which_install_check(dependency: Dependency):
    return bool(shutil.which(dependency.name))


class Dependency:
    def __init__(self,
                 name: str,
                 type: str,
                 install_check: t.Callable[[Dependency], bool],
                 source: str | None = None):
        self.name = name
        self.type = type
        self.install_check = install_check
        self.source = source or name

    @property
    def satisfied(self):
        return self.install_check(self)

    @property
    def needed(self):
        return DEPENDENCY_TYPES[self.type][1]()

    @property
    def install_hint(self):
        return DEPENDENCY_TYPES[self.type][0].format(name=self.name, source=self.source)

    def __repr__(self):
        return f'Dependency(name={self.name}, needed={self.needed}, satisfied={self.satisfied})'

    def __or__(self, other: Dependency):
        return _OrDependency(self, other)

    def __and__(self, other: Dependency):
        return _AndDependency(self, other)


class _OrDependency(Dependency):
    def __init__(self, left: Dependency, right: Dependency):
        self.left = left
        self.right = right

    def __repr__(self):
        return f'{self.left} | {self.right}'

    @property
    def satisfied(self):
        return self.left.satisfied or self.right.satisfied

    @property
    def needed(self):
        return self.left.needed or self.right.needed

    @property
    def install_hint(self):
        return (
            (self.left.needed and self.left.install_hint)
            or (self.right.needed and self.right.install_hint)
            or ''
        )


class _AndDependency(Dependency):
    def __init__(self, left: Dependency, right: Dependency):
        self.left = left
        self.right = right

    def __repr__(self):
        return f'{self.left} & {self.right}'

    @property
    def satisfied(self):
        return self.left.satisfied and self.right.satisfied

    @property
    def needed(self):
        # These should mostly match, but we'll allow for cases where one
        # dependency is paired on more specific platforms.
        return self.left.needed or self.right.needed

    def install_hint(self):
        return '; '.join(d.install_hint for d in [self.left, self.right] if d.needed)
