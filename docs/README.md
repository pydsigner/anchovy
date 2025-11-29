# Anchovy Documentation

Welcome to the comprehensive documentation for Anchovy, a minimal, unopinionated file-processing framework designed for static website generation.

## Quick Links

- [Getting Started](./getting-started.md) - Installation and first project
- [Core Concepts](./core-concepts.md) - Understanding Rules, Steps, Matchers, and PathCalcs
- [Steps Reference](./steps-reference.md) - Complete guide to all built-in Steps
- [Matchers and PathCalcs](./matchers-pathcalcs.md) - Deep dive into file routing
- [Custody and Rebuilds](./custody-and-rebuilds.md) - Intelligent incremental builds
- [Advanced Usage](./advanced-usage.md) - Custom components and programmatic usage
- [API Reference](./api-reference.md) - Complete API documentation
- [FAQ](./FAQ.md) - Frequently asked questions and troubleshooting

## Documentation Structure

### For Beginners

Start here if you're new to Anchovy:

1. **[Getting Started](./getting-started.md)** - Set up your first project in minutes
2. **[Core Concepts](./core-concepts.md)** - Learn the fundamental abstractions
3. **[Steps Reference](./steps-reference.md)** - Explore available file processors

### For Regular Users

Once you're comfortable with the basics:

4. **[Matchers and PathCalcs](./matchers-pathcalcs.md)** - Master file routing and path transformations
5. **[Custody and Rebuilds](./custody-and-rebuilds.md)** - Speed up builds with intelligent caching

### For Advanced Users

Deep dive into customization and optimization:

6. **[Advanced Usage](./advanced-usage.md)** - Custom Steps, Contexts, programmatic usage
7. **[API Reference](./api-reference.md)** - Complete technical reference

## What is Anchovy?

Anchovy is a file-processing framework with three key characteristics:

### Minimal

- Core is ~1000 lines of code
- No mandatory dependencies
- Can be used with just a few pip-installable extras
- Simple, understandable architecture

### Unopinionated

- No assumptions about project structure
- Flexible component system
- Works for blogs, documentation, apps, or anything else
- Easy to integrate external tools

### Complete

- Dependency auditing system
- Wealth of built-in Steps for common tasks
- Intelligent rebuild system with custody tracking
- Development server included
- Reproducible builds with checksums

## Key Features

### Rich Step Library

Out-of-the-box support for:
- **Templates**: Jinja2 rendering with Markdown
- **CSS**: Preprocessing and minification
- **Images**: Conversion, thumbnailing, optimization (Pillow, ImageMagick, cwebp, optipng)
- **Minification**: HTML, CSS, JavaScript, JSON, SVG, XML
- **Network**: HTTP resource fetching with ETag caching
- **Archives**: Extraction of zip, tar, and compressed archives

### Intelligent Rebuilds

The custody system provides:
- SHA1-based change detection
- Dependency graph tracking
- Automatic staleness detection
- Reproducible build artifacts
- Orphan file cleanup

### Developer-Friendly

- Clear error messages
- Dependency auditing (`--audit-steps`)
- Built-in development server
- Progress tracking (with rich/tqdm)
- Extensible architecture

## Quick Example

Here's a minimal static site configuration:

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

SETTINGS = InputBuildSettings(
    input_dir=Path('site'),
    output_dir=Path('build'),
    custody_cache=Path('build-cache.json'),
)

RULES = [
    # Ignore dotfiles
    Rule(REMatcher(r'(.*/)*\..*'), None),

    # Render Markdown
    Rule(
        REMatcher(r'.*\.md'),
        OutputDirPathCalc('.html'),
        JinjaMarkdownStep()
    ),

    # Copy static files
    Rule(
        REMatcher(r'static/.*'),
        OutputDirPathCalc(),
        DirectCopyStep()
    ),
]
```

Run with:
```bash
python -m anchovy config.py
# Or serve with live preview
python -m anchovy config.py -s -p 8080
```

## Installation

```bash
# Minimal installation
pip install anchovy

# Recommended (includes Jinja, Markdown, CSS, minification)
pip install anchovy[base]

# Web features (markdown, CSS, images, minification)
pip install anchovy[web]

# All features
pip install anchovy[all]
```

## Common Tasks

### Render Markdown to HTML

```python
Rule(
    REMatcher(r'.*\.md'),
    OutputDirPathCalc('.html'),
    JinjaMarkdownStep(
        frontmatter_parser='toml',
        enable_syntax_highlight=True,
        enable_toc_anchors=True
    )
)
```

### Create Image Thumbnails

```python
Rule(
    REMatcher(r'gallery/.*\.jpg'),
    [
        OutputDirPathCalc(),              # Full size
        OutputDirPathCalc('.thumb.jpg'),  # Thumbnail
    ],
    PillowStep(thumbnail=(300, 300))
)
```

### Minify HTML/CSS/JS

```python
# HTML
Rule(
    REMatcher(r'.*\.html', parent_dir='working_dir'),
    OutputDirPathCalc(),
    HTMLMinifierStep(minify_css=True, minify_js=True)
)

# CSS
Rule(
    REMatcher(r'.*\.css'),
    OutputDirPathCalc('.min.css'),
    CSSMinifierStep()
)
```

### Multi-Stage Pipeline

```python
RULES = [
    # Stage 1: Markdown → HTML (working_dir)
    Rule(
        REMatcher(r'.*\.md', parent_dir='input_dir'),
        WorkingDirPathCalc('.html'),
        JinjaMarkdownStep()
    ),

    # Stage 2: HTML → Minified HTML (output_dir)
    Rule(
        REMatcher(r'.*\.html', parent_dir='working_dir'),
        [OutputDirPathCalc(), None],  # Stop after this
        HTMLMinifierStep()
    ),
]
```

## Examples

The repository includes several complete examples:

- **[examples/basic_site.py](../examples/basic_site.py)** - Simple Markdown site
- **[examples/code_index.py](../examples/code_index.py)** - Comprehensive demo
- **[examples/gallery.py](../examples/gallery.py)** - Image gallery with thumbnails

Run them with:
```bash
anchovy examples/basic_site.py -s -p 8080
```

## Getting Help

- **[GitHub Issues](https://github.com/pydsigner/anchovy/issues)** - Report bugs or request features
- **[Documentation](./getting-started.md)** - Start with Getting Started guide
- **[Examples](../examples/)** - Browse example projects
- **CLI Help** - Run `anchovy -h` or `anchovy config.py -- -h`

## Contributing

Anchovy is open source under the Apache 2.0 license. Contributions are welcome!

## License

Apache License 2.0 - see LICENSE file for details.

---

**Next Steps:**
- New to Anchovy? Start with [Getting Started](./getting-started.md)
- Building a site? Check out [Steps Reference](./steps-reference.md)
- Need advanced features? See [Advanced Usage](./advanced-usage.md)
