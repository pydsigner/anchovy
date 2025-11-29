# Advanced Usage

This guide covers advanced Anchovy features including programmatic usage, custom components, integration with other tools, and optimization techniques.

## Table of Contents

- [Programmatic Usage](#programmatic-usage)
- [Custom Context](#custom-context)
- [Custom Steps](#custom-steps)
- [Custom Matchers and PathCalcs](#custom-matchers-and-pathcalcs)
- [Integration with External Tools](#integration-with-external-tools)
- [Build Hooks and Automation](#build-hooks-and-automation)
- [Testing and Validation](#testing-and-validation)
- [Performance Optimization](#performance-optimization)

## Programmatic Usage

While Anchovy works great from the command line, you can also use it programmatically for custom build workflows.

### Using run_from_rules

```python
from pathlib import Path
from anchovy import InputBuildSettings, Rule, REMatcher, OutputDirPathCalc, DirectCopyStep
from anchovy.cli import run_from_rules

# Define your configuration
SETTINGS = InputBuildSettings(
    input_dir=Path('site'),
    output_dir=Path('build'),
    custody_cache=Path('build-cache.json')
)

RULES = [
    Rule(REMatcher(r'.*\.md'), OutputDirPathCalc('.html'), JinjaMarkdownStep()),
    Rule(REMatcher(r'static/.*'), OutputDirPathCalc(), DirectCopyStep()),
]

# Run the build
if __name__ == '__main__':
    run_from_rules(SETTINGS, RULES)
```

### With Pre/Post Processing

```python
from anchovy.cli import run_from_rules
from my_site.config import SETTINGS, RULES

def main():
    # Pre-build tasks
    print("Starting build...")
    setup_environment()
    validate_content()

    # Run Anchovy
    run_from_rules(SETTINGS, RULES)

    # Post-build tasks
    print("Build complete!")
    generate_sitemap()
    upload_to_cdn()

if __name__ == '__main__':
    main()
```

### Direct Context Usage

```python
from pathlib import Path
from anchovy import Context, BuildSettings

# Create settings
settings = BuildSettings(
    input_dir=Path('site'),
    output_dir=Path('build'),
    working_dir=Path('working'),
    custody_cache=Path('build-cache.json'),
    purge_dirs=False
)

# Create context with rules
context = Context(settings, rules=[...])

# Run the build
context.run()

# Access build information
print(f"Processed {len(context.processed_files)} files")
```

### Custom CLI Arguments

```python
import argparse
from pathlib import Path
from anchovy.cli import run_from_rules
from my_site.config import SETTINGS, RULES

def main():
    parser = argparse.ArgumentParser(description='Build my site')
    parser.add_argument('--draft', action='store_true', help='Include draft posts')
    parser.add_argument('--optimize', action='store_true', help='Enable optimizations')
    args = parser.parse_args()

    # Modify rules based on arguments
    rules = RULES.copy()
    if args.draft:
        rules = add_draft_rules(rules)
    if args.optimize:
        rules = add_optimization_rules(rules)

    # Run build
    run_from_rules(SETTINGS, rules)

if __name__ == '__main__':
    main()
```

### Accessing Build Results

```python
from anchovy import Context

class TrackingContext(Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.processed_count = 0
        self.skipped_count = 0
        self.error_count = 0

    def process_file(self, path):
        try:
            result = super().process_file(path)
            if result.was_processed:
                self.processed_count += 1
            else:
                self.skipped_count += 1
            return result
        except Exception as e:
            self.error_count += 1
            raise

# Use custom context
context = TrackingContext(settings, rules)
context.run()

print(f"Processed: {context.processed_count}")
print(f"Skipped: {context.skipped_count}")
print(f"Errors: {context.error_count}")
```

## Custom Context

Customize the build process by subclassing `Context`.

### Filtering Input Files

```python
from anchovy import Context
from pathlib import Path
import time

class RecentFilesContext(Context):
    """Only process files modified in the last hour."""

    def find_inputs(self, path: Path):
        hour_ago = time.time() - 3600
        for candidate in super().find_inputs(path):
            if candidate.stat().st_mtime > hour_ago:
                yield candidate

# Use it
context = RecentFilesContext(settings, rules)
context.run()
```

### Custom Directory Structure

```python
from anchovy import Context
from pathlib import Path

class MultiInputContext(Context):
    """Process files from multiple input directories."""

    def __init__(self, settings, rules, extra_inputs=None):
        super().__init__(settings, rules)
        self.extra_inputs = extra_inputs or []

    def find_all_inputs(self):
        # Get standard inputs
        yield from super().find_inputs(self.context['input_dir'])

        # Add extra inputs
        for extra_dir in self.extra_inputs:
            yield from super().find_inputs(extra_dir)

# Use it
context = MultiInputContext(
    settings,
    rules,
    extra_inputs=[Path('content'), Path('data')]
)
```

### Progress Tracking

```python
from anchovy import Context
from pathlib import Path

class ProgressContext(Context):
    """Display progress during build."""

    def process(self):
        # Count total files
        all_files = list(self.find_inputs(self.context['input_dir']))
        total = len(all_files)

        print(f"Processing {total} files...")

        for i, path in enumerate(all_files, 1):
            print(f"[{i}/{total}] {path.name}")
            self.process_file(path)

        print("Build complete!")

# Or use with rich/tqdm
from rich.progress import track

class RichProgressContext(Context):
    def process(self):
        all_files = list(self.find_inputs(self.context['input_dir']))
        for path in track(all_files, description="Building..."):
            self.process_file(path)
```

### Error Handling

```python
from anchovy import Context
import logging

logger = logging.getLogger(__name__)

class RobustContext(Context):
    """Continue building even if some files fail."""

    def __init__(self, settings, rules):
        super().__init__(settings, rules)
        self.errors = []

    def process_file(self, path):
        try:
            return super().process_file(path)
        except Exception as e:
            logger.error(f"Failed to process {path}: {e}")
            self.errors.append((path, e))
            # Continue processing other files
            return None

    def run(self):
        super().run()

        if self.errors:
            print(f"\nBuild completed with {len(self.errors)} errors:")
            for path, error in self.errors:
                print(f"  {path}: {error}")
```

## Custom Steps

Create sophisticated file processors tailored to your needs.

### Multi-Step Pipeline

```python
from anchovy import Step
from pathlib import Path

class PipelineStep(Step):
    """Run multiple processing steps in sequence."""

    def __init__(self, *steps):
        super().__init__()
        self.steps = steps

    def __call__(self, path: Path, output_paths: list[Path]) -> None:
        # Start with input
        current = path

        # Run through each step
        for i, step in enumerate(self.steps):
            if i < len(self.steps) - 1:
                # Intermediate output
                temp = path.with_suffix(f'.step{i}')
                step(current, [temp])
                current = temp
            else:
                # Final output
                step(current, output_paths)

        # Clean up intermediate files
        for i in range(len(self.steps) - 1):
            temp = path.with_suffix(f'.step{i}')
            if temp.exists():
                temp.unlink()

# Use it
Rule(
    REMatcher(r'.*\.md'),
    OutputDirPathCalc('.html'),
    PipelineStep(
        MarkdownToHTMLStep(),
        MinifyHTMLStep(),
        ValidateHTMLStep()
    )
)
```

### Conditional Processing

```python
from anchovy import Step
from pathlib import Path

class ConditionalStep(Step):
    """Apply different processing based on file properties."""

    def __init__(self, small_step, large_step, threshold=1024*1024):
        super().__init__()
        self.small_step = small_step
        self.large_step = large_step
        self.threshold = threshold

    def __call__(self, path: Path, output_paths: list[Path]) -> None:
        size = path.stat().st_size

        if size < self.threshold:
            self.small_step(path, output_paths)
        else:
            self.large_step(path, output_paths)

# Use it - optimize large images differently
Rule(
    REMatcher(r'.*\.jpg'),
    OutputDirPathCalc(),
    ConditionalStep(
        small_step=DirectCopyStep(),  # Small images: just copy
        large_step=CWebPStep(quality=85),  # Large images: convert to WebP
        threshold=500*1024
    )
)
```

### Caching Step

```python
from anchovy import Step, BaseStandardStep
from pathlib import Path
import pickle

class CachedStep(BaseStandardStep):
    """Cache expensive computations."""

    def __init__(self, cache_file='step-cache.pkl'):
        super().__init__()
        self.cache_file = Path(cache_file)
        self.cache = self.load_cache()

    def load_cache(self):
        if self.cache_file.exists():
            with open(self.cache_file, 'rb') as f:
                return pickle.load(f)
        return {}

    def save_cache(self):
        with open(self.cache_file, 'wb') as f:
            pickle.dump(self.cache, f)

    def process(self, input_path: Path, output_path: Path) -> None:
        # Generate cache key
        cache_key = str(input_path)

        # Check cache
        if cache_key in self.cache:
            print(f"Using cached result for {input_path.name}")
            result = self.cache[cache_key]
        else:
            print(f"Computing result for {input_path.name}")
            result = self.expensive_computation(input_path)
            self.cache[cache_key] = result
            self.save_cache()

        # Write output
        output_path.write_text(result)

    def expensive_computation(self, path: Path) -> str:
        # Your expensive operation here
        import time
        time.sleep(1)  # Simulate slow operation
        return path.read_text().upper()
```

### Aggregating Step

```python
from anchovy import Step
from pathlib import Path
import json

class IndexStep(Step):
    """Aggregate information from all processed files."""

    def __init__(self):
        super().__init__()
        self.entries = []

    def __call__(self, path: Path, output_paths: list[Path]) -> None:
        # Extract metadata
        content = path.read_text()
        metadata = self.extract_metadata(content)

        # Add to index
        self.entries.append({
            'path': str(path),
            'metadata': metadata
        })

        # Generate individual output
        for output_path in output_paths:
            output_path.write_text(self.render(content, metadata))

    def finalize(self, output_dir: Path):
        """Call this after all files are processed."""
        index_path = output_dir / 'index.json'
        with open(index_path, 'w') as f:
            json.dump(self.entries, f, indent=2)

    def extract_metadata(self, content: str) -> dict:
        # Parse frontmatter, extract title, etc.
        return {'title': 'Example'}

# Use it
index_step = IndexStep()

RULES = [
    Rule(REMatcher(r'.*\.md'), OutputDirPathCalc('.html'), index_step),
]

# After build
def main():
    context = Context(settings, RULES)
    context.run()
    index_step.finalize(context['output_dir'])
```

## Custom Matchers and PathCalcs

### Glob Pattern Matcher

```python
from anchovy import Matcher
from pathlib import Path
import fnmatch

class GlobMatcher(Matcher[bool]):
    """Match using glob patterns instead of regex."""

    def __init__(self, pattern: str):
        self.pattern = pattern

    def __call__(self, context, path: Path) -> bool | None:
        if fnmatch.fnmatch(str(path), self.pattern):
            return True
        return None

# Use it
Rule(
    GlobMatcher('**/*.md'),
    OutputDirPathCalc('.html'),
    JinjaMarkdownStep()
)
```

### YAML Frontmatter Matcher

```python
from anchovy import Matcher
from pathlib import Path
import yaml

class YAMLFrontmatterMatcher(Matcher[dict]):
    """Match based on YAML frontmatter content."""

    def __init__(self, **required_fields):
        self.required_fields = required_fields

    def __call__(self, context, path: Path) -> dict | None:
        if not path.suffix == '.md':
            return None

        content = path.read_text()
        if not content.startswith('---'):
            return None

        # Parse frontmatter
        parts = content.split('---', 2)
        if len(parts) < 3:
            return None

        frontmatter = yaml.safe_load(parts[1])

        # Check required fields
        for key, value in self.required_fields.items():
            if frontmatter.get(key) != value:
                return None

        return frontmatter

# Use it - only process published posts
Rule(
    YAMLFrontmatterMatcher(published=True),
    OutputDirPathCalc('.html'),
    JinjaMarkdownStep()
)
```

### Template-Based PathCalc

```python
from anchovy import PathCalc
from pathlib import Path

class TemplatePathCalc(PathCalc):
    """Use a template string for output paths."""

    def __init__(self, template: str, ext: str = None):
        self.template = template
        self.ext = ext

    def __call__(self, context, path: Path, match) -> Path:
        output_dir = context['output_dir']
        input_dir = context['input_dir']

        # Get path components
        relative = path.relative_to(input_dir)
        parts = relative.parts

        # Template variables
        variables = {
            'year': parts[0] if len(parts) > 0 else '',
            'month': parts[1] if len(parts) > 1 else '',
            'name': path.stem,
            'ext': self.ext or path.suffix,
        }

        # Format template
        output_path = self.template.format(**variables)
        return output_dir / output_path

# Use it
# Template: {year}/{month}/{name}{ext}
# Input: 2024/01/post.md
# Output: build/2024/01/post.html
Rule(
    REMatcher(r'\d{4}/\d{2}/.*\.md'),
    TemplatePathCalc('{year}/{month}/{name}{ext}', ext='.html'),
    JinjaMarkdownStep()
)
```

## Integration with External Tools

### Running Shell Commands

```python
from anchovy import BaseCommandStep, WebExecDependency

class ShellStep(BaseCommandStep):
    """Run arbitrary shell commands."""

    def __init__(self, command_template: str):
        super().__init__()
        self.command_template = command_template

    def get_command(self, input_path, output_path):
        return self.command_template.format(
            input=str(input_path),
            output=str(output_path)
        ).split()

# Use it
Rule(
    REMatcher(r'.*\.svg'),
    OutputDirPathCalc('.png'),
    ShellStep('inkscape {input} --export-filename={output}')
)
```

### Docker Integration

```python
from anchovy import BaseCommandStep
from pathlib import Path

class DockerStep(BaseCommandStep):
    """Run commands inside Docker containers."""

    def __init__(self, image: str, command: str):
        super().__init__()
        self.image = image
        self.command = command

    def get_command(self, input_path: Path, output_path: Path):
        # Mount current directory as /workspace
        return [
            'docker', 'run', '--rm',
            '-v', f'{Path.cwd()}:/workspace',
            '-w', '/workspace',
            self.image,
            'sh', '-c',
            self.command.format(
                input=str(input_path),
                output=str(output_path)
            )
        ]

# Use it - run pandoc in Docker
Rule(
    REMatcher(r'.*\.md'),
    OutputDirPathCalc('.pdf'),
    DockerStep(
        image='pandoc/core',
        command='pandoc {input} -o {output}'
    )
)
```

### API Integration

```python
from anchovy import Step
from pathlib import Path
import requests

class TranslateStep(Step):
    """Translate content using an API."""

    def __init__(self, api_key: str, target_lang: str):
        super().__init__()
        self.api_key = api_key
        self.target_lang = target_lang

    def __call__(self, path: Path, output_paths: list[Path]) -> None:
        content = path.read_text()

        # Call translation API
        response = requests.post(
            'https://api.translate.example.com/v1/translate',
            headers={'Authorization': f'Bearer {self.api_key}'},
            json={
                'text': content,
                'target_lang': self.target_lang
            }
        )

        translated = response.json()['text']

        # Write translated content
        for output_path in output_paths:
            output_path.write_text(translated)

# Use it
Rule(
    REMatcher(r'en/.*\.md'),
    DirPathCalc(dest='output_dir/es'),
    TranslateStep(api_key='...', target_lang='es')
)
```

## Build Hooks and Automation

### Pre-Build Validation

```python
from pathlib import Path
from anchovy.cli import run_from_rules
from my_site.config import SETTINGS, RULES

def validate_content():
    """Check content before building."""
    input_dir = SETTINGS['input_dir']

    # Check for required files
    required = ['index.md', 'about.md']
    for filename in required:
        if not (input_dir / filename).exists():
            raise FileNotFoundError(f"Missing required file: {filename}")

    # Validate markdown files
    for md_file in input_dir.rglob('*.md'):
        content = md_file.read_text()
        if '---' not in content:
            print(f"Warning: No frontmatter in {md_file}")

def main():
    validate_content()
    run_from_rules(SETTINGS, RULES)

if __name__ == '__main__':
    main()
```

### Post-Build Actions

```python
from anchovy.cli import run_from_rules
from my_site.config import SETTINGS, RULES
import subprocess

def generate_sitemap():
    """Create sitemap.xml after build."""
    output_dir = SETTINGS['output_dir']

    # Find all HTML files
    html_files = list(output_dir.rglob('*.html'))

    # Generate sitemap
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>']
    sitemap.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for html_file in html_files:
        rel_path = html_file.relative_to(output_dir)
        url = f'https://example.com/{rel_path}'
        sitemap.append(f'  <url><loc>{url}</loc></url>')

    sitemap.append('</urlset>')

    # Write sitemap
    (output_dir / 'sitemap.xml').write_text('\n'.join(sitemap))

def optimize_images():
    """Run image optimization after build."""
    subprocess.run(['optipng', '-o7', 'build/**/*.png'], shell=True)

def main():
    run_from_rules(SETTINGS, RULES)
    generate_sitemap()
    optimize_images()
    print("Build complete with sitemap and optimized images!")

if __name__ == '__main__':
    main()
```

### Watch and Rebuild

```python
from pathlib import Path
from anchovy.cli import run_from_rules
from my_site.config import SETTINGS, RULES
import time

def watch_and_rebuild():
    """Watch for changes and rebuild."""
    input_dir = SETTINGS['input_dir']

    # Track modification times
    mtimes = {}
    for path in input_dir.rglob('*'):
        if path.is_file():
            mtimes[path] = path.stat().st_mtime

    print("Watching for changes...")

    while True:
        time.sleep(1)

        # Check for changes
        changed = False
        for path in input_dir.rglob('*'):
            if not path.is_file():
                continue

            current_mtime = path.stat().st_mtime
            if path not in mtimes or mtimes[path] != current_mtime:
                print(f"Detected change: {path}")
                mtimes[path] = current_mtime
                changed = True

        if changed:
            print("Rebuilding...")
            try:
                run_from_rules(SETTINGS, RULES)
                print("Build complete!")
            except Exception as e:
                print(f"Build failed: {e}")

if __name__ == '__main__':
    watch_and_rebuild()
```

## Testing and Validation

### Testing Configuration

```python
from pathlib import Path
from anchovy import Context, BuildSettings
from my_site.config import RULES
import tempfile

def test_build():
    """Test build configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test input
        input_dir = tmpdir / 'input'
        input_dir.mkdir()
        (input_dir / 'test.md').write_text('# Test')

        # Create settings
        settings = BuildSettings(
            input_dir=input_dir,
            output_dir=tmpdir / 'output',
            working_dir=tmpdir / 'working',
            custody_cache=None,
            purge_dirs=False
        )

        # Run build
        context = Context(settings, RULES)
        context.run()

        # Verify output
        output_file = tmpdir / 'output' / 'test.html'
        assert output_file.exists(), "Output file not created"
        assert '<h1>Test</h1>' in output_file.read_text()

        print("✓ Build test passed")

if __name__ == '__main__':
    test_build()
```

### Validation Step

```python
from anchovy import Step
from pathlib import Path
import html.parser

class HTMLValidator(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.errors = []

    def error(self, message):
        self.errors.append(message)

class ValidateHTMLStep(Step):
    """Validate HTML output."""

    def __call__(self, path: Path, output_paths: list[Path]) -> None:
        for output_path in output_paths:
            content = output_path.read_text()

            # Validate
            validator = HTMLValidator()
            try:
                validator.feed(content)
            except Exception as e:
                raise ValueError(f"Invalid HTML in {output_path}: {e}")

            if validator.errors:
                raise ValueError(f"HTML errors in {output_path}: {validator.errors}")

# Use it in a pipeline
Rule(
    REMatcher(r'.*\.html', parent_dir='working_dir'),
    [OutputDirPathCalc(), None],
    PipelineStep(
        HTMLMinifierStep(),
        ValidateHTMLStep()
    )
)
```

## Performance Optimization

### Parallel Processing

```python
from anchovy import Context
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

class ParallelContext(Context):
    """Process files in parallel."""

    def __init__(self, settings, rules, max_workers=4):
        super().__init__(settings, rules)
        self.max_workers = max_workers

    def process(self):
        all_files = list(self.find_inputs(self.context['input_dir']))

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.process_file, path): path
                for path in all_files
            }

            for future in as_completed(futures):
                path = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"Error processing {path}: {e}")

# Use it
context = ParallelContext(settings, rules, max_workers=8)
context.run()
```

### Lazy Loading

```python
from anchovy import Step
from pathlib import Path
from functools import lru_cache

class LazyTemplateStep(Step):
    """Cache template loading."""

    @lru_cache(maxsize=100)
    def load_template(self, template_path: Path):
        """Load template (cached)."""
        return template_path.read_text()

    def __call__(self, path: Path, output_paths: list[Path]) -> None:
        template = self.load_template(self.context['input_dir'] / 'base.html')
        content = path.read_text()
        result = template.replace('{{ content }}', content)

        for output_path in output_paths:
            output_path.write_text(result)
```

### Incremental Builds

```python
# Always use custody caching for incremental builds
SETTINGS = InputBuildSettings(
    input_dir=Path('site'),
    output_dir=Path('build'),
    custody_cache=Path('build-cache.json'),  # Essential!
    purge_dirs=False  # Don't purge for incremental builds
)
```

### Resource Management

```python
from anchovy import Step
from pathlib import Path
import gc

class MemoryEfficientStep(Step):
    """Process large files without loading entirely into memory."""

    def __call__(self, path: Path, output_paths: list[Path]) -> None:
        # Stream processing
        for output_path in output_paths:
            with open(path, 'r') as infile:
                with open(output_path, 'w') as outfile:
                    for line in infile:
                        # Process line by line
                        processed = line.upper()
                        outfile.write(processed)

        # Clean up
        gc.collect()
```

## Next Steps

- [API Reference](./api-reference.md) - Complete API documentation
- [Examples](../examples/) - Browse example projects in the repository
