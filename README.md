# LicenseID - A portable SPDX License ID matcher

[![PyPI - Version](https://img.shields.io/pypi/v/licenseid)](https://pypi.org/project/licenseid/)
![GitHub License](https://img.shields.io/github/license/bact/licenseid)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19881009.svg)](https://doi.org/10.5281/zenodo.19881009)

Get the [SPDX License ID][spdx-license-id] from license text.

A portable license ID matcher with command line interface and Python API.

*Used as a license detection engine for [Pitloom] software bill of materilas generator.*

[spdx-license-id]: https://spdx.org/licenses/
[Pitloom]: https://github.com/bact/pitloom/

## Features

- **Hybrid matching strategy**:
  - **Tier 0 (Shortcut)**: Immediate identification for exact license names and IDs.
  - **Tier 1 (Recall)**: Rapid candidate retrieval using SQLite FTS5 (trigram) with query truncation for performance.
  - **Tier 2 (Precision)**: Adaptive ranking using RapidFuzz with boosting for canonical matches.
  - **Tier 3 (Validation)**: Optional final validation via `tools-java` if available.
- **Unix philosophy**: Parseable, line-delimited CLI output.

## Installation

Install with `pipx`:

```bash
pipx install licenseid
```

Or using `uv`:

```bash
uv tool install licenseid
```

> [!IMPORTANT]
> After installation, build the local license database by running:
>
> ```bash
> licenseid update
> ```

## Usage

### 1. Match a license

Identify license text from a file:

```bash
licenseid match LICENSE.txt
```

Or match from a string:

```bash
licenseid match --text "Apache License\nVersion 2.0"
```

The `--text` argument supports standard escape sequences (e.g., `\n`, `\t`, `\"`) which are automatically unescaped before matching.

Common options:

- `--db <path>`: Use a custom database path (global option). Supports SQLite URIs for in-memory databases (e.g., `file:test?mode=memory&cache=shared`).
- `--bold`: Print only the top license ID (no other info).
- `--diff`: Show a word-by-word diff between the input and the best-matching candidate.
- `--json`: Output results in JSON format.

The system uses a **composite score** (Similarity + Coverage + Popularity) to ensure the "tightest" match is preferred (e.g., distinguishing between a license and its supersets).

### 2. Update the license database

```bash
licenseid update
```

Advanced update options:

- `--version <version>`: Download a specific SPDX License List version (e.g., `3.28.0`).
- `--force`: Force update even if the local database is already at the target version.
- `--no-cache`: Bypass the local cache for downloads.

### 3. Cache management

`licenseid` maintains a local cache of remote data to save bandwidth.

- `licenses.json`: Cached for 45 days.
- `popularity.csv`: Cached for 75 days.
- SPDX data tarballs are versioned and never expire.

To clear the cache manually:

```bash
licenseid --clear-cache
```

### 4. Output formats

Default (Unix-friendly):

```text
LICENSE_ID=Apache-2.0 SIMILARITY=0.9850 COVERAGE=1.0000
```

ID only:

```bash
licenseid match LICENSE.txt --bold
```

Example output:

```text
Apache-2.0
```

JSON:

```bash
licenseid match LICENSE.txt --json
```

Example output:

```json
[
  {
    "license_id": "Apache-2.0",
    "score": 0.985,
    "similarity": 0.985,
    "coverage": 1.0,
    "is_spdx": true,
    "is_osi_approved": true
  }
]
```

Diff (visual comparison):

```bash
licenseid match LICENSE.txt --diff
```

Example output:

```diff
LICENSE_ID=Apache-2.0 SIMILARITY=0.9980 COVERAGE=0.9975

WORD DIFF:
--- DATABASE
+++ INPUT
@@ -1601,8 +1601,4 @@
 language
 governing
 permissions
-and
-limitations
-under
-the
-license
+se
```

## Python API

You can use `licenseid` directly in your Python projects:

```python
import json
from licenseid.matcher import AggregatedLicenseMatcher

# Initialize the matcher (uses default database path if not provided)
matcher = AggregatedLicenseMatcher()

# Match license text
results = matcher.match("MIT License")

# Results are returned as a list of dictionaries (JSON-serializable)
print(json.dumps(results, indent=2))
```

Example JSON output:

```json
[
  {
    "license_id": "MIT",
    "score": 1.01,
    "similarity": 1.0,
    "coverage": 0.0
  }
]
```

## Development

### Running tests

Regular test suite:

```bash
pytest
```

Run benchmarks and accuracy tests (expensive):

```bash
pytest --run-benchmark
```

## Configuration

- `SPDX_TOOLS_JAR`: Path to the `tools-java` jar for Tier 3 validation.

## License

Apache-2.0
