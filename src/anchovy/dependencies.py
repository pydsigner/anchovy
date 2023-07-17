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
    """
    An install checker which tries to import a Python module.
    """
    try:
        importlib.import_module(dependency.check_name)
    except ImportError:
        return False
    return True


def which_install_check(dependency: Dependency):
    """
    An install checker using `shutil.which()` to look for an executable.
    """
    return bool(shutil.which(dependency.check_name))


def pip_dependency(name: str, source: str | None = None, check_name: str | None = None):
    """
    A shortcut function for creating typical pip-based Dependencys.
    """
    return Dependency(name, 'pip', import_install_check, source, check_name)


def web_exec_dependency(name: str, source: str | None = None, check_name: str | None = None):
    """
    A shortcut function for creating typical Dependencys for general
    internet-sourced executables.
    """
    return Dependency(name, 'web', which_install_check, source, check_name)


class Dependency:
    """
    A class for tracking and evaluating dependencies.
    """
    def __init__(self,
                 name: str,
                 type: str,
                 install_check: t.Callable[[Dependency], bool],
                 source: str | None = None,
                 check_name: str | None = None):
        self.name = name
        self.type = type
        self.install_check = install_check
        self.source = source or name
        self.check_name = check_name or name

    @property
    def satisfied(self):
        """
        A bool indicating if this dependency is met.
        """
        return self.install_check(self)

    @property
    def needed(self):
        """
        A bool indicating if this dependency is needed on the current platform.
        """
        return DEPENDENCY_TYPES[self.type][1]()

    @property
    def install_hint(self):
        """
        A string giving help on how to install this dependency.
        """
        return DEPENDENCY_TYPES[self.type][0].format(name=self.name, source=self.source)

    def __repr__(self):
        return f'Dependency(name={self.name}, needed={self.needed}, satisfied={self.satisfied})'

    def __str__(self):
        return self.name

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

    def __str__(self):
        return repr(self)

    @property
    def satisfied(self):
        """
        A bool indicating whether either of these dependencies are met.
        """
        return self.left.satisfied or self.right.satisfied

    @property
    def needed(self):
        """
        A bool indicating whether either of these dependencies is needed.
        """
        return self.left.needed or self.right.needed

    @property
    def install_hint(self):
        """
        A string giving help on how to meet one of these dependencies, if
        either is needed.
        """
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

    def __str__(self):
        return repr(self)

    @property
    def satisfied(self):
        """
        A bool indicating whether both of these dependencies are met.
        """
        return self.left.satisfied and self.right.satisfied

    @property
    def needed(self):
        """
        A bool indicating whether either of these dependencies is needed.
        """
        # These should mostly match, but we'll allow for cases where one
        # dependency is paired on more specific platforms.
        return self.left.needed or self.right.needed

    @property
    def install_hint(self):
        """
        A string giving help on how to install these dependencies, if they are
        needed.
        """
        return '; '.join(d.install_hint for d in [self.left, self.right] if d.needed)
