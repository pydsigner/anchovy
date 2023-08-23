from __future__ import annotations

import abc
import importlib
import shutil


class Dependency(abc.ABC):
    """
    A base class for trackable, evaluable, composable dependencies.
    """

    @property
    @abc.abstractmethod
    def satisfied(self) -> bool:
        """
        A bool indicating whether this dependency is met.
        """

    @property
    def needed(self) -> bool:
        """
        A bool indicating whether this dependency is needed on the current platform.
        """
        return True

    @property
    @abc.abstractmethod
    def install_hint(self) -> str:
        """
        A string giving help on how to install this dependency.
        """

    def __repr__(self):
        return f'{self.__class__.__name__}({self}, needed={self.needed}, satisfied={self.satisfied})'

    def __or__(self, other: Dependency):
        return _OrDependency(self, other)

    def __and__(self, other: Dependency):
        return _AndDependency(self, other)


class _OrDependency(Dependency):
    def __init__(self, left: Dependency, right: Dependency):
        self.left = left
        self.right = right

    def __repr__(self):
        return f'({self.left!r} | {self.right!r})'

    def __str__(self):
        return f'({self.left} | {self.right})'

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
        return f'({self.left!r} & {self.right!r})'

    def __str__(self):
        return f'({self.left} & {self.right})'

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


class PipDependency(Dependency):
    """
    A Dependency on a pip-installable package.
    """
    def __init__(self,
                 name: str,
                 source: str | None = None,
                 check_name: str | None = None):
        self.name = name
        self.source = source or name
        self.check_name = check_name or name

    def __str__(self):
        return self.name

    @property
    def satisfied(self):
        """
        A bool indicating whether this dependency is met.
        """
        try:
            importlib.import_module(self.check_name)
        except ImportError:
            return False
        return True

    @property
    def install_hint(self):
        """
        A string giving help on how to install this dependency.
        """
        return f'pip install {self.source}'


class WebExecDependency(Dependency):
    """
    A Dependency on a general internet-sourced executable.
    """
    def __init__(self,
                 name: str,
                 source: str | None = None,
                 check_name: str | None = None):
        self.name = name
        self.source = source or name
        self.check_name = check_name or name

    def __str__(self):
        return self.name

    @property
    def satisfied(self):
        """
        A bool indicating whether this dependency is met.
        """
        return bool(shutil.which(self.check_name))

    @property
    def install_hint(self):
        """
        A string giving help on how to install this dependency.
        """
        return self.source
