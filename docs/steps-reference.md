# Steps Reference

This is a comprehensive guide to all built-in Steps in Anchovy. Steps are file processors that transform inputs into outputs.

## Table of Contents

- [Basic Steps](#basic-steps)
- [Template & Markdown](#template--markdown)
- [CSS Processing](#css-processing)
- [Minification](#minification)
- [Image Processing](#image-processing)
- [Network & Archives](#network--archives)
- [Creating Custom Steps](#creating-custom-steps)

## Basic Steps

### DirectCopyStep

Simply copies files without modification.

```python
from anchovy import DirectCopyStep

DirectCopyStep()
```

**Use Cases:**
- Static assets (images, fonts, etc.)
- Pre-built files
- Binary files

**Example:**
```python
Rule(
    REMatcher(r'static/.*'),
    OutputDirPathCalc(),
    DirectCopyStep()
)
```

**Dependencies:** None

---

## Template & Markdown

### JinjaRenderStep

Base class for rendering Jinja2 templates. Typically you'll use `JinjaMarkdownStep` instead, but this is useful for custom template rendering.

```python
from anchovy import JinjaRenderStep

class MyTemplateStep(JinjaRenderStep):
    def __call__(self, path: Path, output_paths: list[Path]):
        # Prepare template variables
        meta = {'title': 'My Page'}

        # Render template
        template_name = path.name
        self.render_template(template_name, meta, output_paths)
```

**Configuration:**
```python
JinjaRenderStep(
    template_globals=None  # Dict of global variables for templates
)
```

**Dependencies:** `jinja2`

---

### JinjaMarkdownStep

Powerful Markdown renderer with Jinja2 templating, frontmatter support, syntax highlighting, and many extensions.

```python
from anchovy import JinjaMarkdownStep

JinjaMarkdownStep(
    frontmatter_parser='toml',
    enable_toc_anchors=True,
    enable_syntax_highlight=True,
    enable_typographer=True,
    enable_containers=True,
    enable_footnotes=True,
    track_wordcount=True,
    substitutions=True,
    template_globals=None
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `frontmatter_parser` | `str \| None` | `'toml'` | Frontmatter format: `'toml'`, `'yaml'`, `'simple'`, or `None` |
| `enable_toc_anchors` | `bool` | `True` | Add anchor IDs to headings for table of contents |
| `enable_syntax_highlight` | `bool` | `True` | Syntax highlighting for code blocks with Pygments |
| `enable_typographer` | `bool` | `True` | Smart quotes, ellipses, dashes |
| `enable_containers` | `bool` | `True` | Markdown containers (custom divs) |
| `enable_footnotes` | `bool` | `True` | Footnote support |
| `track_wordcount` | `bool` | `True` | Add `wordcount` variable to template context |
| `substitutions` | `bool` | `True` | Variable substitutions via `${{ var }}` |
| `template_globals` | `dict \| None` | `None` | Global variables for all templates |

**Frontmatter Examples:**

TOML:
```markdown
---
title = "My Post"
date = 2024-01-15
tags = ["python", "anchovy"]
template = "post.jinja.html"
---

# Content here
```

YAML:
```markdown
---
title: My Post
date: 2024-01-15
tags:
  - python
  - anchovy
template: post.jinja.html
---

# Content here
```

Simple (key: value):
```markdown
---
title: My Post
date: 2024-01-15
template: post.jinja.html
---

# Content here
```

**Template Variables:**

The template receives these variables:

```python
{
    'content': '<p>Rendered HTML content</p>',
    'title': 'From frontmatter',
    'date': 'From frontmatter',
    'wordcount': 42,  # If track_wordcount=True
    # ... any other frontmatter fields
}
```

**Template Example:**

```html
<!DOCTYPE html>
<html>
<head>
    <title>{{ title | default('Untitled') }}</title>
    <meta name="date" content="{{ date }}">
</head>
<body>
    <article>
        <h1>{{ title }}</h1>
        <p class="meta">{{ wordcount }} words</p>
        {{ content }}
    </article>
</body>
</html>
```

**Markdown Extensions:**

Syntax highlighting:
````markdown
```python
def hello():
    print("Hello, world!")
```
````

Containers:
```markdown
::: warning
This is a warning message
:::

::: note
This is a note
:::
```

Renders as:
```html
<div class="warning">
<p>This is a warning message</p>
</div>
```

Footnotes:
```markdown
Here's a sentence with a footnote[^1].

[^1]: This is the footnote content.
```

Variable substitution:
```markdown
---
site_name = "My Blog"
---

Welcome to ${{ site_name }}!
```

**Complete Example:**

```python
Rule(
    REMatcher(r'.*\.md'),
    OutputDirPathCalc('.html'),
    JinjaMarkdownStep(
        frontmatter_parser='toml',
        enable_toc_anchors=True,
        enable_syntax_highlight=True,
        enable_typographer=True,
        template_globals={
            'site_name': 'My Blog',
            'base_url': 'https://example.com'
        }
    )
)
```

**Dependencies:** `jinja2`, `markdown-it-py`, `mdit_py_plugins`, `Pygments`, `tomli` (Python < 3.11)

---

## CSS Processing

### AnchovyCSSStep

Preprocesses Anchovy CSS format into standard CSS.

```python
from anchovy import AnchovyCSSStep

AnchovyCSSStep()
```

**Anchovy CSS Features:**
- Nested selectors
- Variables
- Mixins
- See [anchovy_css documentation](https://github.com/pydsigner/anchovy_css) for details

**Example:**

```python
Rule(
    REMatcher(r'.*\.acss'),
    OutputDirPathCalc('.css'),
    AnchovyCSSStep()
)
```

**Dependencies:** `anchovy_css`

---

## Minification

### ResourcePackerStep

Combines multiple files into a single file. Reads a config file listing files to combine.

```python
from anchovy import ResourcePackerStep

ResourcePackerStep()
```

**Config File Format:**

```
# pack.txt - lines starting with # are comments
vendor/jquery.min.js
vendor/bootstrap.min.js
src/app.js
src/utils.js
```

**Example:**

```python
# Input: scripts.pack.txt -> Output: scripts.js
Rule(
    REMatcher(r'.*\.pack\.txt'),
    OutputDirPathCalc(transform=lambda p: p.with_suffix('.js')),
    ResourcePackerStep()
)
```

**Custody Tracking:** Returns explicit custody chain with all included files as sources.

**Dependencies:** None

---

### CSSMinifierStep

Minifies CSS files using LightningCSS with advanced optimization options.

```python
from anchovy import CSSMinifierStep

CSSMinifierStep(
    error_recovery=True,
    flags=0,
    unused_symbols=None,
    targets=None,
    minify=True
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `error_recovery` | `bool` | `True` | Recover from parse errors when possible |
| `flags` | `int` | `0` | Parser flags (see LightningCSS docs) |
| `unused_symbols` | `set \| None` | `None` | CSS symbols to remove |
| `targets` | `dict \| None` | Browsers | Browser targets for vendor prefixes |
| `minify` | `bool` | `True` | Enable minification |

**Default Browser Targets:**
```python
{
    'chrome': (95 << 16),   # Chrome 95+
    'firefox': (94 << 16),  # Firefox 94+
    'safari': (15 << 16),   # Safari 15+
}
```

**Example:**

```python
Rule(
    REMatcher(r'.*\.css'),
    OutputDirPathCalc('.min.css'),
    CSSMinifierStep(
        minify=True,
        targets={'chrome': (100 << 16)}  # Chrome 100+
    )
)
```

**Dependencies:** `lightningcss`

---

### HTMLMinifierStep

Fast HTML minification with optional CSS/JS minification.

```python
from anchovy import HTMLMinifierStep

HTMLMinifierStep(
    minify_css=True,
    minify_js=True
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `minify_css` | `bool` | `True` | Minify inline CSS |
| `minify_js` | `bool` | `True` | Minify inline JavaScript |

**Example:**

```python
Rule(
    REMatcher(r'.*\.html'),
    OutputDirPathCalc('.min.html'),
    HTMLMinifierStep(minify_css=True, minify_js=True)
)
```

**Implementation Note:** Uses `minify-html-onepass` by default, falls back to `minify-html` if unavailable.

**Dependencies:** `minify-html-onepass` OR `minify-html`

---

### AssetMinifierStep

Multi-format minifier supporting CSS, HTML, JS, JSON, SVG, and XML using tdewolff-minify.

```python
from anchovy import AssetMinifierStep

AssetMinifierStep(
    mime_type=None
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mime_type` | `str \| None` | `None` | MIME type override (auto-detected if None) |

**Supported Formats:**
- `text/css` - CSS files
- `text/html` - HTML files
- `application/javascript` / `text/javascript` - JavaScript files
- `application/json` - JSON files
- `image/svg+xml` - SVG files
- `text/xml` / `application/xml` - XML files

**Example:**

```python
# Auto-detect format
Rule(
    REMatcher(r'assets/.*\.(css|html|js|json|svg|xml)'),
    OutputDirPathCalc(),
    AssetMinifierStep()
)

# Force specific MIME type
Rule(
    REMatcher(r'.*\.xml'),
    OutputDirPathCalc(),
    AssetMinifierStep(mime_type='text/xml')
)
```

**Platform Note:** Not supported on macOS (Darwin).

**Dependencies:** `tdewolff-minify`

---

## Image Processing

### PillowStep

Pure Python image conversion and optimization using Pillow. Supports thumbnailing and EXIF orientation correction.

```python
from anchovy import PillowStep

PillowStep(
    thumbnail=None,
    transpose=True
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `thumbnail` | `tuple \| None` | `None` | `(width, height)` for thumbnailing |
| `transpose` | `bool` | `True` | Apply EXIF orientation correction |

**Supported Formats:** JPEG, PNG, WebP, GIF, BMP, TIFF, and [many more](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html)

**Examples:**

```python
# Simple conversion (JPEG to WebP)
Rule(
    REMatcher(r'.*\.jpg'),
    OutputDirPathCalc('.webp'),
    PillowStep()
)

# Create thumbnails
Rule(
    REMatcher(r'gallery/.*\.jpg'),
    [
        OutputDirPathCalc(),              # Full size
        OutputDirPathCalc('.thumb.jpg'),  # Thumbnail
    ],
    PillowStep(thumbnail=(300, 300))
)

# Fix orientation, no thumbnailing
Rule(
    REMatcher(r'photos/.*\.jpg'),
    OutputDirPathCalc(),
    PillowStep(transpose=True)
)
```

**Thumbnailing Behavior:**
- Preserves aspect ratio
- Downscales only (never upscales)
- Uses high-quality Lanczos resampling

**Transposition:**
- Reads EXIF orientation tag
- Rotates/flips image accordingly
- Removes EXIF orientation tag
- Ensures images display correctly in all browsers

**Dependencies:** `Pillow`

---

### CWebPStep

WebP conversion and optimization using the `cwebp` command-line tool.

```python
from anchovy import CWebPStep

CWebPStep(
    quality=75,
    lossless=False,
    cwebp_options=None
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `quality` | `int` | `75` | Quality level 0-100 (ignored if lossless=True) |
| `lossless` | `bool` | `False` | Use lossless compression |
| `cwebp_options` | `list \| None` | `None` | Additional cwebp command options |

**Examples:**

```python
# Lossy conversion
Rule(
    REMatcher(r'photos/.*\.(jpg|png)'),
    OutputDirPathCalc('.webp'),
    CWebPStep(quality=80)
)

# Lossless conversion
Rule(
    REMatcher(r'graphics/.*\.png'),
    OutputDirPathCalc('.webp'),
    CWebPStep(lossless=True)
)

# Custom options
Rule(
    REMatcher(r'.*\.png'),
    OutputDirPathCalc('.webp'),
    CWebPStep(
        quality=85,
        cwebp_options=['-m', '6', '-af']  # Max compression, auto-filter
    )
)
```

**Dependencies:** `cwebp` executable (from [WebP tools](https://developers.google.com/speed/webp/download))

---

### ImageMagickStep

Fully customizable image transformation using ImageMagick.

```python
from anchovy import ImageMagickStep

ImageMagickStep(
    *magick_options
)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `magick_options` | `str...` | ImageMagick command options |

**Examples:**

```python
# Resize to fixed dimensions
Rule(
    REMatcher(r'.*\.jpg'),
    OutputDirPathCalc('.resized.jpg'),
    ImageMagickStep('-resize', '800x600')
)

# Convert to grayscale
Rule(
    REMatcher(r'.*\.png'),
    OutputDirPathCalc('.gray.png'),
    ImageMagickStep('-colorspace', 'Gray')
)

# Complex pipeline
Rule(
    REMatcher(r'.*\.jpg'),
    OutputDirPathCalc('.processed.jpg'),
    ImageMagickStep(
        '-resize', '1200x1200>',  # Shrink if larger
        '-quality', '85',
        '-strip',                  # Remove metadata
        '-auto-orient'             # Fix orientation
    )
)
```

**Dependencies:** `magick` executable (ImageMagick 7+)

---

### IMThumbnailStep

Pre-configured ImageMagick for creating thumbnails with optional padding.

```python
from anchovy import IMThumbnailStep

IMThumbnailStep(
    dimensions='300x300',
    fill_color=None,
    extra_options=None
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dimensions` | `str` | `'300x300'` | ImageMagick geometry string |
| `fill_color` | `str \| None` | `None` | Padding color (e.g., `'#0000'` for transparent) |
| `extra_options` | `list \| None` | `None` | Additional ImageMagick options |

**Examples:**

```python
# Basic thumbnail (preserves aspect ratio)
Rule(
    REMatcher(r'gallery/.*\.jpg'),
    OutputDirPathCalc('.thumb.jpg'),
    IMThumbnailStep(dimensions='300x300')
)

# Thumbnail with transparent padding
Rule(
    REMatcher(r'products/.*\.png'),
    OutputDirPathCalc('.thumb.png'),
    IMThumbnailStep(
        dimensions='200x200',
        fill_color='#0000'  # Transparent
    )
)

# Thumbnail with white padding and border
Rule(
    REMatcher(r'.*\.jpg'),
    OutputDirPathCalc('.thumb.jpg'),
    IMThumbnailStep(
        dimensions='250x250',
        fill_color='white',
        extra_options=['-bordercolor', 'black', '-border', '1']
    )
)
```

**Geometry String Examples:**
- `'300x300'` - Fit within 300x300, preserve aspect ratio
- `'300x300^'` - Fill 300x300, preserve aspect ratio (may crop)
- `'300x300!'` - Force exact 300x300 (distort)
- `'50%'` - Scale to 50% of original

**Dependencies:** `magick` executable (ImageMagick)

---

### OptipngStep

PNG optimization using `optipng`.

```python
from anchovy import OptipngStep

OptipngStep(
    optimization_level=None,
    extra_options=None
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `optimization_level` | `int \| None` | `None` | Optimization level 0-7 (optipng default if None) |
| `extra_options` | `list \| None` | `None` | Additional optipng options |

**Examples:**

```python
# Default optimization
Rule(
    REMatcher(r'.*\.png'),
    OutputDirPathCalc(),
    OptipngStep()
)

# Maximum optimization (slowest)
Rule(
    REMatcher(r'assets/.*\.png'),
    OutputDirPathCalc(),
    OptipngStep(optimization_level=7)
)

# Custom options
Rule(
    REMatcher(r'.*\.png'),
    OutputDirPathCalc(),
    OptipngStep(
        optimization_level=2,
        extra_options=['-strip', 'all']  # Remove all metadata
    )
)
```

**Optimization Levels:**
- `0` - No optimization
- `1` - Fast, moderate compression
- `2` - Default balance
- `3-6` - Progressively slower, better compression
- `7` - Maximum compression (very slow)

**Dependencies:** `optipng` executable

---

## Network & Archives

### RequestsFetchStep

Fetches resources from URLs defined in TOML configuration files. Supports ETag-based caching.

```python
from anchovy import RequestsFetchStep

RequestsFetchStep(
    chunk_size=8192,
    timeout=None
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `chunk_size` | `int` | `8192` | Download chunk size in bytes |
| `timeout` | `float \| None` | `None` | Request timeout in seconds |

**Config File Format:**

```toml
url = "https://example.com/resource.js"
```

**Example:**

```python
# fetch.toml contains: url = "https://cdn.example.com/lib.js"
Rule(
    REMatcher(r'.*\.fetch\.toml'),
    OutputDirPathCalc(transform=lambda p: p.with_suffix('.js')),
    RequestsFetchStep(timeout=30)
)
```

**Custody Tracking:**
- Stores URL and ETag in custody cache
- Skips re-download if ETag unchanged
- Automatically handles HTTP caching

**Dependencies:** `requests`, `tomli` (Python < 3.11)

---

### URLLibFetchStep

Alternative to `RequestsFetchStep` using standard library `urllib`. Same functionality but no `requests` dependency.

```python
from anchovy import URLLibFetchStep

URLLibFetchStep(
    chunk_size=8192,
    timeout=None
)
```

**Parameters:** Same as `RequestsFetchStep`

**Example:**

```python
Rule(
    REMatcher(r'.*\.fetch\.toml'),
    OutputDirPathCalc(transform=lambda p: p.with_suffix('.js')),
    URLLibFetchStep()
)
```

**Dependencies:** `tomli` (Python < 3.11)

---

### UnpackArchiveStep

Extracts archive files (tar, zip, gzip, bzip2, xz).

```python
from anchovy import UnpackArchiveStep

UnpackArchiveStep(
    format=None
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | `str \| None` | `None` | Archive format (auto-detected if None) |

**Supported Formats:**
- `'zip'` - ZIP archives
- `'tar'` - TAR archives
- `'gztar'` - Gzipped TAR (.tar.gz)
- `'bztar'` - Bzip2'd TAR (.tar.bz2)
- `'xztar'` - XZ'd TAR (.tar.xz)

**Example:**

```python
# Auto-detect format
Rule(
    REMatcher(r'.*\.(zip|tar|tar\.gz|tar\.bz2|tar\.xz)'),
    OutputDirPathCalc(transform=lambda p: p.parent / p.stem),
    UnpackArchiveStep()
)

# Force specific format
Rule(
    REMatcher(r'.*\.bundle'),
    OutputDirPathCalc(transform=lambda p: p.parent / p.stem),
    UnpackArchiveStep(format='zip')
)
```

**Custody Tracking:** Returns all unpacked files for further processing

**Output Structure:**
```
Input:  archives/package.tar.gz
Output: build/archives/package/
         ├── file1.txt
         ├── file2.txt
         └── subdir/
             └── file3.txt
```

**Dependencies:** None (uses standard library `shutil`)

---

## Creating Custom Steps

### Basic Custom Step

```python
from pathlib import Path
from anchovy import Step

class UpperCaseStep(Step):
    """Converts text files to uppercase."""

    def __call__(self, path: Path, output_paths: list[Path]) -> None:
        # Read input
        content = path.read_text()

        # Transform
        result = content.upper()

        # Write to all outputs
        for output_path in output_paths:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result)
```

### Step with Configuration

```python
class ReplaceTextStep(Step):
    """Replaces text in files."""

    def __init__(self, old: str, new: str):
        super().__init__()
        self.old = old
        self.new = new

    def __call__(self, path: Path, output_paths: list[Path]) -> None:
        content = path.read_text()
        result = content.replace(self.old, self.new)

        for output_path in output_paths:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result)

# Usage
Rule(
    REMatcher(r'.*\.txt'),
    OutputDirPathCalc(),
    ReplaceTextStep(old='foo', new='bar')
)
```

### Step with Dependencies

```python
from anchovy import Step, PipDependency

class MarkdownStep(Step):
    """Custom markdown renderer."""

    def get_dependencies(self):
        return PipDependency('markdown', check_name='markdown')

    def __call__(self, path: Path, output_paths: list[Path]) -> None:
        import markdown

        content = path.read_text()
        html = markdown.markdown(content)

        for output_path in output_paths:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html)
```

### Step with Context Access

```python
class ContextAwareStep(Step):
    """Uses context directories."""

    def __call__(self, path: Path, output_paths: list[Path]) -> None:
        input_dir = self.context['input_dir']
        output_dir = self.context['output_dir']

        # Calculate relative path
        relative = path.relative_to(input_dir)

        # Use context information
        content = f"File: {relative}\nInput: {input_dir}\nOutput: {output_dir}\n"

        for output_path in output_paths:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content)
```

### Using BaseStandardStep

```python
from anchovy import BaseStandardStep

class MyRenderStep(BaseStandardStep):
    """Uses BaseStandardStep for simpler implementation."""

    def process(self, input_path: Path, output_path: Path) -> None:
        """Create the primary output. BaseStandardStep handles copying to other outputs."""
        content = input_path.read_text()
        result = self.transform(content)

        with self.ensure_outputs(output_path):
            output_path.write_text(result)

    def transform(self, content: str) -> str:
        """Your transformation logic."""
        return content.upper()
```

### Using BaseCommandStep

```python
from anchovy import BaseCommandStep, WebExecDependency

class PandocStep(BaseCommandStep):
    """Converts files using Pandoc."""

    def __init__(self, from_format: str, to_format: str):
        super().__init__()
        self.from_format = from_format
        self.to_format = to_format

    def get_command(self, input_path: Path, output_path: Path) -> list[str]:
        return [
            'pandoc',
            '-f', self.from_format,
            '-t', self.to_format,
            '-o', str(output_path),
            str(input_path)
        ]

    def get_dependencies(self):
        return WebExecDependency('pandoc', 'https://pandoc.org/')

# Usage
Rule(
    REMatcher(r'.*\.md'),
    OutputDirPathCalc('.docx'),
    PandocStep(from_format='markdown', to_format='docx')
)
```

### Explicit Custody Tracking

```python
class MultiSourceStep(Step):
    """Step with multiple source dependencies."""

    def __call__(self, path: Path, output_paths: list[Path]) -> tuple:
        # Read config to find additional sources
        config = self.parse_config(path)
        sources = [path]

        for include_file in config.get('includes', []):
            include_path = path.parent / include_file
            sources.append(include_path)

        # Process all sources
        combined = self.combine_sources(sources)

        # Write output
        for output_path in output_paths:
            output_path.write_text(combined)

        # Return explicit custody chain
        return (sources, output_paths)
```

## Step Discovery and Auditing

All Steps are automatically registered when defined. You can audit available Steps:

```bash
# Show all Steps and their availability
anchovy config.py --audit-steps
```

Output example:
```
Available Steps:
  DirectCopyStep
  JinjaMarkdownStep (requires: jinja2, markdown-it-py)
  PillowStep (requires: Pillow)

Unavailable Steps:
  CWebPStep (missing: cwebp executable)
  ImageMagickStep (missing: magick executable)
```

Programmatically:

```python
from anchovy import Step

# Get all registered Steps
all_steps = Step.get_all_steps()

# Get only available Steps
available = Step.get_available_steps()

# Check specific Step
if JinjaMarkdownStep in available:
    print("Markdown rendering is available")
```

## Next Steps

- [Matchers and PathCalcs](./matchers-pathcalcs.md) - Control file routing
- [Custody and Rebuilds](./custody-and-rebuilds.md) - Intelligent caching
- [Advanced Usage](./advanced-usage.md) - Custom components and programmatic usage
