# Getting Started with Anchovy

Anchovy is a minimal, unopinionated file-processing framework designed for static website generation but flexible enough for any file transformation pipeline.

## Installation

### Basic Installation

For just the framework and core components:

```bash
pip install anchovy
```

### Recommended Installation

For typical static website generation with Jinja2 templating, Markdown, minification, and CSS preprocessing:

```bash
pip install anchovy[base]
```

### Other Installation Options

```bash
# Web development features (markdown, CSS, images, minification)
pip install anchovy[web]

# Jinja2 templating support
pip install anchovy[jinja]

# Markdown rendering with syntax highlighting
pip install anchovy[markdown]

# CSS preprocessing
pip install anchovy[css]

# Image processing (Pillow)
pip install anchovy[pillow]

# HTML/CSS/JS minification
pip install anchovy[minify]

# HTTP resource fetching
pip install anchovy[include]

# Pretty terminal output with rich
pip install anchovy[pretty]

# All features
pip install anchovy[all]
```

### Install from Source

```bash
pip install git+https://github.com/pydsigner/anchovy
# Or with extras
pip install git+https://github.com/pydsigner/anchovy#egg=anchovy[base]
```

## Your First Anchovy Project

Let's build a simple static website with Markdown content and static files.

### 1. Create the Project Structure

```
my-site/
├── config.py          # Anchovy configuration
└── site/              # Source files
    ├── static/
    │   ├── styles.css
    │   └── script.js
    ├── base.jinja.html
    ├── index.md
    └── about.md
```

### 2. Write the Configuration

Create `config.py`:

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

# Build settings - can be overridden via CLI arguments
SETTINGS = InputBuildSettings(
    input_dir=Path('site'),      # Where source files live
    output_dir=Path('build'),     # Where to put the final output
    working_dir=Path('working'),  # Temporary intermediate files
    custody_cache=Path('build-cache.json'),  # Track changes for rebuilds
)

# Processing rules - applied in order to each file
RULES = [
    # Rule 1: Ignore dotfiles (like .DS_Store)
    Rule(
        REMatcher(r'(.*/)*\..*', parent_dir='input_dir'),
        None  # None means "stop processing this file"
    ),

    # Rule 2: Render Markdown files to HTML
    Rule(
        REMatcher(r'.*\.md'),              # Match files ending in .md
        OutputDirPathCalc('.html'),        # Change .md -> .html in output_dir
        JinjaMarkdownStep()                # Render with Jinja and Markdown
    ),

    # Rule 3: Copy static files directly
    Rule(
        REMatcher(r'(.*/)*static/.*', parent_dir='input_dir'),
        OutputDirPathCalc(),               # Keep same name in output_dir
        DirectCopyStep()                   # Just copy without modification
    ),
]
```

### 3. Create Content

Create `site/base.jinja.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title | default('My Site') }}</title>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <nav>
        <a href="/">Home</a>
        <a href="/about.html">About</a>
    </nav>
    <main>
        {{ content }}
    </main>
    <script src="/static/script.js"></script>
</body>
</html>
```

Create `site/index.md`:

```markdown
---
title: Welcome to My Site
template: base.jinja.html
---

# Welcome!

This is my first Anchovy-powered website.

## Features

- Simple Markdown content
- Jinja2 templating
- Static file handling
```

Create `site/about.md`:

```markdown
---
title: About Us
template: base.jinja.html
---

# About

Learn more about this project.
```

Create `site/static/styles.css`:

```css
body {
    font-family: sans-serif;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
}

nav {
    margin-bottom: 2rem;
}

nav a {
    margin-right: 1rem;
}
```

### 4. Build the Site

```bash
# Run the build
python -m anchovy config.py

# Build and serve with live preview
python -m anchovy config.py -s -p 8080
```

The output will be in the `build/` directory:

```
build/
├── static/
│   ├── styles.css
│   └── script.js
├── index.html
└── about.html
```

## Command Line Usage

### Basic Commands

```bash
# Build from a config file
python -m anchovy config.py

# Build from a Python module
anchovy -m mypackage.siteconfig

# Override settings with CLI flags
anchovy config.py -i ./source -o ./public -w ./temp

# Serve the output after building
anchovy config.py -s -p 8080

# Show help for your config's custom arguments
python -m anchovy config.py -- -h

# Audit available and unavailable Steps
anchovy config.py --audit-steps
```

### CLI Arguments

- `-i, --input-dir PATH`: Override input directory
- `-o, --output-dir PATH`: Override output directory
- `-w, --working-dir PATH`: Override working directory
- `--custody-cache PATH`: Override custody cache file
- `--purge`: Purge output and working directories before building
- `-s, --serve`: Start HTTP server after building
- `-p, --port PORT`: Server port (default: 8080)
- `-m, --module`: Load config from a Python module instead of file
- `--audit-steps`: Show available/unavailable Steps without building
- `-h, --help`: Show help message

## Understanding the Build Process

When you run Anchovy:

1. **Discovery**: Anchovy finds all files in `input_dir`
2. **Matching**: Each file is tested against Rules in order
3. **Path Calculation**: Matched files get their output paths calculated
4. **Processing**: Steps transform files (render templates, copy, etc.)
5. **Intermediate Files**: Files in `working_dir` are re-processed
6. **Caching**: If custody cache is enabled, unchanged files are skipped

### How Rules Work

A Rule has three parts:

```python
Rule(
    matcher,      # Determines if this rule applies to a file
    path_calc,    # Calculates where the output should go
    step          # Transforms the file
)
```

- **Matcher**: Returns a truthy value if the file matches, None otherwise
- **PathCalc**: Can be a single PathCalc, a list, or None to halt processing
- **Step**: Optional file processor (None to just match without processing)

### Example Rule Patterns

```python
# Ignore files (no path_calc means stop processing)
Rule(REMatcher(r'.*\.draft\.md'), None)

# Process and stop (path_calc list ends with None)
Rule(
    REMatcher(r'.*\.md'),
    [OutputDirPathCalc('.html'), None],  # None stops further processing
    JinjaMarkdownStep()
)

# Process and continue (file goes to working_dir for more rules)
Rule(
    REMatcher(r'.*\.md'),
    WorkingDirPathCalc('.html'),  # Continues to be processed
    JinjaMarkdownStep()
)

# Multiple outputs from one input
Rule(
    REMatcher(r'.*\.jpg'),
    [
        OutputDirPathCalc(),              # Original size
        OutputDirPathCalc('.thumb.jpg'),  # Thumbnail
    ],
    IMThumbnailStep(dimensions='300x300')
)
```

## Next Steps

- [Core Concepts](./core-concepts.md) - Deep dive into Rules, Steps, Matchers, and PathCalcs
- [Steps Reference](./steps-reference.md) - Complete guide to all built-in Steps
- [Custody and Rebuilds](./custody-and-rebuilds.md) - Smart caching and incremental builds
- [Advanced Usage](./advanced-usage.md) - Custom Steps, programmatic usage, and more
- [API Reference](./api-reference.md) - Complete API documentation

## Example Projects

The Anchovy repository includes several complete examples:

- `examples/basic_site.py` - Simple Markdown site (similar to this guide)
- `examples/code_index.py` - Comprehensive demo with many features
- `examples/gallery.py` - Image gallery with thumbnails

Run them with:

```bash
anchovy examples/basic_site.py -s -p 8080
```
