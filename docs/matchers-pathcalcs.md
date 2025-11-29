# Matchers and PathCalcs

This guide provides an in-depth look at Matchers and PathCalcs, the components that control which files get processed and where outputs are written.

## Table of Contents

- [Matchers](#matchers)
  - [REMatcher](#rematcher)
  - [Matcher Composition](#matcher-composition)
  - [Custom Matchers](#custom-matchers)
- [PathCalcs](#pathcalcs)
  - [OutputDirPathCalc](#outputdirpathcalc)
  - [WorkingDirPathCalc](#workingdirpathcalc)
  - [DirPathCalc](#dirpathcalc)
  - [WebIndexPathCalc](#webindexpathcalc)
  - [Custom PathCalcs](#custom-pathcalcs)
- [Advanced Patterns](#advanced-patterns)

## Matchers

Matchers determine which files a Rule should process. They return a value (of any type) if the file matches, or `None` if it doesn't. The returned value is passed to the PathCalc.

### Basic Matcher Interface

```python
from anchovy import Matcher
from pathlib import Path
from typing import TypeVar

T = TypeVar('T')

class MyMatcher(Matcher[T]):
    def __call__(self, context: Context, path: Path) -> T | None:
        """
        Check if path matches.

        Args:
            context: The build context
            path: File path to check

        Returns:
            Any truthy value if match, None otherwise
        """
        if self.matches(path):
            return self.extract_info(path)
        return None
```

### REMatcher

The built-in `REMatcher` uses regular expressions for pattern matching.

#### Basic Usage

```python
from anchovy import REMatcher

# Match by extension
REMatcher(r'.*\.md')
REMatcher(r'.*\.html')

# Match by path pattern
REMatcher(r'blog/.*\.md')
REMatcher(r'static/images/.*\.(jpg|png|gif)')

# Match specific files
REMatcher(r'.*/index\.html')
```

#### Regular Expression Flags

```python
import re

# Case-insensitive matching
REMatcher(r'.*\.MD', flags=re.IGNORECASE)

# Dot matches newline (for multi-line content)
REMatcher(r'.*\.txt', flags=re.DOTALL)

# Verbose regex with comments
REMatcher(r'''
    .*          # Any path
    \.          # Literal dot
    (jpg|png)   # Extensions
''', flags=re.VERBOSE)
```

#### Parent Directory Matching

The `parent_dir` parameter makes paths relative before matching:

```python
# Match .html files only in input_dir
REMatcher(r'.*\.html', parent_dir='input_dir')

# Match .html files only in working_dir
REMatcher(r'.*\.html', parent_dir='working_dir')

# Match files in static/ subdirectory of input_dir
REMatcher(r'static/.*', parent_dir='input_dir')
```

**Why is this important?** Without `parent_dir`, you might match files from different sources:

```python
# BAD: Matches .html from both input_dir and working_dir
Rule(REMatcher(r'.*\.html'), ..., HTMLMinifierStep())

# GOOD: Only matches .html from working_dir (after markdown rendering)
Rule(REMatcher(r'.*\.html', parent_dir='working_dir'), ..., HTMLMinifierStep())
```

#### Named Capture Groups

Named groups can be used by PathCalcs:

```python
# Capture stem and extension separately
REMatcher(r'(?P<stem>.*)\.(?P<ext>[^.]+)')

# Capture complex extensions like .tar.gz
REMatcher(r'(?P<stem>.*)\.(?P<ext>tar\.gz|tar\.bz2|[^.]+)')

# Capture date from filename
REMatcher(r'(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})-(?P<title>.*)\.md')
```

The `DirPathCalc` uses `stem` and `ext` groups automatically:

```python
# This matcher provides stem and ext groups
matcher = REMatcher(r'(?P<stem>.*)\.(?P<ext>tar\.gz|[^.]+)')

# DirPathCalc uses them to handle complex extensions
path_calc = OutputDirPathCalc('.tar.bz2')

# Example: archive.tar.gz -> archive.tar.bz2
```

#### Complete Examples

```python
# Match all markdown files
Rule(
    REMatcher(r'.*\.md'),
    OutputDirPathCalc('.html'),
    JinjaMarkdownStep()
)

# Match only blog posts
Rule(
    REMatcher(r'blog/\d{4}/\d{2}/.*\.md'),
    OutputDirPathCalc('.html'),
    JinjaMarkdownStep()
)

# Match images in specific directory
Rule(
    REMatcher(r'gallery/.*\.(jpg|jpeg|png)', flags=re.IGNORECASE),
    OutputDirPathCalc('.webp'),
    PillowStep()
)

# Match files but not in drafts/
Rule(
    REMatcher(r'(?!.*drafts/).*\.md'),  # Negative lookahead
    OutputDirPathCalc('.html'),
    JinjaMarkdownStep()
)
```

### Matcher Composition

Matchers can be combined with `|` (OR) and `&` (AND) operators.

#### OR Composition (`|`)

Matches if either matcher succeeds:

```python
# Match markdown or text files
REMatcher(r'.*\.md') | REMatcher(r'.*\.txt')

# Match multiple image formats
(
    REMatcher(r'.*\.jpg')
    | REMatcher(r'.*\.png')
    | REMatcher(r'.*\.gif')
)

# Shorter alternative using regex
REMatcher(r'.*\.(jpg|png|gif)')
```

#### AND Composition (`&`)

Matches only if both matchers succeed:

```python
# Match .md files in blog/ directory
REMatcher(r'.*\.md') & REMatcher(r'blog/.*')

# Match large files (requires custom matcher)
REMatcher(r'.*\.jpg') & FileSizeMatcher(min_bytes=1024*1024)
```

#### Complex Compositions

```python
# Blog posts or pages, but not drafts
(
    (REMatcher(r'blog/.*\.md') | REMatcher(r'pages/.*\.md'))
    & ~REMatcher(r'.*\.draft\.md')  # NOT draft
)

# Images in gallery, but not thumbnails
REMatcher(r'gallery/.*\.(jpg|png)') & ~REMatcher(r'.*\.thumb\.')
```

#### Practical Examples

```python
RULES = [
    # Ignore drafts and dotfiles
    Rule(
        REMatcher(r'.*\.draft\.') | REMatcher(r'(.*/)*\..*'),
        None
    ),

    # Process markdown from multiple sources
    Rule(
        REMatcher(r'blog/.*\.md') | REMatcher(r'docs/.*\.md'),
        OutputDirPathCalc('.html'),
        JinjaMarkdownStep()
    ),

    # Only process large images
    Rule(
        REMatcher(r'.*\.jpg') & FileSizeMatcher(min_bytes=500*1024),
        OutputDirPathCalc(),
        CWebPStep(quality=85)
    ),
]
```

### Custom Matchers

Create custom matchers for sophisticated logic.

#### File Size Matcher

```python
from anchovy import Matcher
from pathlib import Path

class FileSizeMatcher(Matcher[int]):
    """Matches files based on size."""

    def __init__(self, min_bytes: int = 0, max_bytes: int | None = None):
        self.min_bytes = min_bytes
        self.max_bytes = max_bytes

    def __call__(self, context: Context, path: Path) -> int | None:
        size = path.stat().st_size

        if size < self.min_bytes:
            return None
        if self.max_bytes is not None and size > self.max_bytes:
            return None

        return size  # Return size for use in PathCalc

# Usage
Rule(
    FileSizeMatcher(max_bytes=1024*1024),  # Files under 1MB
    OutputDirPathCalc(),
    DirectCopyStep()
)
```

#### Modified Time Matcher

```python
import time
from anchovy import Matcher

class RecentFileMatcher(Matcher[float]):
    """Matches files modified within a time window."""

    def __init__(self, hours: int = 24):
        self.cutoff = time.time() - (hours * 3600)

    def __call__(self, context: Context, path: Path) -> float | None:
        mtime = path.stat().st_mtime

        if mtime > self.cutoff:
            return mtime
        return None

# Usage - only process recently modified files
Rule(
    RecentFileMatcher(hours=1) & REMatcher(r'.*\.md'),
    OutputDirPathCalc('.html'),
    JinjaMarkdownStep()
)
```

#### Content-Based Matcher

```python
from anchovy import Matcher

class FrontmatterMatcher(Matcher[dict]):
    """Matches files with specific frontmatter."""

    def __init__(self, required_key: str, required_value: str | None = None):
        self.required_key = required_key
        self.required_value = required_value

    def __call__(self, context: Context, path: Path) -> dict | None:
        content = path.read_text()

        # Parse frontmatter (simplified)
        if not content.startswith('---'):
            return None

        frontmatter = self.parse_frontmatter(content)

        if self.required_key not in frontmatter:
            return None

        if self.required_value is not None:
            if frontmatter[self.required_key] != self.required_value:
                return None

        return frontmatter

    def parse_frontmatter(self, content: str) -> dict:
        # Simplified parser
        lines = content.split('---')[1].strip().split('\n')
        return dict(line.split(': ', 1) for line in lines if ': ' in line)

# Usage - only process published posts
Rule(
    FrontmatterMatcher('status', 'published'),
    OutputDirPathCalc('.html'),
    JinjaMarkdownStep()
)
```

#### Extension Matcher with Groups

```python
from anchovy import Matcher
import re

class ExtensionMatcher(Matcher[re.Match]):
    """Matches files by extension with named groups."""

    def __init__(self, *extensions: str):
        pattern = r'(?P<stem>.*)\.(?P<ext>' + '|'.join(extensions) + r')$'
        self.regex = re.compile(pattern)

    def __call__(self, context: Context, path: Path) -> re.Match | None:
        return self.regex.match(path.name)

# Usage
Rule(
    ExtensionMatcher('jpg', 'jpeg', 'png'),
    OutputDirPathCalc('.webp'),
    PillowStep()
)
```

## PathCalcs

PathCalcs determine where output files should be written. They receive the matched file path and the Matcher's return value.

### Basic PathCalc Interface

```python
from anchovy import PathCalc
from typing import TypeVar

T = TypeVar('T')

class MyPathCalc(PathCalc[T]):
    def __call__(self, context: Context, path: Path, match: T) -> Path:
        """
        Calculate output path.

        Args:
            context: Build context
            path: Input file path
            match: Value returned by Matcher

        Returns:
            Output path
        """
        output_dir = context['output_dir']
        # Calculate and return output path
        return output_dir / 'output.txt'
```

### OutputDirPathCalc

Places files in the output directory, preserving relative path structure.

#### Basic Usage

```python
from anchovy import OutputDirPathCalc

# Same name and structure
OutputDirPathCalc()

# Change extension
OutputDirPathCalc('.html')
OutputDirPathCalc('.min.css')
OutputDirPathCalc('.webp')
```

#### With Transform Function

```python
# Flatten directory structure
OutputDirPathCalc(transform=lambda p: p.name)

# Add prefix to filename
OutputDirPathCalc(transform=lambda p: p.with_stem(f'processed-{p.stem}'))

# Change directory structure
def reorganize(path: Path) -> Path:
    # Move all files to 'assets' subdirectory
    return Path('assets') / path.name

OutputDirPathCalc(transform=reorganize)
```

#### Examples

```python
# Simple copy with structure preservation
# site/blog/post.md -> build/blog/post.md
Rule(
    REMatcher(r'.*\.md'),
    OutputDirPathCalc(),
    DirectCopyStep()
)

# Extension change
# site/blog/post.md -> build/blog/post.html
Rule(
    REMatcher(r'.*\.md'),
    OutputDirPathCalc('.html'),
    JinjaMarkdownStep()
)

# Flatten to single directory
# site/blog/2024/post.md -> build/post.html
Rule(
    REMatcher(r'.*\.md'),
    OutputDirPathCalc('.html', transform=lambda p: p.name),
    JinjaMarkdownStep()
)
```

### WorkingDirPathCalc

Places files in the working directory for intermediate processing.

```python
from anchovy import WorkingDirPathCalc

# Same name
WorkingDirPathCalc()

# Change extension
WorkingDirPathCalc('.tmp.html')
WorkingDirPathCalc('.processed')
```

#### Multi-Stage Processing

```python
RULES = [
    # Stage 1: Markdown -> HTML (to working_dir)
    Rule(
        REMatcher(r'.*\.md', parent_dir='input_dir'),
        WorkingDirPathCalc('.html'),
        JinjaMarkdownStep()
    ),

    # Stage 2: HTML -> Minified (to output_dir, stop processing)
    Rule(
        REMatcher(r'.*\.html', parent_dir='working_dir'),
        [OutputDirPathCalc(), None],
        HTMLMinifierStep()
    ),
]
```

### DirPathCalc

Generic path calculator for any destination directory.

```python
from anchovy import DirPathCalc
from pathlib import Path

# To specific directory
DirPathCalc(dest=Path('custom/output'))

# To context directory
DirPathCalc(dest='output_dir')
DirPathCalc(dest='working_dir')

# With extension change
DirPathCalc(dest='output_dir', ext='.html')

# With transform
DirPathCalc(
    dest='output_dir',
    ext='.html',
    transform=lambda p: p.with_stem(f'{p.stem}-processed')
)
```

#### Examples

```python
# Output to custom location
Rule(
    REMatcher(r'.*\.md'),
    DirPathCalc(dest=Path('docs/output'), ext='.html'),
    JinjaMarkdownStep()
)

# Multiple output destinations
Rule(
    REMatcher(r'.*\.jpg'),
    [
        DirPathCalc(dest='output_dir'),           # Full size
        DirPathCalc(dest='output_dir/thumbs'),    # Thumbnail copy
    ],
    PillowStep(thumbnail=(300, 300))
)
```

### WebIndexPathCalc

Converts file paths to web-friendly index structure.

```python
from anchovy import WebIndexPathCalc

# Default: index.html
WebIndexPathCalc()

# Custom index base
WebIndexPathCalc(index_base='default')
WebIndexPathCalc(index_base='home')
```

#### Path Transformations

```
Input               Output
------------------  ------------------------
about.html          about/index.html
blog/post.html      blog/post/index.html
index.html          index.html (unchanged)
feed.xml            feed.xml (non-.html unchanged)
```

#### Examples

```python
# Clean URLs without .html extension
Rule(
    REMatcher(r'.*\.md'),
    WebIndexPathCalc(),
    JinjaMarkdownStep()
)

# Custom index
Rule(
    REMatcher(r'.*\.md'),
    WebIndexPathCalc(index_base='default'),
    JinjaMarkdownStep()
)
```

**URL Structure:**

```
site/about.md -> build/about/index.html
URL: https://example.com/about/

site/blog/post.md -> build/blog/post/index.html
URL: https://example.com/blog/post/
```

### Custom PathCalcs

Create custom PathCalcs for specialized output path logic.

#### Date-Based Organization

```python
from anchovy import PathCalc
from datetime import datetime

class DatePathCalc(PathCalc):
    """Organize outputs by date."""

    def __init__(self, ext: str | None = None):
        self.ext = ext

    def __call__(self, context: Context, path: Path, match) -> Path:
        output_dir = context['output_dir']

        # Get current date
        date = datetime.now()
        year = date.strftime('%Y')
        month = date.strftime('%m')

        # Build path: output/2024/01/filename.html
        filename = path.stem + (self.ext or path.suffix)
        return output_dir / year / month / filename

# Usage
Rule(
    REMatcher(r'.*\.md'),
    DatePathCalc(ext='.html'),
    JinjaMarkdownStep()
)
```

#### Metadata-Based Organization

```python
from anchovy import PathCalc
import re

class CategoryPathCalc(PathCalc):
    """Organize outputs by category from filename."""

    def __init__(self, ext: str = '.html'):
        self.ext = ext
        self.pattern = re.compile(r'(?P<category>[^-]+)-(?P<name>.*)')

    def __call__(self, context: Context, path: Path, match) -> Path:
        output_dir = context['output_dir']

        # Extract category from filename: "tech-my-post.md"
        filename_match = self.pattern.match(path.stem)

        if filename_match:
            category = filename_match.group('category')
            name = filename_match.group('name')
            return output_dir / category / (name + self.ext)

        # Fallback to uncategorized
        return output_dir / 'uncategorized' / (path.stem + self.ext)

# Usage: "tech-article.md" -> "build/tech/article.html"
Rule(
    REMatcher(r'.*\.md'),
    CategoryPathCalc(),
    JinjaMarkdownStep()
)
```

#### Hash-Based Organization

```python
from anchovy import PathCalc
import hashlib

class HashPathCalc(PathCalc):
    """Organize by content hash for cache busting."""

    def __init__(self, ext: str | None = None):
        self.ext = ext

    def __call__(self, context: Context, path: Path, match) -> Path:
        output_dir = context['output_dir']

        # Calculate hash
        content = path.read_bytes()
        hash_hex = hashlib.sha256(content).hexdigest()[:8]

        # Include hash in filename
        ext = self.ext or path.suffix
        filename = f'{path.stem}-{hash_hex}{ext}'

        return output_dir / filename

# Usage: "script.js" -> "build/script-a1b2c3d4.js"
Rule(
    REMatcher(r'.*\.js'),
    HashPathCalc(),
    DirectCopyStep()
)
```

#### Using Matcher Results

```python
from anchovy import PathCalc
import re

class BlogPathCalc(PathCalc[re.Match]):
    """Use captured groups from matcher."""

    def __call__(self, context: Context, path: Path, match: re.Match) -> Path:
        output_dir = context['output_dir']

        # Extract date from filename via matcher groups
        year = match.group('year')
        month = match.group('month')
        day = match.group('day')
        title = match.group('title')

        # Build path: output/2024/01/15/my-post/index.html
        return output_dir / year / month / day / title / 'index.html'

# Matcher with named groups
matcher = REMatcher(r'(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})-(?P<title>.*)\.md')

# PathCalc uses those groups
Rule(
    matcher,
    BlogPathCalc(),
    JinjaMarkdownStep()
)
```

## Advanced Patterns

### Multiple Output Paths

A single input can produce multiple outputs:

```python
# Create both full-size and thumbnail
Rule(
    REMatcher(r'gallery/.*\.jpg'),
    [
        OutputDirPathCalc(),              # build/gallery/photo.jpg
        OutputDirPathCalc('.thumb.jpg'),  # build/gallery/photo.thumb.jpg
    ],
    PillowStep(thumbnail=(300, 300))
)

# Create multiple formats
Rule(
    REMatcher(r'.*\.jpg'),
    [
        OutputDirPathCalc(),        # build/photo.jpg (original)
        OutputDirPathCalc('.webp'), # build/photo.webp
        OutputDirPathCalc('.avif'), # build/photo.avif
    ],
    ImageConverterStep()
)
```

### Conditional PathCalcs

```python
def conditional_path(context: Context, path: Path, match) -> Path:
    """Choose destination based on file properties."""
    output_dir = context['output_dir']

    # Large files go to separate directory
    if path.stat().st_size > 1024 * 1024:
        return output_dir / 'large' / path.name

    return output_dir / path.name

Rule(
    REMatcher(r'.*\.jpg'),
    conditional_path,  # Can use function directly
    DirectCopyStep()
)
```

### Halting Patterns

```python
# Ignore files (no path_calc)
Rule(REMatcher(r'.*\.draft\.md'), None)

# Process once, then stop (None at end of list)
Rule(
    REMatcher(r'.*\.md'),
    [OutputDirPathCalc('.html'), None],
    JinjaMarkdownStep()
)

# Continue processing (file goes to working_dir)
Rule(
    REMatcher(r'.*\.md'),
    WorkingDirPathCalc('.html'),
    JinjaMarkdownStep()
)
```

### Complex Matcher + PathCalc Combinations

```python
# Archive extraction with smart output paths
Rule(
    REMatcher(r'archives/(?P<name>.*)\.(?P<ext>zip|tar\.gz)'),
    DirPathCalc(
        dest='output_dir',
        transform=lambda p: Path('extracted') / p.stem
    ),
    UnpackArchiveStep()
)

# Date-organized blog with categories
blog_matcher = REMatcher(
    r'blog/(?P<year>\d{4})/(?P<category>[^/]+)/(?P<title>.*)\.md'
)

class BlogOutputCalc(PathCalc):
    def __call__(self, context, path, match):
        output_dir = context['output_dir']
        year = match.group('year')
        category = match.group('category')
        title = match.group('title')
        return output_dir / year / category / title / 'index.html'

Rule(blog_matcher, BlogOutputCalc(), JinjaMarkdownStep())
```

### Directory Structure Preservation

```python
# Preserve structure from input_dir
# site/blog/2024/post.md -> build/blog/2024/post.html
Rule(
    REMatcher(r'.*\.md'),
    OutputDirPathCalc('.html'),  # Preserves structure by default
    JinjaMarkdownStep()
)

# Preserve structure but change root
# site/blog/post.md -> build/articles/blog/post.html
def reroot(path: Path) -> Path:
    return Path('articles') / path

Rule(
    REMatcher(r'blog/.*\.md'),
    OutputDirPathCalc('.html', transform=reroot),
    JinjaMarkdownStep()
)
```

### Extension Handling

```python
# Simple extension
OutputDirPathCalc('.html')  # .md -> .html

# Multi-part extension
OutputDirPathCalc('.min.css')  # .css -> .min.css

# Complex extension with regex groups
matcher = REMatcher(r'(?P<stem>.*)\.(?P<ext>tar\.gz|[^.]+)')
OutputDirPathCalc('.tar.bz2')  # .tar.gz -> .tar.bz2

# Remove extension
OutputDirPathCalc(transform=lambda p: p.with_suffix(''))

# Double extension
OutputDirPathCalc(transform=lambda p: p.with_suffix(p.suffix + '.bak'))
```

## Best Practices

### Use parent_dir for Clarity

```python
# Good - explicit about source
Rule(REMatcher(r'.*\.html', parent_dir='input_dir'), ...)
Rule(REMatcher(r'.*\.html', parent_dir='working_dir'), ...)

# Risky - ambiguous
Rule(REMatcher(r'.*\.html'), ...)
```

### Order Rules Carefully

```python
RULES = [
    # Specific before general
    Rule(REMatcher(r'special/.*\.md'), ...),
    Rule(REMatcher(r'.*\.md'), ...),

    # Exclusions first
    Rule(REMatcher(r'.*\.draft\.md'), None),
    Rule(REMatcher(r'.*\.md'), ...),
]
```

### Keep PathCalcs Simple

```python
# Good - simple and clear
OutputDirPathCalc('.html')

# Avoid - overly complex
OutputDirPathCalc(transform=lambda p: Path(
    'output' if p.stat().st_size > 1000 else 'small'
) / p.parent.name / (p.stem + '-processed' + '.html'))

# Better - extract to named function or custom PathCalc
def organize_by_size(path: Path) -> Path:
    size_dir = 'large' if path.stat().st_size > 1024*1024 else 'small'
    return Path(size_dir) / path.with_suffix('.html')

OutputDirPathCalc(transform=organize_by_size)
```

### Test Matchers and PathCalcs

```python
from pathlib import Path
from anchovy import Context, BuildSettings, REMatcher, OutputDirPathCalc

# Create test context
settings = BuildSettings(
    input_dir=Path('test/input'),
    output_dir=Path('test/output'),
    working_dir=Path('test/working'),
    custody_cache=None,
    purge_dirs=False
)
context = Context(settings, rules=[])

# Test matcher
matcher = REMatcher(r'blog/.*\.md')
test_path = Path('test/input/blog/post.md')
result = matcher(context, test_path)
assert result is not None, "Should match blog posts"

# Test path calc
path_calc = OutputDirPathCalc('.html')
output = path_calc(context, test_path, result)
assert output == Path('test/output/blog/post.html')
```

## Next Steps

- [Custody and Rebuilds](./custody-and-rebuilds.md) - Smart caching system
- [Advanced Usage](./advanced-usage.md) - Custom components and programmatic usage
- [API Reference](./api-reference.md) - Complete API documentation
