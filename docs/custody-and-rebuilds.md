# Custody and Intelligent Rebuilds

Anchovy's custody system provides intelligent incremental rebuilds by tracking file dependencies and changes. This guide explains how it works and how to use it effectively.

## Table of Contents

- [Overview](#overview)
- [Enabling Custody Caching](#enabling-custody-caching)
- [How It Works](#how-it-works)
- [Custody Entries](#custody-entries)
- [Staleness Detection](#staleness-detection)
- [Custom Custody Entries](#custom-custody-entries)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

The Custodian is Anchovy's dependency tracking system. It:

- Tracks relationships between inputs and outputs
- Stores checksums and metadata for all files
- Skips processing when inputs haven't changed
- Detects when outputs have been modified externally
- Removes orphaned output files
- Supports custom entry types for special dependencies

**Benefits:**
- **Fast rebuilds**: Only process changed files
- **Consistent builds**: Detect external modifications
- **Reproducibility**: Save build artifacts with checksums
- **Dependency tracking**: Understand what depends on what

## Enabling Custody Caching

Enable custody caching by specifying a cache file:

### In Configuration

```python
from pathlib import Path
from anchovy import InputBuildSettings

SETTINGS = InputBuildSettings(
    input_dir=Path('site'),
    output_dir=Path('build'),
    custody_cache=Path('build-cache.json'),  # Enable custody caching
)
```

### Via CLI

```bash
# Specify cache file
anchovy config.py --custody-cache build-cache.json

# Disable custody cache (even if config specifies one)
anchovy config.py --custody-cache=None
```

### Cache File Format

The cache is JSON with this structure:

```json
{
  "parameters": {
    "input_dir": "/path/to/site",
    "output_dir": "/path/to/build",
    "working_dir": "/path/to/working"
  },
  "graph": {
    "output/file.html": {
      "input/source.md": [
        "output/file.html"
      ],
      "templates/base.html": [
        "output/file.html"
      ]
    }
  },
  "entries": {
    "input/source.md": {
      "entry_type": "path",
      "key": "input/source.md",
      "meta": {
        "sha1": "a1b2c3d4...",
        "m_time": 1234567890.0,
        "size": 1024
      }
    }
  }
}
```

## How It Works

### Build Flow with Custody

```
1. Load custody cache (if exists)
   ├─ Read parameters, graph, entries
   └─ Validate parameters match current settings

2. For each file to process:
   ├─ Check if refresh needed
   │  ├─ Parameters changed?
   │  ├─ Output files exist?
   │  ├─ Upstream record exists?
   │  ├─ Upstream unchanged?
   │  └─ Downstream unchanged?
   │
   ├─ If refresh needed:
   │  ├─ Run Step
   │  ├─ Record new checksums
   │  └─ Update dependency graph
   │
   └─ If refresh NOT needed:
      └─ Skip processing (use cached)

3. Remove orphaned files
   ├─ Find outputs in cache but not in new graph
   └─ Delete them

4. Save custody cache
   ├─ Write parameters, graph, entries
   └─ Save to JSON file
```

### Dependency Graph

The custody graph tracks which inputs affect which outputs:

```python
{
    "output/post.html": {
        "input/post.md": ["output/post.html"],
        "templates/base.html": ["output/post.html"],
        "templates/macros.html": ["output/post.html"]
    }
}
```

This means:
- `output/post.html` depends on three source files
- If any source changes, `output/post.html` will be regenerated
- If `output/post.html` is deleted, it will be regenerated
- If `post.md` is deleted, `output/post.html` becomes orphaned

### Metadata Tracking

For each file, the Custodian stores:

```python
{
    "entry_type": "path",
    "key": "input/post.md",
    "meta": {
        "sha1": "a1b2c3d4...",  # SHA1 checksum
        "m_time": 1234567890.0,  # Modification time
        "size": 1024             # File size in bytes
    }
}
```

## Custody Entries

### Path Entries

Standard file entries track local files:

```python
{
    "entry_type": "path",
    "key": "site/index.md",
    "meta": {
        "sha1": "abc123...",
        "m_time": 1234567890.0,
        "size": 2048
    }
}
```

**Checker:** Compares SHA1 checksums

### Requests Entries

For files fetched via `RequestsFetchStep`:

```python
{
    "entry_type": "requests",
    "key": "https://cdn.example.com/lib.js",
    "meta": {
        "etag": "\"abc123\"",  # HTTP ETag header
        "url": "https://cdn.example.com/lib.js"
    }
}
```

**Checker:** Compares ETag headers (if available)

### URLLib Entries

For files fetched via `URLLibFetchStep`:

```python
{
    "entry_type": "urllib",
    "key": "https://example.com/data.json",
    "meta": {
        "etag": "\"xyz789\"",
        "url": "https://example.com/data.json"
    }
}
```

**Checker:** Compares ETag headers (if available)

## Staleness Detection

The Custodian determines if a file needs reprocessing by checking these conditions:

### 1. Stale Parameters

Build settings changed since last run:

```python
# Last run: input_dir=site, output_dir=build
# This run: input_dir=content, output_dir=public
# Result: All files are stale
```

**Reason:** `"Stale parameters"`

**Fix:** Full rebuild required

### 2. Missing Output

Output file doesn't exist:

```python
# Expected: build/index.html
# Actual: File not found
# Result: Stale
```

**Reason:** `"Missing output (build/index.html)"`

**Fix:** Regenerate output

### 3. Missing Upstream Record

No custody record for source file:

```python
# New file: site/new-post.md
# Cache: No entry for site/new-post.md
# Result: Stale
```

**Reason:** `"Missing upstream record (site/new-post.md)"`

**Fix:** Process new file

### 4. Stale Upstream

Source file changed:

```python
# Cached: site/index.md (sha1: abc123...)
# Current: site/index.md (sha1: xyz789...)
# Result: Stale
```

**Reason:** `"Stale upstream (site/index.md)"`

**Fix:** Reprocess because input changed

### 5. Stale Downstream

Output was modified externally:

```python
# Cached: build/index.html (sha1: abc123...)
# Current: build/index.html (sha1: xyz789...)
# Result: Stale
```

**Reason:** `"Stale downstream (build/index.html)"`

**Fix:** Reprocess because output was tampered with

### Staleness Examples

```python
# Fresh build - no cache
# All files: Missing upstream record -> Process all

# Second build - nothing changed
# All files: Fresh -> Skip all

# Edit one markdown file
# Edited file: Stale upstream -> Process
# Other files: Fresh -> Skip

# Delete an output file
# Corresponding input: Missing output -> Process
# Other files: Fresh -> Skip

# Manually edit an output file
# Corresponding input: Stale downstream -> Process
# Other files: Fresh -> Skip

# Change build settings
# All files: Stale parameters -> Process all
```

## Custom Custody Entries

Create custom entry types for special dependencies.

### Defining a Custom Entry Type

```python
from anchovy import Custodian, CustodyEntry

@Custodian.register_checker('my_custom_type')
def check_custom_entry(entry: CustodyEntry) -> bool:
    """
    Check if custom entry is still valid.

    Args:
        entry: The custody entry to check

    Returns:
        True if entry is still valid, False if stale
    """
    # Your staleness logic
    key = entry['key']
    meta = entry['meta']

    # Example: Check external API version
    current_version = fetch_api_version(meta['api_url'])
    return current_version == meta['version']
```

### Creating Custom Entries in Steps

```python
from anchovy import Step

class APIFetchStep(Step):
    """Fetches data from an API and tracks version."""

    def __call__(self, path: Path, output_paths: list[Path]) -> tuple:
        # Read config
        config = self.read_config(path)
        api_url = config['api_url']

        # Fetch data
        data, version = self.fetch_from_api(api_url)

        # Write output
        for output_path in output_paths:
            output_path.write_text(data)

        # Create custom custody entry
        custom_entry = CustodyEntry(
            entry_type='my_custom_type',
            key=api_url,
            meta={
                'api_url': api_url,
                'version': version,
                'timestamp': time.time()
            }
        )

        # Return explicit custody with custom entry
        return ([custom_entry], output_paths)
```

### Git Commit Checker Example

```python
import subprocess
from anchovy import Custodian, CustodyEntry

@Custodian.register_checker('git_commit')
def check_git_commit(entry: CustodyEntry) -> bool:
    """Check if git commit is still current."""
    repo_path = entry['meta']['repo_path']
    cached_commit = entry['meta']['commit_hash']

    # Get current commit
    result = subprocess.run(
        ['git', 'rev-parse', 'HEAD'],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    current_commit = result.stdout.strip()

    return current_commit == cached_commit

class GitInfoStep(Step):
    """Embed git commit info in build."""

    def __call__(self, path: Path, output_paths: list[Path]) -> tuple:
        # Get current commit
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True
        )
        commit_hash = result.stdout.strip()

        # Generate output
        content = f"Built from commit: {commit_hash}\n"
        for output_path in output_paths:
            output_path.write_text(content)

        # Track git commit as dependency
        git_entry = CustodyEntry(
            entry_type='git_commit',
            key=str(Path.cwd()),
            meta={
                'repo_path': str(Path.cwd()),
                'commit_hash': commit_hash
            }
        )

        return ([git_entry, path], output_paths)
```

### Environment Variable Checker

```python
import os
from anchovy import Custodian, CustodyEntry

@Custodian.register_checker('env_var')
def check_env_var(entry: CustodyEntry) -> bool:
    """Check if environment variable is unchanged."""
    var_name = entry['meta']['var_name']
    cached_value = entry['meta']['value']
    current_value = os.environ.get(var_name)

    return current_value == cached_value

class EnvTemplateStep(Step):
    """Template that depends on environment variables."""

    def __call__(self, path: Path, output_paths: list[Path]) -> tuple:
        # Read environment
        api_key = os.environ.get('API_KEY', 'default')
        debug_mode = os.environ.get('DEBUG', 'false')

        # Generate output using env vars
        content = self.render_with_env(path, api_key, debug_mode)

        for output_path in output_paths:
            output_path.write_text(content)

        # Track env vars as dependencies
        env_entries = [
            CustodyEntry(
                entry_type='env_var',
                key='API_KEY',
                meta={'var_name': 'API_KEY', 'value': api_key}
            ),
            CustodyEntry(
                entry_type='env_var',
                key='DEBUG',
                meta={'var_name': 'DEBUG', 'value': debug_mode}
            )
        ]

        return (env_entries + [path], output_paths)
```

## Best Practices

### Always Use Custody Caching

Enable custody caching for faster builds:

```python
SETTINGS = InputBuildSettings(
    input_dir=Path('site'),
    output_dir=Path('build'),
    custody_cache=Path('build-cache.json'),  # Always specify
)
```

### Commit the Cache File

Add custody cache to version control:

```bash
git add build-cache.json
git commit -m "Update build cache"
```

**Benefits:**
- Reproducible builds
- CI/CD can use cached builds
- Team members share build state

### Use Explicit Custody for Complex Dependencies

When a Step has dependencies beyond the input file:

```python
class TemplateStep(Step):
    def __call__(self, path: Path, output_paths: list[Path]) -> tuple:
        # This markdown file uses a template
        template_path = self.find_template(path)

        # Render using both files
        content = self.render(path, template_path)

        for output_path in output_paths:
            output_path.write_text(content)

        # Return BOTH files as sources
        return ([path, template_path], output_paths)
```

This ensures changes to the template trigger rebuilds.

### Clean Builds When Needed

Force a full rebuild when:
- Custody cache is corrupted
- Build logic changed significantly
- Strange behavior occurs

```bash
# Delete cache and rebuild
rm build-cache.json
anchovy config.py

# Or use purge flag
anchovy config.py --purge
```

### Monitor Cache Growth

Large caches may slow down builds:

```bash
# Check cache size
ls -lh build-cache.json

# Reduce by removing old entries (manual editing or full rebuild)
rm build-cache.json && anchovy config.py
```

### Use Descriptive Entry Types

For custom entries, use clear names:

```python
# Good
@Custodian.register_checker('external_api_version')
@Custodian.register_checker('git_submodule_commit')
@Custodian.register_checker('config_file_hash')

# Bad
@Custodian.register_checker('custom1')
@Custodian.register_checker('check2')
```

## Troubleshooting

### All Files Rebuild Every Time

**Possible Causes:**

1. **No custody cache specified**
   ```python
   # Fix: Add custody_cache to settings
   SETTINGS = InputBuildSettings(
       custody_cache=Path('build-cache.json')
   )
   ```

2. **Cache file not being saved**
   ```bash
   # Check permissions
   ls -l build-cache.json

   # Check for errors during save
   anchovy config.py  # Look for error messages
   ```

3. **Build settings change each run**
   ```python
   # Bad: Different each time
   SETTINGS = InputBuildSettings(
       input_dir=Path(f'site-{datetime.now()}')  # DON'T DO THIS
   )

   # Good: Consistent
   SETTINGS = InputBuildSettings(
       input_dir=Path('site')
   )
   ```

### Outputs Not Regenerating When They Should

**Possible Causes:**

1. **Dependency not tracked**
   ```python
   # Bad: Template change won't trigger rebuild
   class BadStep(Step):
       def __call__(self, path: Path, output_paths: list[Path]) -> None:
           template = self.load_template()  # Not tracked!
           content = template.render(path.read_text())
           output_paths[0].write_text(content)

   # Good: Template tracked as dependency
   class GoodStep(Step):
       def __call__(self, path: Path, output_paths: list[Path]) -> tuple:
           template_path = self.find_template()
           template = self.load_template(template_path)
           content = template.render(path.read_text())
           output_paths[0].write_text(content)
           return ([path, template_path], output_paths)
   ```

2. **Custom checker always returns True**
   ```python
   # Bad: Always says "fresh"
   @Custodian.register_checker('my_type')
   def check(entry):
       return True  # BUG: Never stale!

   # Good: Actually checks staleness
   @Custodian.register_checker('my_type')
   def check(entry):
       current = get_current_state()
       cached = entry['meta']['state']
       return current == cached
   ```

### Orphaned Files Not Removed

**Possible Causes:**

1. **Custody cache disabled**
   ```bash
   # Enable it
   anchovy config.py --custody-cache build-cache.json
   ```

2. **Files created outside Anchovy**
   ```bash
   # Manually created files aren't tracked
   echo "test" > build/manual.html  # Not in custody graph

   # Anchovy won't remove it
   ```

### Cache File Corruption

**Symptoms:**
- JSON decode errors
- Missing keys in cache
- Strange rebuild behavior

**Fix:**
```bash
# Delete and rebuild
rm build-cache.json
anchovy config.py

# Cache will be regenerated
```

### Slow Builds Despite Caching

**Possible Causes:**

1. **Too many small files**
   ```bash
   # Solution: Combine files where possible
   # Use ResourcePackerStep to bundle
   ```

2. **Expensive staleness checks**
   ```python
   # Bad: Network call on every check
   @Custodian.register_checker('api')
   def check(entry):
       return requests.get(entry['meta']['url']).status_code == 200

   # Good: Cache results or use ETags
   @Custodian.register_checker('api')
   def check(entry):
       response = requests.head(entry['meta']['url'])
       return response.headers.get('ETag') == entry['meta']['etag']
   ```

3. **Large cache file**
   ```bash
   # Check size
   ls -lh build-cache.json

   # If very large (>10MB), consider clean rebuild
   rm build-cache.json && anchovy config.py
   ```

## Advanced Usage

### Programmatic Custody Access

```python
from anchovy import Custodian, Context, BuildSettings
from pathlib import Path

# Create custodian
custodian = Custodian()

# Bind to context
settings = BuildSettings(...)
context = Context(settings, rules=[])
custodian.bind(context)

# Load cache
custodian.load_file(Path('build-cache.json'))

# Check staleness
sources = [Path('site/index.md')]
outputs = [Path('build/index.html')]
is_stale, reason = custodian.refresh_needed(sources, outputs)

if is_stale:
    print(f"Rebuild needed: {reason}")
    # Process file...
    custodian.add_step(sources, outputs, "Processed")
else:
    print("Using cached version")
    custodian.skip_step(sources[0], outputs)

# Save cache
custodian.dump_file(Path('build-cache.json'))
```

### Inspecting the Cache

```python
import json
from pathlib import Path

# Load cache
with open('build-cache.json') as f:
    cache = json.load(f)

# Inspect parameters
print("Build parameters:", cache['parameters'])

# Inspect dependency graph
for output, dependencies in cache['graph'].items():
    print(f"{output} depends on:")
    for source, outputs in dependencies.items():
        print(f"  - {source}")

# Inspect entries
for key, entry in cache['entries'].items():
    print(f"{key}: {entry['entry_type']}")
    print(f"  Metadata: {entry['meta']}")
```

## Next Steps

- [Advanced Usage](./advanced-usage.md) - Custom components and programmatic usage
- [API Reference](./api-reference.md) - Complete API documentation
