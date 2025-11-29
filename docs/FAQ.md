# Frequently Asked Questions

Common questions and answers about Anchovy.

## General

### What is Anchovy best suited for?

Anchovy excels at:
- Static website generation (blogs, documentation, portfolios)
- File transformation pipelines (image processing, minification)
- Build automation requiring dependency tracking
- Projects needing reproducible builds with custody tracking

It's particularly good when you want flexibility and don't want to fight an opinionated framework.

### How is Anchovy different from Jekyll, Hugo, or Eleventy?

**Anchovy vs. Jekyll/Hugo:**
- Anchovy is unopinionated - no enforced directory structure or blog assumptions
- Anchovy is Python-based, not Ruby or Go
- Anchovy works as a general file processor, not just for websites

**Anchovy vs. Eleventy:**
- Anchovy has no mandatory dependencies (not even Node.js)
- Anchovy's Step system is more modular and composable
- Anchovy has built-in custody tracking for intelligent rebuilds

**Anchovy vs. Static Site Generators Generally:**
- Anchovy is more of a framework/library than a tool
- You write Python configuration, giving you full programming power
- Anchovy can process non-web files (images, data, etc.)

### Can I use Anchovy for non-website projects?

Yes! Anchovy is a general file-processing framework. Use cases include:
- Image batch processing and optimization
- Data transformation pipelines
- Documentation generation
- Asset compilation and bundling
- Any workflow involving file transformations

### Does Anchovy require Python knowledge?

Basic Python is helpful but not required for simple sites. The configuration is straightforward:

```python
RULES = [
    Rule(REMatcher(r'.*\.md'), OutputDirPathCalc('.html'), JinjaMarkdownStep()),
]
```

For advanced usage (custom Steps, complex logic), Python knowledge becomes more important.

## Installation

### Which installation option should I choose?

- **`pip install anchovy`** - Minimal, no dependencies, for core framework only
- **`pip install anchovy[base]`** - Recommended for most users (Jinja, Markdown, CSS, minification)
- **`pip install anchovy[web]`** - Web development focus (base minus network fetching)
- **`pip install anchovy[all]`** - Currently same as `[base]`, future-proof

### Why are there so many optional dependencies?

Anchovy's philosophy is "pay for what you use." The core has no dependencies, and you only install what you need. This keeps the installation small and avoids bloat.

### How do I check what's installed?

```bash
anchovy config.py --audit-steps
```

This shows all available Steps and which dependencies are missing.

## Configuration

### Where should I put my configuration?

Common patterns:
- **`config.py`** in project root - Simple projects
- **`site_config.py`** or similar - Descriptive name
- **`myproject/build.py`** - Part of a Python package
- **`-m myproject.config`** - Module import style

### Can I split configuration across multiple files?

Yes! Use Python imports:

```python
# common.py
from pathlib import Path
BASE_DIR = Path(__file__).parent

# dev_config.py
from common import BASE_DIR
SETTINGS = InputBuildSettings(input_dir=BASE_DIR / 'site', ...)

# prod_config.py
from common import BASE_DIR
SETTINGS = InputBuildSettings(input_dir=BASE_DIR / 'content', ...)
```

### How do I use environment variables in configuration?

```python
import os
from pathlib import Path

SETTINGS = InputBuildSettings(
    input_dir=Path(os.environ.get('INPUT_DIR', 'site')),
    output_dir=Path(os.environ.get('OUTPUT_DIR', 'build')),
)

# Or use python-dotenv
from dotenv import load_dotenv
load_dotenv()
```

## Rules and Processing

### Why aren't my files being processed?

Common causes:

1. **No matching rule**
   ```python
   # Add debug Rule at the end
   Rule(REMatcher(r'.*'), OutputDirPathCalc(), DirectCopyStep())
   ```

2. **Rule order wrong** - More specific rules should come first
   ```python
   # Wrong order
   Rule(REMatcher(r'.*\.md'), ...)      # Catches everything
   Rule(REMatcher(r'blog/.*\.md'), ...) # Never reached!

   # Correct order
   Rule(REMatcher(r'blog/.*\.md'), ...) # Specific first
   Rule(REMatcher(r'.*\.md'), ...)      # General after
   ```

3. **File is ignored** - Check for exclusion rules
   ```python
   Rule(REMatcher(r'.*\.draft\.md'), None)  # This ignores drafts
   ```

4. **parent_dir mismatch**
   ```python
   # File is in working_dir, but rule checks input_dir
   Rule(REMatcher(r'.*\.html', parent_dir='input_dir'), ...)
   ```

### How do I process files through multiple steps?

Use `WorkingDirPathCalc` to create multi-stage pipelines:

```python
RULES = [
    # Stage 1: MD → HTML (to working_dir)
    Rule(
        REMatcher(r'.*\.md', parent_dir='input_dir'),
        WorkingDirPathCalc('.html'),
        JinjaMarkdownStep()
    ),

    # Stage 2: HTML → Minified (to output_dir, stop)
    Rule(
        REMatcher(r'.*\.html', parent_dir='working_dir'),
        [OutputDirPathCalc(), None],
        HTMLMinifierStep()
    ),
]
```

### How do I create one output from multiple inputs?

Use a custom Step that tracks all sources:

```python
class CombineStep(Step):
    def __call__(self, path: Path, output_paths: list[Path]) -> tuple:
        # path is a config file listing other files
        sources = [path]

        # Read config and collect source files
        for source_file in self.parse_config(path):
            sources.append(source_file)

        # Combine all sources
        combined = self.combine(sources)

        # Write output
        for output_path in output_paths:
            output_path.write_text(combined)

        # Return explicit custody
        return (sources, output_paths)
```

