# Core Concepts

This guide explains the fundamental abstractions in Anchovy and how they work together to create powerful file-processing pipelines.

## Table of Contents

- [Context](#context)
- [Rules](#rules)
- [Steps](#steps)
- [Matchers](#matchers)
- [PathCalcs](#pathcalcs)
- [Build Settings](#build-settings)
- [Workflow](#workflow)

## Context

The `Context` is the central orchestrator of your build. It manages settings, executes rules, and coordinates the entire pipeline.

### Creating a Context

```python
from pathlib import Path
from anchovy import Context, BuildSettings

settings = BuildSettings(
    input_dir=Path('site'),
    output_dir=Path('build'),
    working_dir=Path('working'),
    custody_cache=Path('build-cache.json'),
    purge_dirs=False
)

context = Context(settings, rules=[...])
```

### Context Directories

The Context manages four key directories:

```python
context['input_dir']    # Source files (read-only)
context['output_dir']   # Final output destination
context['working_dir']  # Temporary intermediate files
context['custody_cache'] # Build cache file (optional)
```

You can access these in your Steps and PathCalcs using the context's `__getitem__` method.

### Context Workflow

```python
# Full build with cleanup
context.run()

# Process files without cleanup
context.process()
```

The `run()` method:
1. Optionally purges output and working directories
2. Calls `process()` to transform files
3. Removes orphaned files (when custody cache is available)
4. Saves the custody cache

The `process()` method:
1. Discovers all input files
2. Matches each file against Rules
3. Calculates output paths
4. Executes Steps
5. Re-processes intermediate files from working_dir

## Rules

Rules determine which files get processed and how. Each Rule is a mapping from file patterns to processing instructions.

### Rule Anatomy

```python
from anchovy import Rule, REMatcher, OutputDirPathCalc, JinjaMarkdownStep

Rule(
    matcher=REMatcher(r'.*\.md'),      # Which files match
    path_calc=OutputDirPathCalc('.html'),  # Where outputs go
    step=JinjaMarkdownStep()           # How to transform
)
```

### Rule Components

A Rule has three components:

1. **Matcher**: Determines if the rule applies to a file
2. **PathCalc**: Calculates output paths (can be a single PathCalc, a list, or None)
3. **Step**: Optional file processor (can be None)

### Rule Matching

Rules are evaluated in order. The first matching rule processes the file:

```python
RULES = [
    # First check for draft files - these are ignored
    Rule(REMatcher(r'.*\.draft\.md'), None),

    # Then process normal markdown files
    Rule(REMatcher(r'.*\.md'), OutputDirPathCalc('.html'), JinjaMarkdownStep()),

    # Catch-all for other files
    Rule(REMatcher(r'.*'), OutputDirPathCalc(), DirectCopyStep()),
]
```

### Halting Processing

You can stop processing a file in several ways:

```python
# Option 1: None as path_calc (file is matched but not processed)
Rule(REMatcher(r'.*\.draft'), None)

# Option 2: None at end of path_calc list (process once, then stop)
Rule(
    REMatcher(r'.*\.md'),
    [OutputDirPathCalc('.html'), None],
    JinjaMarkdownStep()
)

# Option 3: No step (just calculate paths, don't transform)
Rule(REMatcher(r'.*\.txt'), OutputDirPathCalc())
```

### Multiple Output Paths

A single input can produce multiple outputs:

```python
Rule(
    REMatcher(r'.*\.jpg'),
    [
        OutputDirPathCalc(),                    # Full size
        OutputDirPathCalc('.thumb.jpg'),        # Thumbnail
        OutputDirPathCalc('.webp', transform=lambda p: p.with_suffix('.webp')),
    ],
    PillowStep(thumbnail=(300, 300))
)
```

### Continuing Processing

Files placed in `working_dir` are automatically re-processed:

```python
RULES = [
    # Step 1: Markdown -> HTML (in working_dir)
    Rule(
        REMatcher(r'.*\.md', parent_dir='input_dir'),
        WorkingDirPathCalc('.html'),
        JinjaMarkdownStep()
    ),

    # Step 2: HTML -> Minified HTML (in output_dir)
    Rule(
        REMatcher(r'.*\.html', parent_dir='working_dir'),
        [OutputDirPathCalc(), None],  # Stop after minification
        HTMLMinifierStep()
    ),
]
```

## Steps

Steps are the workhorses of Anchovy - they transform files from inputs to outputs.

### Step Interface

All Steps inherit from the `Step` base class:

```python
from anchovy import Step

class MyStep(Step):
    def __call__(self, path: Path, output_paths: list[Path]) -> None:
        """
        Transform the input file at `path` into outputs at `output_paths`.

        Args:
            path: Input file path
            output_paths: List of output file paths

        Returns:
            None for standard processing, or (sources, outputs) tuple
            for explicit custody chain tracking
        """
        # Read input
        content = path.read_text()

        # Transform
        result = content.upper()

        # Write outputs
        for output_path in output_paths:
            output_path.write_text(result)
```

### Step Lifecycle

1. **Class Definition**: Step is defined and auto-registered
2. **Binding**: `bind(context)` is called when Step joins a Context
3. **Dependency Check**: `is_available()` confirms dependencies are met
4. **Execution**: `__call__(path, output_paths)` transforms files

### Declaring Dependencies

Steps can declare their requirements:

```python
from anchovy import Step, PipDependency, WebExecDependency

class MyImageStep(Step):
    def get_dependencies(self):
        return PipDependency('Pillow', check_name='PIL')

class MyOptimizeStep(Step):
    def get_dependencies(self):
        return WebExecDependency(
            'optipng',
            'http://optipng.sourceforge.net/'
        )
```

Dependencies can be composed with `|` (OR) and `&` (AND):

```python
def get_dependencies(self):
    # Need either PIL or ImageMagick
    return (
        PipDependency('Pillow', check_name='PIL')
        | WebExecDependency('magick', 'https://imagemagick.org')
    )
```

### Context Access

Steps can access the Context they're bound to:

```python
class ContextAwareStep(Step):
    def __call__(self, path: Path, output_paths: list[Path]) -> None:
        input_dir = self.context['input_dir']
        output_dir = self.context['output_dir']

        # Use context information
        relative_path = path.relative_to(input_dir)
        # ...
```

### Base Step Classes

Anchovy provides helpful base classes:

```python
from anchovy import DirectCopyStep, BaseStandardStep, BaseCommandStep

# DirectCopyStep - simple file copying
DirectCopyStep()

# BaseStandardStep - for creating one primary output + copies
class MyRenderStep(BaseStandardStep):
    def process(self, input_path: Path, output_path: Path) -> None:
        # Create the primary output
        content = input_path.read_text()
        output_path.write_text(content.upper())

# BaseCommandStep - for invoking external programs
class MyToolStep(BaseCommandStep):
    def get_command(self, input_path: Path, output_path: Path) -> list[str]:
        return ['mytool', '-i', str(input_path), '-o', str(output_path)]

    def get_dependencies(self):
        return WebExecDependency('mytool', 'https://...')
```

### Explicit Custody Tracking

Steps can return explicit custody chains to track additional dependencies beyond the input file. This is critical for correct incremental builds.

#### Return Value Format

```python
def __call__(self, path: Path, output_paths: list[Path]) -> None | tuple:
    # Option 1: Return None (default custody tracking)
    # Anchovy assumes: input file -> output files
    process_file(path, output_paths)
    return None

    # Option 2: Return explicit custody tuple
    # You specify exactly which files are sources and outputs
    sources = [path, dependency1, dependency2]
    return (sources, output_paths)
```

#### When to Use Explicit Custody

**Use Case 1: Template Dependencies**

When a file depends on multiple source files (like templates with includes):

```python
class JinjaStep(Step):
    def __call__(self, path: Path, output_paths: list[Path]) -> tuple:
        # Main template
        template = load_template('base.html')

        # Find all included/extended templates
        includes = find_template_dependencies('base.html')
        # e.g., ['_header.html', '_footer.html', '_nav.html']

        # Render output
        render(path, template, output_paths[0])

        # Track ALL templates as sources
        # If any template changes, this file will be regenerated
        all_templates = [Path('templates/base.html')] + [
            Path(f'templates/{inc}') for inc in includes
        ]
        return ([path] + all_templates, output_paths)
```

**Real example from `JinjaMarkdownStep`:**
```python
def __call__(self, path: Path, output_paths: list[Path]):
    # Render markdown using template
    template_path, template_deps = self.render_template(...)

    # Track markdown file, main template, AND all includes/extends
    sources = [path, Path(template_path)] + template_deps
    return sources, output_paths
```

**Use Case 2: Config-Based Dependencies**

When a file references other files via configuration:

```python
class CombineStep(Step):
    def __call__(self, path: Path, output_paths: list[Path]) -> tuple:
        # path is a config file listing files to combine
        config = parse_config(path)  # e.g., ['a.js', 'b.js', 'c.js']

        sources = [path]  # Start with config file

        # Read and combine all referenced files
        combined = []
        for filename in config['files']:
            file_path = path.parent / filename
            sources.append(file_path)  # Track as dependency
            combined.append(file_path.read_text())

        # Write combined output
        output_paths[0].write_text('\n'.join(combined))

        # Return all source files
        # If any source changes, output will be regenerated
        return (sources, output_paths)
```

**Real example from `ResourcePackerStep`:**
```python
def __call__(self, path: Path, output_paths: list[Path]) -> tuple:
    # Read list of files from config
    files_to_pack = read_file_list(path)

    # Pack all files together
    packed_content = pack_files(files_to_pack)
    output_paths[0].write_text(packed_content)

    # Track config + all packed files as sources
    return ([path] + files_to_pack, output_paths)
```

**Use Case 3: Custom Custody Entries**

When dependencies aren't files (like URLs, git commits, env vars):

```python
from anchovy import CustodyEntry

class APIFetchStep(Step):
    def __call__(self, path: Path, output_paths: list[Path]) -> tuple:
        config = parse_config(path)
        url = config['api_url']

        # Fetch from API
        response = fetch_with_etag(url)
        output_paths[0].write_text(response.content)

        # Create custom custody entry tracking ETag
        api_entry = CustodyEntry(
            entry_type='api_fetch',
            key=url,
            meta={'etag': response.headers.get('ETag')}
        )

        # Track config file AND API state
        return ([path, api_entry], output_paths)
```

See [Custody and Rebuilds](./custody-and-rebuilds.md) for more on custom entries.

#### What Happens Without Explicit Custody?

If you return `None`, Anchovy assumes:
- **Source**: Just the input file (`path`)
- **Outputs**: All files in `output_paths`

This is fine for simple transformations, but **fails to track hidden dependencies**:

```python
# BAD: Template changes won't trigger rebuild
class NaiveJinjaStep(Step):
    def __call__(self, path: Path, output_paths: list[Path]):
        template = load_template('base.html')  # NOT tracked!
        render(path, template, output_paths[0])
        # Returns None - only tracks input markdown file

# GOOD: Template changes trigger rebuild
class GoodJinjaStep(Step):
    def __call__(self, path: Path, output_paths: list[Path]) -> tuple:
        template_path = Path('templates/base.html')
        template = load_template(template_path)
        render(path, template, output_paths[0])
        # Explicitly track both files
        return ([path, template_path], output_paths)
```

#### Best Practices

1. **Always track dependencies**: If your Step reads other files, track them
2. **Track all levels**: Include transitive dependencies (templates of templates)
3. **Test rebuilds**: Change a dependency and verify rebuild triggers
4. **Document sources**: Comment what each source represents

```python
def __call__(self, path: Path, output_paths: list[Path]) -> tuple:
    sources = [
        path,                    # Main input file
        template_path,           # Jinja template
        config_path,             # Site configuration
    ] + include_paths           # All template includes

    return (sources, output_paths)
```

## Matchers

Matchers determine which files a Rule applies to. They can return any type, which is passed to the PathCalc.

### Matcher Interface

```python
from anchovy import Matcher
from typing import TypeVar

T = TypeVar('T')

class MyMatcher(Matcher[T]):
    def __call__(self, context: Context, path: Path) -> T | None:
        """
        Check if this matcher applies to the given path.

        Returns:
            Any truthy value if it matches, None otherwise.
            The return value is passed to PathCalc.
        """
        if path.suffix == '.md':
            return path.stem  # Return the filename without extension
        return None
```

### REMatcher

The built-in `REMatcher` uses regular expressions:

```python
from anchovy import REMatcher
import re

# Basic pattern matching
REMatcher(r'.*\.md')

# Case-insensitive
REMatcher(r'.*\.MD', flags=re.IGNORECASE)

# Match relative to a context directory
REMatcher(r'(.*/)*static/.*', parent_dir='input_dir')
REMatcher(r'.*\.html', parent_dir='working_dir')

# Capture groups for use in PathCalc
REMatcher(r'(?P<name>.*)\.(?P<ext>[^.]+)')
```

The `parent_dir` parameter makes the path relative to a context directory before matching. This is crucial for distinguishing files from different sources:

```python
# Only match .html files in input_dir (not working_dir)
REMatcher(r'.*\.html', parent_dir='input_dir')

# Only match .html files in working_dir
REMatcher(r'.*\.html', parent_dir='working_dir')
```

### Matcher Composition

Matchers can be combined with `|` (OR) and `&` (AND):

```python
# Match markdown OR text files
REMatcher(r'.*\.md') | REMatcher(r'.*\.txt')

# Match files in docs/ AND ending in .md
REMatcher(r'docs/.*') & REMatcher(r'.*\.md')

# Complex combinations
(
    (REMatcher(r'.*\.md') | REMatcher(r'.*\.markdown'))
    & REMatcher(r'(?!.*\.draft\.)')
)
```

### Custom Matchers

Create custom matchers for complex logic:

```python
class FileSizeMatcher(Matcher[int]):
    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes

    def __call__(self, context: Context, path: Path) -> int | None:
        size = path.stat().st_size
        if size <= self.max_bytes:
            return size
        return None

# Use it
Rule(
    FileSizeMatcher(1024 * 1024),  # Files under 1MB
    OutputDirPathCalc(),
    DirectCopyStep()
)
```

## PathCalcs

PathCalcs calculate where output files should be written based on input paths and matcher results.

### PathCalc Interface

```python
from anchovy import PathCalc
from typing import TypeVar

T = TypeVar('T')

class MyPathCalc(PathCalc[T]):
    def __call__(self, context: Context, path: Path, match: T) -> Path:
        """
        Calculate the output path for a matched file.

        Args:
            context: The build context
            path: Input file path
            match: Return value from the Matcher

        Returns:
            Output path
        """
        output_dir = context['output_dir']
        return output_dir / path.name
```

### Built-in PathCalcs

```python
from anchovy import (
    OutputDirPathCalc,
    WorkingDirPathCalc,
    DirPathCalc,
    WebIndexPathCalc,
)

# Place in output_dir with same name
OutputDirPathCalc()

# Change extension
OutputDirPathCalc('.html')
OutputDirPathCalc('.min.css')

# Transform path with function
OutputDirPathCalc(transform=lambda p: p.with_stem(p.stem + '.processed'))

# Place in working_dir (for intermediate files)
WorkingDirPathCalc()
WorkingDirPathCalc('.tmp.html')

# Place in custom directory
DirPathCalc(dest=Path('custom/dir'))
DirPathCalc(dest='output_dir', ext='.html')  # Can reference context dirs

# Web-friendly URLs (a/b.html -> a/b/index.html)
WebIndexPathCalc()
WebIndexPathCalc(index_base='default')
```

### Path Transformations

PathCalcs preserve directory structure by default:

```
Input:  site/blog/2024/post.md
Output: build/blog/2024/post.html  (with OutputDirPathCalc('.html'))
```

Transform functions can modify this:

```python
# Flatten directory structure
OutputDirPathCalc(transform=lambda p: p.name)

# Add date prefix
from datetime import datetime
OutputDirPathCalc(transform=lambda p: f"{datetime.now():%Y%m%d}-{p.name}")

# Complex transformations
def my_transform(path: Path) -> Path:
    # Remove 'drafts' from path
    parts = [p for p in path.parts if p != 'drafts']
    return Path(*parts)

OutputDirPathCalc(transform=my_transform)
```

### Using Matcher Results

PathCalcs receive the Matcher's return value:

```python
# Matcher with named groups
matcher = REMatcher(r'(?P<stem>.*)\.(?P<ext>tar\.gz|[^.]+)')

# PathCalc using the match groups
class SmartExtPathCalc(PathCalc):
    def __init__(self, new_ext: str):
        self.new_ext = new_ext

    def __call__(self, context, path, match):
        output_dir = context['output_dir']

        # Use captured groups from regex
        stem = match.group('stem')
        old_ext = match.group('ext')

        # Preserve path structure but change extension
        relative = path.relative_to(context['input_dir'])
        return output_dir / relative.parent / f"{stem}{self.new_ext}"
```

The built-in `DirPathCalc` uses 'stem' and 'ext' groups automatically:

```python
# This matcher captures stem and ext
REMatcher(r'(?P<stem>.*)\.(?P<ext>tar\.gz|[^.]+)')

# DirPathCalc uses them to handle multi-part extensions
OutputDirPathCalc('.tar.bz2')  # Properly handles .tar.gz -> .tar.bz2
```

## Build Settings

Build settings configure the Context and control build behavior.

### InputBuildSettings

User-provided configuration (all fields optional except input_dir):

```python
from anchovy import InputBuildSettings
from pathlib import Path

SETTINGS = InputBuildSettings(
    input_dir=Path('site'),                  # Required
    output_dir=Path('build'),                # Default: input_dir / 'build'
    working_dir=Path('working'),             # Default: temp directory
    custody_cache=Path('build-cache.json'),  # Default: None (disabled)
    purge_dirs=False,                        # Default: False
)
```

### BuildSettings

Fully resolved settings (all fields required):

```python
from anchovy import BuildSettings

# Usually created by Context or CLI
settings = BuildSettings(
    input_dir=Path('site'),
    output_dir=Path('build'),
    working_dir=Path('/tmp/anchovy-xyz'),  # Never None
    custody_cache=Path('build-cache.json'),
    purge_dirs=False,
)
```

### CLI Override

Command-line arguments override config file settings:

```bash
# Override in config
anchovy config.py -i ./content -o ./public -w ./tmp

# Purge directories before building
anchovy config.py --purge

# Disable custody cache
anchovy config.py --custody-cache=None
```

## Workflow

Understanding the complete build workflow helps you design effective pipelines.

### Complete Build Flow

```
1. Load Configuration
   ├─ Parse config file/module
   ├─ Extract SETTINGS and RULES
   └─ Apply CLI overrides

2. Create Context
   ├─ Bind all Steps
   ├─ Check dependencies
   ├─ Load custody cache
   └─ Validate directories

3. Run Pre-Processing
   ├─ Purge directories (if enabled)
   └─ Create directory structure

4. Process Files
   ├─ Discover input files
   ├─ For each file:
   │  ├─ Match against Rules (in order)
   │  ├─ Calculate output paths
   │  ├─ Check staleness (custody)
   │  ├─ Execute Step (if stale)
   │  └─ Track in custody graph
   └─ Collect intermediate files

5. Process Intermediate Files
   ├─ Find files in working_dir
   ├─ Re-process through Rules
   └─ Repeat until no new files

6. Post-Processing
   ├─ Remove orphaned outputs
   ├─ Save custody cache
   └─ Report results
```

### File Discovery

Input files are discovered recursively:

```python
# Context finds all files in input_dir
for input_path in context.find_inputs(context['input_dir']):
    # Process each file...
```

You can customize discovery by subclassing Context:

```python
from anchovy import Context
import time

class RecentFilesContext(Context):
    def find_inputs(self, path: Path):
        """Only process files modified in the last hour."""
        hour_ago = time.time() - 3600
        for candidate in super().find_inputs(path):
            if candidate.stat().st_mtime > hour_ago:
                yield candidate
```

### Rule Matching Order

Rules are evaluated sequentially until one matches:

```python
RULES = [
    # Specific rules first
    Rule(REMatcher(r'special/.*\.md'), ...),

    # More general rules after
    Rule(REMatcher(r'.*\.md'), ...),

    # Catch-all at the end
    Rule(REMatcher(r'.*'), ...),
]
```

Once a file matches a rule:
- If `path_calc` is `None`: Stop processing
- If `path_calc` list ends with `None`: Process with Step, then stop
- Otherwise: Process with Step, file may be re-processed later

### Intermediate File Processing

Files in `working_dir` are automatically re-processed:

```python
# Multi-stage pipeline example
RULES = [
    # Stage 1: Markdown -> HTML (working_dir)
    Rule(
        REMatcher(r'.*\.md', parent_dir='input_dir'),
        WorkingDirPathCalc('.html'),
        JinjaMarkdownStep()
    ),

    # Stage 2: HTML -> Minified (output_dir, then stop)
    Rule(
        REMatcher(r'.*\.html', parent_dir='working_dir'),
        [OutputDirPathCalc(), None],
        HTMLMinifierStep()
    ),
]
```

This enables powerful multi-step transformations without manually coordinating steps.

## Best Practices

### Rule Organization

```python
RULES = [
    # 1. Exclusions first
    Rule(REMatcher(r'(.*/)*\..*'), None),  # Ignore dotfiles
    Rule(REMatcher(r'.*\.draft\.md'), None),  # Ignore drafts

    # 2. Special cases
    Rule(REMatcher(r'gallery/.*\.jpg'), ..., IMThumbnailStep()),

    # 3. General processing
    Rule(REMatcher(r'.*\.md'), ..., JinjaMarkdownStep()),
    Rule(REMatcher(r'.*\.css'), ..., CSSMinifierStep()),

    # 4. Fallback
    Rule(REMatcher(r'.*'), OutputDirPathCalc(), DirectCopyStep()),
]
```

### Step Configuration

Keep Step configuration in the Rule definition:

```python
# Good - configuration is visible in Rules
Rule(
    REMatcher(r'.*\.md'),
    OutputDirPathCalc('.html'),
    JinjaMarkdownStep(
        frontmatter_parser='toml',
        enable_toc_anchors=True,
        enable_syntax_highlight=True
    )
)

# Avoid - configuration hidden in Step instance
markdown_step = JinjaMarkdownStep(...)  # Configured elsewhere
Rule(REMatcher(r'.*\.md'), OutputDirPathCalc('.html'), markdown_step)
```

### Directory Management

Use `parent_dir` to distinguish file sources:

```python
# Good - explicit about where files come from
Rule(REMatcher(r'.*\.html', parent_dir='input_dir'), ...)
Rule(REMatcher(r'.*\.html', parent_dir='working_dir'), ...)

# Risky - may match files from both sources
Rule(REMatcher(r'.*\.html'), ...)
```

## Next Steps

- [Steps Reference](./steps-reference.md) - Complete guide to all built-in Steps
- [Matchers and PathCalcs](./matchers-pathcalcs.md) - Deep dive into path handling
- [Custody and Rebuilds](./custody-and-rebuilds.md) - Smart caching system
- [Advanced Usage](./advanced-usage.md) - Custom components and programmatic usage
