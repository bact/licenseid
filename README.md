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

## Usage

### 1. Update the license database

Before matching, you need to build the local license index:

```bash
licenseid update
```

Advanced update options:

- `--version <version>`: Download a specific SPDX License List version (e.g., `3.28.0`).
- `--force`: Force update even if the local database is already at the target version.
- `--no-cache`: Bypass the local cache for downloads.

### 2. Identify a license

Identify license text from a file, an ID, or a string:

```bash
# From a file
licenseid match LICENSE.txt

# From an ID (returns metadata)
licenseid match MIT

# From a string (piped)
echo "MIT License..." | licenseid match
```

Common options:

- `--db <path>`: Use a custom database path (global option). Supports SQLite URIs for in-memory databases (e.g., `file:test?mode=memory&cache=shared`).
- `--id <id>`: Explicitly treat input as an SPDX License ID (bypasses file/text matching).
- `--bold`: Print only the top license ID (no other info).
- `--diff`: Show a word-by-word diff between the input and the best-matching candidate.
- `--json`: Output results in JSON format.

The system uses a **composite score** (Similarity + Coverage + Popularity) to ensure the "tightest" match is preferred (e.g., distinguishing between a license and its supersets).

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

### 5. Exit codes

The CLI follows standard Unix exit code conventions, making it suitable for use in scripts and CI/CD pipelines.

| Exit Code | Meaning | Scenarios |
| :--- | :--- | :--- |
| **0** | Success | Confident match found; predicate is TRUE; database updated or already up-to-date. |
| **1** | Logic Failure | No matching license found; predicate is FALSE; network error. |
| **2** | Usage Error | Missing subcommand; missing input text/file; invalid parameters. |

### 6. License predicates (for CI/CD)

Predicate commands are designed for shell scripting. They print `true`/`false` and exit with `0` (for true) or `1` (for false).

| Command | Description |
| :--- | :--- |
| `is-spdx` | True if the license is in the SPDX License List. |
| `is-open` | True if the license is OSI-approved **OR** FSF-libre. |
| `is-free` | Alias for `is-open`. |
| `is-osi` | True if the license is OSI-approved. |
| `is-fsf` | True if the license is FSF-libre. |

Example usage in a script:

```bash
# Check by ID
if licenseid is-osi MIT; then
  echo "This is an OSI-approved license."
fi

# Check by File
licenseid is-open LICENSE.txt || echo "Warning: Not an open source license"

# Check by Text (via stdin)
echo "MIT License..." | licenseid is-fsf && echo "FSF Libre!"
```

## Python API

You can use `licenseid` directly in your Python projects:

```python
from licenseid.matcher import AggregatedLicenseMatcher

# Initialize with default database
matcher = AggregatedLicenseMatcher()

# 1. Smart Matching (ID, File, or Text)
results = matcher.match("MIT")
results = matcher.match("LICENSE.txt")
results = matcher.match("MIT License. Permission is hereby granted...")

# 2. Explicit Matching
results = matcher.match(license_id="MIT")
results = matcher.match(file_path="LICENSE.txt")
results = matcher.match(text="Custom license text...")

# 3. Predicates
if matcher.is_osi("MIT"):
    print("OSI Approved!")

if matcher.is_open(file_path="LICENSE.txt"):
    print("Open Source!")
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
