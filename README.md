[![PyPI - Project Version](https://img.shields.io/pypi/v/anchovy)](https://pypi.org/project/anchovy)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/anchovy)](https://pypi.org/project/anchovy)
[![GitHub - Project License](https://img.shields.io/github/license/pydsigner/anchovy)](https://github.com/pydsigner/anchovy)
[![GitHub - Code Size](https://img.shields.io/github/languages/code-size/pydsigner/anchovy)](https://github.com/pydsigner/anchovy)
[![codecov](https://codecov.io/gh/pydsigner/anchovy/graph/badge.svg?token=A8WRBWO3JG)](https://codecov.io/gh/pydsigner/anchovy)

# Anchovy

Anchovy is a minimal, unopinionated file-processing framework equipped with a
complete static website generation toolkit.

* **Minimal:** Anchovy's core is around a thousand lines of code and has no
  mandatory dependencies. Plus, Anchovy can be used for real projects with just
  a few pip-installable extras, even if you want to preprocess CSS.

* **Unopinionated:** Anchovy offers a set of components which can be easily
  configured to your site's exact requirements, without tediously ripping out
  or overriding entrenched behaviors. Anchovy does not assume you are building
  a blog or that you wish to design your templates in a specific way. You can
  even build things that aren't websites! Plus, Anchovy operates on files, so
  it's simple to integrate tools like imagemagick, dart-sass, or less.js if you
  need them.

* **Complete:** Anchovy comes with a dependency auditing system, allowing you
  to grab any component you want without installing anything but Anchovy and
  find out what you *will* need to run your build. Choose from a wealth of
  Steps, Anchovy's modular file processors, for everything from rendering Jinja
  templates and minifying CSS to unpacking archives and thumbnailing images.
  Plus, add a few extra parameters or lines of configuration to get automatic
  intelligent minimum builds based on input checksums, and get a reproducible
  run artifact to boot— even if you want to fetch HTTP resources or write your
  own Steps.

## Installation

Anchovy has no essential prerequisites and can be installed with
`pip install anchovy` to get just the framework and a few built-in components,
but for typical usage `pip install anchovy[base]` is recommended. This will
pull in support for Jinja2 templating, markdown, minification, and Anchovy's
CSS preprocessor. A full list of available extras may be found in the
[pyproject.toml](./pyproject.toml) file.

Alternatively, Anchovy may be installed directly from source with
`pip install git+https://github.com/pydsigner/anchovy` or the corresponding
`pip install git+https://github.com/pydsigner/anchovy#egg=anchovy[base]`.

## Command Line Usage

Anchovy operates on config files written in Python, or even modules directly.

* `python -m anchovy -h`
* `anchovy -m mypackage.anchovyconf -o ../release/`
* `python -m anchovy mysite/anchovy_site.py -- -h`

```python
from pathlib import Path

from anchovy import (
    DirectCopyStep,
    InputBuildSettings,
    JinjaMarkdownStep,
    OutputDirPathCalc,
    REMatcher,
    Rule,
)


# Optional, and can be overridden with CLI arguments.
SETTINGS = InputBuildSettings(
    input_dir=Path('site'),
    working_dir=Path('working'),
    output_dir=Path('build'),
    custody_cache=Path('build-cache.json'),
)
RULES = [
    # Ignore dotfiles found in either the input_dir or the working dir.
    Rule(
        (
            REMatcher(r'(.*/)*\..*', parent_dir='input_dir')
            | REMatcher(r'(.*/)*\..*', parent_dir='working_dir')
        ),
        None
    ),
    # Render markdown files, then stop processing them.
    Rule(
        REMatcher(r'.*\.md'),
        [OutputDirPathCalc('.html'), None],
        JinjaMarkdownStep()
    ),
    # Copy everything else in static/ directories through.
    Rule(
        REMatcher(r'(.*/)*static/.*', parent_dir='input_dir'),
        OutputDirPathCalc(),
        DirectCopyStep()
    ),
]
```

This example is very simple, but is legitimately enough for a small website.
If we stored the configuration in `config.py` and added a raw site like this:
```
site/
    static/
        styles.css
        toolbar.js
    base.jinja.html
    index.md
    about.md
    contact.md
```
 `python -m anchovy config.py` would produce output like this:
```
output/
    static/
        styles.css
        toolbar.js
    index.html
    about.html
    contact.html
```

This example can be found in runnable form as [examples/basic_site.py](./examples/basic_site.py)
in the source distribution. Available command line arguments can be seen by
passing `-h`: `python -m anchovy examples/basic_site.py -- -h`. The `--` is
required because `anchovy` itself also accepts the flag.

## Programmatic Usage

Anchovy is very usable from the command line, but projects desiring to
customize behavior, for example by running tasks before or after pipeline
execution, may utilize `anchovy.cli.run_from_rules()`:

```python
import time
from pathlib import Path

from anchovy.cli import run_from_rules
from anchovy.core import Context

from my_site.config import SETTINGS, RULES


class MyContext(Context):
    def find_inputs(path: Path):
        # Only process files modified in the last hour.
        hour_ago = time.time() - 3600
        for candidate in super().find_inputs(path):
            if candidate.stat().st_mtime > hour_ago:
                yield candidate


def main():
    print('Pretending to run pre-pipeline tasks...')
    run_from_rules(SETTINGS, RULES, context_cls=MyContext)
    print('Pretending to run post-pipeline tasks...')


if __name__ == '__main__':
    main()
```