See `ResourcePackerStep` for a real example.

## Templates and Markdown

### How do I pass data to templates?

Use frontmatter in Markdown files:

```markdown
---
title: My Post
author: Jane Doe
date: 2024-01-15
---

# Content here
```

These become template variables:
```html
<h1>{{ title }}</h1>
<p>By {{ author }} on {{ date }}</p>
{{ content }}
```

### Can I use template inheritance?

Yes! Specify the template in frontmatter:

```markdown
---
template: post.jinja.html
---
```

And in your template:
```html
{% extends "base.jinja.html" %}
{% block content %}
{{ content }}
{% endblock %}
```

### How do I track template dependencies?

See the [Jinja template dependency tracking example](./matchers-pathcalcs.md) in the docs. The key is returning all templates in the custody tuple:

```python
def __call__(self, path: Path, output_paths: list[Path]) -> tuple:
    # Find all included templates
    dependencies = self.find_template_deps(path)

    # Render
    result = self.render(path)

    # Return all templates as sources
    return ([path] + dependencies, output_paths)
```

## Performance

### How can I speed up builds?

1. **Enable custody caching**
   ```python
   SETTINGS = InputBuildSettings(
       custody_cache=Path('build-cache.json')
   )
   ```

2. **Don't purge unnecessarily**
   ```python
   SETTINGS = InputBuildSettings(
       purge_dirs=False  # Only purge when needed
   )
   ```

3. **Use specific matchers**
   ```python
   # Slow - checks every file
   Rule(REMatcher(r'.*'), ...)

   # Fast - only checks .md files
   Rule(REMatcher(r'.*\.md'), ...)
   ```

4. **Profile your Steps**
   - Identify slow Steps
   - Consider parallelization (see Advanced Usage)
   - Cache expensive operations

### Why is my first build slow but rebuilds fast?

This is normal! The first build processes everything. Rebuilds with custody caching skip unchanged files, making them much faster.

### How big can my site be?

Anchovy handles thousands of files well. Performance considerations:
- Custody cache size grows with file count
- More files = more to check for staleness
- Consider parallel processing for very large sites (see Advanced Usage)

## Deployment

### How do I deploy my built site?

The `build/` directory (or your `output_dir`) is a static site. Deploy it anywhere:

```bash
# Copy to web server
rsync -avz build/ user@server:/var/www/

# AWS S3
aws s3 sync build/ s3://my-bucket/

# Netlify
netlify deploy --dir=build

# GitHub Pages
# Push build/ to gh-pages branch
```

### Should I commit the build directory?

Generally no. Add it to `.gitignore`:
```
build/
working/
```

But DO commit the custody cache:
```
build-cache.json
```

### Can I run Anchovy in CI/CD?

Yes! Example GitHub Actions workflow:

```yaml
name: Build and Deploy
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install anchovy[base]
      - run: python -m anchovy config.py
      - uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./build
```

## Troubleshooting

### I get "No module named 'xyz'"

Install the missing dependency:
```bash
# Check what's needed
anchovy config.py --audit-steps

# Install missing package
pip install xyz
```

### Files are being rebuilt every time

Check that:
1. Custody cache is enabled and being saved
2. Build settings aren't changing between runs
3. File modification times aren't being altered

Debug with:
```bash
# Check cache file
cat build-cache.json | jq .parameters
```

### My custom Step isn't being used

Ensure:
1. Step inherits from `Step`
2. `__call__` method is implemented
3. Step is imported in config
4. Dependencies are satisfied (check with `--audit-steps`)

### Images aren't processing

Check dependencies:
```bash
# For PillowStep
pip install Pillow

# For ImageMagick steps
magick --version

# For CWebPStep
cwebp -version
```

## Advanced Topics

### Can I use Anchovy with Docker?

Yes! Example Dockerfile:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "-m", "anchovy", "config.py"]
```

### How do I integrate with webpack/vite/etc?

Run external tools before or after Anchovy:

```python
def main():
    # Run webpack first
    subprocess.run(['npm', 'run', 'build'])

    # Then run Anchovy
    run_from_rules(SETTINGS, RULES)

if __name__ == '__main__':
    main()
```

Or use `BaseCommandStep` to invoke them as part of the pipeline.

### Can I create a plugin system?

Yes! Use entry points or dynamic imports:

```python
# Load plugins from a directory
plugin_dir = Path('plugins')
for plugin_file in plugin_dir.glob('*.py'):
    spec = importlib.util.spec_from_file_location('plugin', plugin_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # module.RULES gets added to your rules
```

## Getting Help

### Where can I ask questions?

- **GitHub Issues**: [https://github.com/pydsigner/anchovy/issues](https://github.com/pydsigner/anchovy/issues)
- **Documentation**: Start with [Getting Started](./getting-started.md)
- **Examples**: Browse [examples/](../examples/) directory

### How do I report a bug?

Open a GitHub issue with:
1. Anchovy version (`pip show anchovy`)
2. Python version
3. Minimal reproduction example
4. Expected vs. actual behavior
5. Full error traceback

### How do I request a feature?

Open a GitHub issue describing:
1. What you want to do
2. Why existing features don't work
3. Proposed API (if you have ideas)

### Can I contribute?

Yes! Anchovy is open source under Apache 2.0. Contributions welcome:
- Bug fixes
- New Steps
- Documentation improvements
- Example projects
- Tests

See the repository for contribution guidelines.
