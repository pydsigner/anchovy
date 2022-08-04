[![PyPI - Project Version](https://img.shields.io/pypi/v/anchovy)](https://pypi.org/project/anchovy)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/anchovy)](https://pypi.org/project/anchovy)
[![GitHub - Project License](https://img.shields.io/github/license/pydsigner/anchovy)](https://github.com/pydsigner/anchovy)
[![GitHub - Code Size](https://img.shields.io/github/languages/code-size/pydsigner/anchovy)](https://github.com/pydsigner/anchovy)
[![Lines of code](https://img.shields.io/tokei/lines/github/pydsigner/anchovy)](https://github.com/pydsigner/anchovy)

# Anchovy

Anchovy is a minimal, unopinionated file processing engine intended for static
website generation.

* **Minimal:** Anchovy's core code is just a few hundred lines of code and has
  no mandatory dependencies. Plus, Anchovy can be used for real projects without
  bringing in dependencies on external executables or languages, even if you
  want to preprocess CSS.

* **Unopinionated:** Anchovy offers a set of components which can be easily
  configured to your site's exact requirements, without tediously ripping out
  or overriding entrenched behaviors. Anchovy does not assume you are building
  a blog or that you wish to design your templates in a specific way. You can
  even build things that aren't websites! Plus, Anchovy operates on files, so
  it's simple to integrate tools like imagemagick, dart-sass, or less.js if you
  need them.

## Installation

Anchovy has no essential prerequisites and can be installed with
`pip install anchovy` to get just the framework and a few built-in components,
but for typical usage `pip install anchovy[base]` is recommended. This will
pull in support for Jinja2 templating, markdown, and Anchovy's CSS preprocessor.
A full list of available extras may be found in the
[pyproject.toml](https://github.com/pydsigner/anchovy/blob/master/pyproject.toml)
file.

Alternatively, Anchovy may be installed directly from source with
`pip install git+https://github.com/pydsigner/anchovy` or the corresponding
`pip install git+https://github.com/pydsigner/anchovy#egg=anchovy[base]`.

## Usage

Anchovy operates on config files written in Python, or even modules directly.

```python
from pathlib import Path

from anchovy.core import InputBuildSettings, Rule
from anchovy.jinja import JinjaMarkdownStep
from anchovy.simple import direct_copy_step


# Optional, and can be overridden with CLI arguments.
SETTINGS = InputBuildSettings(
    input_dir=Path('site'),
    output_dir=Path('build'),
)
RULES: list[Rule] = [
    # Ignore dotfiles.
    (r'(.*/)*\..*', None),
    # Render markdown files, then stop processing them.
    (r'.*\.md', JinjaMarkdownStep()),
    (r'.*\.md', None),
    # Copy everything else in static/ directories through.
    (r'.*/static/.*', direct_copy_step),
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
