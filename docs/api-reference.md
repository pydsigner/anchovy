# API Reference

Complete reference for all Anchovy classes, functions, and interfaces.

## Table of Contents

- [Core Classes](#core-classes)
- [Steps](#steps)
- [Matchers](#matchers)
- [PathCalcs](#pathcalcs)
- [Custody System](#custody-system)
- [Dependencies](#dependencies)
- [CLI](#cli)
- [Utilities](#utilities)

## Core Classes

### Context

The central build orchestrator.

```python
class Context:
    def __init__(
        self,
        settings: BuildSettings,
        rules: list[Rule],
        custodian: Custodian | None = None
    )
```

**Parameters:**
- `settings`: Build configuration
- `rules`: List of processing rules
- `custodian`: Optional custom Custodian instance

**Methods:**

#### `bind()`
```python
def bind(self) -> None
```
Bind all Steps to this Context. Called automatically during initialization.

#### `run()`
```python
def run(self) -> None
```
Execute the complete build pipeline:
1. Optionally purge directories
2. Process all files
3. Remove orphaned outputs
4. Save custody cache

#### `process()`
```python
def process(self) -> None
```
Process files without cleanup operations. Discovers inputs, matches against rules, executes steps, and recursively processes intermediate files.

#### `find_inputs()`
```python
def find_inputs(self, path: Path) -> Generator[Path, None, None]
```
Discover input files recursively.

**Parameters:**
- `path`: Directory to search

**Returns:** Generator yielding file paths

**Example:**
```python
for input_file in context.find_inputs(Path('site')):
    print(input_file)
```

#### `__getitem__()`
```python
def __getitem__(self, key: str) -> Path
```
Access context directories.

**Parameters:**
- `key`: Directory name (`'input_dir'`, `'output_dir'`, `'working_dir'`, `'custody_cache'`)

**Returns:** Path to directory

**Example:**
```python
input_dir = context['input_dir']
output_dir = context['output_dir']
```

---

### Rule

Defines a file processing rule.

```python
class Rule:
    def __init__(
        self,
        matcher: Matcher[T],
        path_calc: PathCalc[T] | list[PathCalc[T] | None] | Path | None,
        step: Step | None = None
    )
```

**Parameters:**
- `matcher`: Determines which files this rule applies to
- `path_calc`: Calculates output path(s). Can be:
  - Single `PathCalc` instance
  - List of `PathCalc` instances (can include `None` to halt)
  - `Path` constant
  - `None` to halt processing
- `step`: Optional file processor

**Example:**
```python
# Simple rule
Rule(
    REMatcher(r'.*\.md'),
    OutputDirPathCalc('.html'),
    JinjaMarkdownStep()
)

# Multiple outputs
Rule(
    REMatcher(r'.*\.jpg'),
    [OutputDirPathCalc(), OutputDirPathCalc('.thumb.jpg')],
    PillowStep(thumbnail=(300, 300))
)

# Process and halt
Rule(
    REMatcher(r'.*\.md'),
    [OutputDirPathCalc('.html'), None],
    JinjaMarkdownStep()
)

# Ignore files
Rule(REMatcher(r'.*\.draft\.md'), None)
```

---

### Step

Abstract base class for file processors.

```python
class Step(ABC):
    @abstractmethod
    def __call__(
        self,
        path: Path,
        output_paths: list[Path]
    ) -> None | tuple[list[Path | CustodyEntry], list[Path]]
```

**Parameters:**
- `path`: Input file path
- `output_paths`: List of output file paths

**Returns:**
- `None` for standard processing
- `tuple[sources, outputs]` for explicit custody tracking

**Methods:**

#### `bind()`
```python
def bind(self, context: Context) -> None
```
Called when Step is added to a Context. Override to initialize resources.

#### `get_dependencies()`
```python
def get_dependencies(self) -> Dependency | None
```
Declare external dependencies. Override to specify requirements.

**Returns:** Dependency object or None

#### `is_available()`
```python
def is_available(self) -> bool
```
Check if all dependencies are satisfied.

**Returns:** True if Step can be used

#### Class Methods

```python
@classmethod
def get_all_steps() -> list[type[Step]]
```
Get all registered Step classes.

```python
@classmethod
def get_available_steps() -> list[type[Step]]
```
Get Step classes with satisfied dependencies.

**Example:**
```python
class MyStep(Step):
    def __init__(self, option: str):
        super().__init__()
        self.option = option

    def get_dependencies(self):
        return PipDependency('some_package')

    def bind(self, context):
        super().bind(context)
        self.output_dir = context['output_dir']

    def __call__(self, path: Path, output_paths: list[Path]) -> None:
        content = path.read_text()
        result = self.transform(content)

        for output_path in output_paths:
            output_path.write_text(result)

    def transform(self, content: str) -> str:
        return content.upper()
```

---

### Matcher

Abstract base class for file matching.

```python
class Matcher(ABC, Generic[T]):
    @abstractmethod
    def __call__(
        self,
        context: Context,
        path: Path
    ) -> T | None
```

**Parameters:**
- `context`: Build context
- `path`: File path to check

**Returns:** Any value if matched, None otherwise

**Operators:**

```python
matcher1 | matcher2  # OR: matches if either matches
matcher1 & matcher2  # AND: matches if both match
~matcher             # NOT: matches if matcher doesn't match
```

**Example:**
```python
class MyMatcher(Matcher[int]):
    def __call__(self, context: Context, path: Path) -> int | None:
        if path.suffix == '.txt':
            return path.stat().st_size
        return None

# Usage
matcher = MyMatcher()
result = matcher(context, Path('file.txt'))  # Returns file size or None
```

---

### PathCalc

Abstract base class for output path calculation.

```python
class PathCalc(ABC, Generic[T]):
    @abstractmethod
    def __call__(
        self,
        context: Context,
        path: Path,
        match: T
    ) -> Path
```

**Parameters:**
- `context`: Build context
- `path`: Input file path
- `match`: Value returned by Matcher

**Returns:** Output path

**Example:**
```python
class MyPathCalc(PathCalc[int]):
    def __call__(self, context: Context, path: Path, match: int) -> Path:
        output_dir = context['output_dir']

        # Use match value (file size) in path
        if match > 1024:
            return output_dir / 'large' / path.name
        else:
            return output_dir / 'small' / path.name
```

---

## Settings

### InputBuildSettings

User-provided configuration (TypedDict).

```python
class InputBuildSettings(TypedDict, total=False):
    input_dir: Path              # Required
    output_dir: Path             # Optional
    working_dir: Path | None     # Optional
    custody_cache: Path | None   # Optional
    purge_dirs: bool | None      # Optional
```

**Fields:**
- `input_dir`: Source files directory (required)
- `output_dir`: Final output directory (default: `input_dir / 'build'`)
- `working_dir`: Intermediate files directory (default: temp directory)
- `custody_cache`: Custody cache file path (default: None, disabled)
- `purge_dirs`: Purge output/working directories before build (default: False)

---

### BuildSettings

Fully resolved settings (TypedDict).

```python
class BuildSettings(TypedDict):
    input_dir: Path
    output_dir: Path
    working_dir: Path           # Never None
    custody_cache: Path | None
    purge_dirs: bool | None
```

All fields are required. Created by Context or CLI from InputBuildSettings.

---

## Steps

### DirectCopyStep

```python
class DirectCopyStep(Step):
    def __init__(self)
```

Simply copies files without modification.

**Dependencies:** None

---

### BaseStandardStep

```python
class BaseStandardStep(Step, ABC):
    def __init__(
        self,
        encoding: str = 'utf-8',
        newline: str | None = None
    )
```

Base class for steps creating one primary output and copying to others.

**Parameters:**
- `encoding`: Text encoding (default: 'utf-8')
- `newline`: Newline character (default: None, universal newlines)

**Abstract Methods:**

```python
@abstractmethod
def process(self, input_path: Path, output_path: Path) -> None
```

Implement to create the primary output.

**Helper Methods:**

```python
def ensure_output_dirs(self, *paths: Path) -> None
```
Create parent directories for output paths.

```python
def duplicate_output_paths(
    self,
    primary: Path,
    others: list[Path]
) -> None
```
Copy primary output to other output paths.

```python
@contextmanager
def ensure_outputs(self, primary: Path, others: list[Path] = [])
```
Context manager combining directory creation and duplication.

---

### BaseCommandStep

```python
class BaseCommandStep(Step, ABC):
    def __init__(self)
```

Base class for steps invoking external executables.

**Abstract Methods:**

```python
@abstractmethod
def get_command(
    self,
    input_path: Path,
    output_path: Path
) -> list[str]
```

Return command to execute as list of strings.

**Overridable Methods:**

```python
def group_outputs(
    self,
    output_paths: list[Path]
) -> dict[str, list[Path]]
```

Group output paths by extension. Override for custom grouping.

---

### JinjaRenderStep

```python
class JinjaRenderStep(Step, ABC):
    def __init__(self, template_globals: dict | None = None)
```

Base class for Jinja template rendering.

**Parameters:**
- `template_globals`: Global variables for templates

**Methods:**

```python
def render_template(
    self,
    template_name: str,
    meta: dict,
    output_paths: list[Path]
) -> tuple[list[Path], list[Path]]
```

Render template and write to outputs.

**Parameters:**
- `template_name`: Template file name
- `meta`: Variables to pass to template
- `output_paths`: Where to write rendered output

**Returns:** `(sources, outputs)` for custody tracking

**Dependencies:** `jinja2`

---

### JinjaMarkdownStep

```python
class JinjaMarkdownStep(JinjaRenderStep):
    def __init__(
        self,
        frontmatter_parser: str | None = 'toml',
        enable_toc_anchors: bool = True,
        enable_syntax_highlight: bool = True,
        enable_typographer: bool = True,
        enable_containers: bool = True,
        enable_footnotes: bool = True,
        track_wordcount: bool = True,
        substitutions: bool = True,
        template_globals: dict | None = None
    )
```

Advanced Markdown renderer with Jinja templating.

**Parameters:**
- `frontmatter_parser`: Frontmatter format: `'toml'`, `'yaml'`, `'simple'`, or `None`
- `enable_toc_anchors`: Add IDs to headings for TOC
- `enable_syntax_highlight`: Pygments syntax highlighting
- `enable_typographer`: Smart quotes, ellipses, dashes
- `enable_containers`: Markdown containers (custom divs)
- `enable_footnotes`: Footnote support
- `track_wordcount`: Add `wordcount` to template context
- `substitutions`: Variable substitutions via `${{ var }}`
- `template_globals`: Global variables for templates

**Dependencies:** `jinja2`, `markdown-it-py`, `mdit_py_plugins`, `Pygments`, `tomli` (Python < 3.11)

---

### AnchovyCSSStep

```python
class AnchovyCSSStep(Step):
    def __init__(self)
```

Preprocesses Anchovy CSS format to standard CSS.

**Dependencies:** `anchovy_css`

---

### CSSMinifierStep

```python
class CSSMinifierStep(Step):
    def __init__(
        self,
        error_recovery: bool = True,
        flags: int = 0,
        unused_symbols: set[str] | None = None,
        targets: dict[str, int] | None = None,
        minify: bool = True
    )
```

Minifies CSS using LightningCSS.

**Parameters:**
- `error_recovery`: Recover from parse errors
- `flags`: Parser flags
- `unused_symbols`: CSS symbols to remove
- `targets`: Browser targets (default: Chrome 95, Firefox 94, Safari 15)
- `minify`: Enable minification

**Dependencies:** `lightningcss`

---

### HTMLMinifierStep

```python
class HTMLMinifierStep(Step):
    def __init__(
        self,
        minify_css: bool = True,
        minify_js: bool = True
    )
```

Fast HTML minification.

**Parameters:**
- `minify_css`: Minify inline CSS
- `minify_js`: Minify inline JavaScript

**Dependencies:** `minify-html-onepass` OR `minify-html`

---

### AssetMinifierStep

```python
class AssetMinifierStep(Step):
    def __init__(self, mime_type: str | None = None)
```

Multi-format minifier using tdewolff-minify.

**Parameters:**
- `mime_type`: MIME type override (auto-detected if None)

**Supported MIME types:**
- `text/css`, `text/html`, `application/javascript`, `text/javascript`
- `application/json`, `image/svg+xml`, `text/xml`, `application/xml`

**Dependencies:** `tdewolff-minify` (not supported on macOS)

---

### ResourcePackerStep

```python
class ResourcePackerStep(Step):
    def __init__(self)
```

Combines multiple files into one based on config file.

**Config format:** Text file with one filename per line, `#` for comments

**Dependencies:** None

---

### PillowStep

```python
class PillowStep(Step):
    def __init__(
        self,
        thumbnail: tuple[int, int] | None = None,
        transpose: bool = True
    )
```

Image conversion and optimization using Pillow.

**Parameters:**
- `thumbnail`: `(width, height)` for thumbnailing
- `transpose`: Apply EXIF orientation correction

**Dependencies:** `Pillow`

---

### CWebPStep

```python
class CWebPStep(BaseCommandStep):
    def __init__(
        self,
        quality: int = 75,
        lossless: bool = False,
        cwebp_options: list[str] | None = None
    )
```

WebP conversion using cwebp.

**Parameters:**
- `quality`: Quality 0-100 (ignored if lossless=True)
- `lossless`: Use lossless compression
- `cwebp_options`: Additional cwebp flags

**Dependencies:** `cwebp` executable

---

### ImageMagickStep

```python
class ImageMagickStep(BaseCommandStep):
    def __init__(self, *magick_options: str)
```

Image transformation using ImageMagick.

**Parameters:**
- `magick_options`: ImageMagick command options

**Dependencies:** `magick` executable

---

### IMThumbnailStep

```python
class IMThumbnailStep(ImageMagickStep):
    def __init__(
        self,
        dimensions: str = '300x300',
        fill_color: str | None = None,
        extra_options: list[str] | None = None
    )
```

Thumbnailing using ImageMagick.

**Parameters:**
- `dimensions`: ImageMagick geometry string
- `fill_color`: Padding color (e.g., `'#0000'` for transparent)
- `extra_options`: Additional ImageMagick options

**Dependencies:** `magick` executable

---

### OptipngStep

```python
class OptipngStep(BaseCommandStep):
    def __init__(
        self,
        optimization_level: int | None = None,
        extra_options: list[str] | None = None
    )
```

PNG optimization using optipng.

**Parameters:**
- `optimization_level`: 0-7 (default uses optipng default)
- `extra_options`: Additional optipng flags

**Dependencies:** `optipng` executable

---

### RequestsFetchStep

```python
class RequestsFetchStep(Step):
    def __init__(
        self,
        chunk_size: int = 8192,
        timeout: float | None = None
    )
```

Fetches resources from URLs defined in TOML files.

**Parameters:**
- `chunk_size`: Download chunk size in bytes
- `timeout`: Request timeout in seconds

**Config format:** TOML file with `url = "https://..."`

**Dependencies:** `requests`, `tomli` (Python < 3.11)

---

### URLLibFetchStep

```python
class URLLibFetchStep(Step):
    def __init__(
        self,
        chunk_size: int = 8192,
        timeout: float | None = None
    )
```

Fetches resources using stdlib urllib (alternative to RequestsFetchStep).

**Parameters:**
- `chunk_size`: Download chunk size in bytes
- `timeout`: Request timeout in seconds

**Dependencies:** `tomli` (Python < 3.11)

---

### UnpackArchiveStep

```python
class UnpackArchiveStep(Step):
    def __init__(self, format: str | None = None)
```

Extracts archive files.

**Parameters:**
- `format`: Archive format (`'zip'`, `'tar'`, `'gztar'`, `'bztar'`, `'xztar'`) or None for auto-detect

**Dependencies:** None (uses stdlib `shutil`)

---

## Matchers

### REMatcher

```python
class REMatcher(Matcher[re.Match[str] | None]):
    def __init__(
        self,
        pattern: str,
        parent_dir: str | None = None,
        flags: int = 0
    )
```

Regular expression file matcher.

**Parameters:**
- `pattern`: Regular expression pattern
- `parent_dir`: Make path relative to context directory before matching (`'input_dir'`, `'working_dir'`, etc.)
- `flags`: Regex flags (e.g., `re.IGNORECASE`)

**Returns:** `re.Match` object if matched, None otherwise

**Example:**
```python
# Match markdown files
REMatcher(r'.*\.md')

# Match with case insensitivity
REMatcher(r'.*\.MD', flags=re.IGNORECASE)

# Match relative to input_dir
REMatcher(r'blog/.*\.md', parent_dir='input_dir')

# Capture groups
REMatcher(r'(?P<year>\d{4})-(?P<month>\d{2})-(?P<name>.*)\.md')
```

---

## PathCalcs

### OutputDirPathCalc

```python
class OutputDirPathCalc(DirPathCalc):
    def __init__(
        self,
        ext: str | None = None,
        transform: Callable[[Path], Path] | None = None
    )
```

Places files in output_dir with optional extension change and transformation.

**Parameters:**
- `ext`: New extension (e.g., `'.html'`, `'.min.css'`)
- `transform`: Path transformation function

**Example:**
```python
# Same name
OutputDirPathCalc()

# Change extension
OutputDirPathCalc('.html')

# Transform path
OutputDirPathCalc(transform=lambda p: p.with_stem(f'{p.stem}-processed'))
```

---

### WorkingDirPathCalc

```python
class WorkingDirPathCalc(DirPathCalc):
    def __init__(
        self,
        ext: str | None = None,
        transform: Callable[[Path], Path] | None = None
    )
```

Places files in working_dir (for intermediate processing).

**Parameters:** Same as OutputDirPathCalc

---

### DirPathCalc

```python
class DirPathCalc(PathCalc[re.Match[str] | None]):
    def __init__(
        self,
        dest: Path | str,
        ext: str | None = None,
        transform: Callable[[Path], Path] | None = None
    )
```

Generic path calculator for any destination.

**Parameters:**
- `dest`: Destination directory (Path or context dir key like `'output_dir'`)
- `ext`: New extension
- `transform`: Path transformation function

**Example:**
```python
# To custom directory
DirPathCalc(dest=Path('custom/output'))

# To context directory
DirPathCalc(dest='output_dir', ext='.html')
```

---

### WebIndexPathCalc

```python
class WebIndexPathCalc(DirPathCalc):
    def __init__(self, index_base: str = 'index')
```

Converts paths to web-friendly index structure.

**Parameters:**
- `index_base`: Index filename base (default: `'index'`)

**Transforms:**
- `about.html` → `about/index.html`
- `blog/post.html` → `blog/post/index.html`
- `index.html` → `index.html` (unchanged)

---

## Custody System

### Custodian

```python
class Custodian:
    def __init__(self)
```

Manages chain-of-custody tracking for intelligent rebuilds.

**Methods:**

#### `bind()`
```python
def bind(self, context: Context) -> None
```

Associate with a Context.

#### `load_file()`
```python
def load_file(self, path: Path) -> None
```

Load custody cache from file.

#### `dump_file()`
```python
def dump_file(self, path: Path) -> None
```

Save custody cache to file.

#### `refresh_needed()`
```python
def refresh_needed(
    self,
    sources: list[Path | CustodyEntry],
    outputs: list[Path]
) -> tuple[bool, str]
```

Check if processing is needed.

**Returns:** `(is_stale, reason)` tuple

#### `add_step()`
```python
def add_step(
    self,
    sources: list[Path | CustodyEntry],
    outputs: list[Path],
    message: str
) -> None
```

Record that a step was executed.

#### `skip_step()`
```python
def skip_step(
    self,
    source: Path | CustodyEntry,
    outputs: list[Path]
) -> None
```

Record that a step was skipped (cached).

#### `register_checker()`
```python
@staticmethod
def register_checker(entry_type: str) -> Callable
```

Decorator to register custom custody entry checker.

**Example:**
```python
@Custodian.register_checker('my_type')
def check_my_type(entry: CustodyEntry) -> bool:
    # Return True if entry is still valid
    return entry['meta']['version'] == get_current_version()
```

---

### CustodyEntry

```python
class CustodyEntry(TypedDict):
    entry_type: str
    key: str
    meta: dict
```

Represents a custody record.

**Fields:**
- `entry_type`: Type identifier (`'path'`, `'requests'`, `'urllib'`, or custom)
- `key`: Unique identifier (file path, URL, etc.)
- `meta`: Type-specific metadata

**Example:**
```python
entry = CustodyEntry(
    entry_type='path',
    key='site/index.md',
    meta={
        'sha1': 'abc123...',
        'm_time': 1234567890.0,
        'size': 2048
    }
)
```

---

## Dependencies

### Dependency

```python
class Dependency(ABC):
    @property
    @abstractmethod
    def satisfied(self) -> bool

    @property
    @abstractmethod
    def needed(self) -> bool

    @property
    @abstractmethod
    def install_hint(self) -> str
```

Abstract base for dependency declarations.

**Operators:**

```python
dep1 | dep2  # OR: satisfied if either is satisfied
dep1 & dep2  # AND: satisfied if both are satisfied
```

---

### PipDependency

```python
class PipDependency(Dependency):
    def __init__(
        self,
        package: str,
        source: str | None = None,
        check_name: str | None = None
    )
```

Python package dependency.

**Parameters:**
- `package`: Package name for pip
- `source`: PyPI URL or description
- `check_name`: Import name (if different from package)

**Example:**
```python
PipDependency('Pillow', check_name='PIL')
PipDependency('markdown-it-py')
```

---

### WebExecDependency

```python
class WebExecDependency(Dependency):
    def __init__(
        self,
        executable: str,
        source: str,
        check_name: str | None = None
    )
```

Executable dependency.

**Parameters:**
- `executable`: Command name
- `source`: Download URL or description
- `check_name`: Alternative name to check

**Example:**
```python
WebExecDependency('cwebp', 'https://developers.google.com/speed/webp')
WebExecDependency('magick', 'https://imagemagick.org')
```

---

## CLI

### run_from_rules

```python
def run_from_rules(
    settings: InputBuildSettings,
    rules: list[Rule],
    custodian: Custodian | None = None,
    context_cls: type[Context] = Context,
    **context_kw
) -> None
```

Main programmatic entry point.

**Parameters:**
- `settings`: Build settings
- `rules`: Processing rules
- `custodian`: Optional custom Custodian
- `context_cls`: Context class to use
- `context_kw`: Additional Context kwargs

**Example:**
```python
from anchovy.cli import run_from_rules
from my_config import SETTINGS, RULES

run_from_rules(SETTINGS, RULES)
```

---

### main

```python
def main(arguments: list[str] | None = None) -> None
```

CLI entry point.

**Parameters:**
- `arguments`: Command-line arguments (default: sys.argv)

**Usage:**
```bash
anchovy config.py
anchovy -m package.module
python -m anchovy config.py -- -h
```

---

## Utilities

### Server

```python
def serve(
    port: int,
    directory: Path,
    host: str = 'localhost'
) -> None
```

Start HTTP server for built output.

**Parameters:**
- `port`: Server port
- `directory`: Directory to serve
- `host`: Bind address

**Example:**
```python
from anchovy.server import serve

serve(8080, Path('build'))
```

---

## Type Aliases

```python
# Settings type aliases
InputBuildSettings = TypedDict(...)
BuildSettings = TypedDict(...)

# Path-like types
PathLike = str | Path
```

---

## Constants

```python
# Default browser targets for CSSMinifierStep
DEFAULT_BROWSER_TARGETS = {
    'chrome': (95 << 16),
    'firefox': (94 << 16),
    'safari': (15 << 16),
}
```

---

## Environment

Context directories can be accessed via dictionary syntax:

```python
context['input_dir']     # Source files
context['output_dir']    # Final output
context['working_dir']   # Intermediate files
context['custody_cache'] # Cache file path (or None)
```

---

This reference covers all public APIs in Anchovy. For usage examples and patterns, see the other documentation guides.
