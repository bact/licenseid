# LicenseID

[![PyPI - Version](https://img.shields.io/pypi/v/licenseid)](https://pypi.org/project/licenseid/)

A portable license ID matcher. Get the SPDX License ID from license text.

`licenseid` takes license text as input and identifies the closest matched SPDX License ID using a hybrid search strategy (trigram + token ratio ranking).

## Features

- **Hybrid strategy**:
  - **Tier 0 (Shortcut)**: Immediate identification for exact license names and IDs.
  - **Tier 1 (Recall)**: Rapid candidate retrieval using SQLite FTS5 (trigram) with query truncation for performance.
  - **Tier 2 (Precision)**: Adaptive ranking using RapidFuzz with boosting for canonical matches.
  - **Tier 3 (Validation)**: Optional final validation via `tools-java` if available.
- **Unix philosophy**: Parseable, line-delimited CLI output.
- **Performance**: Sub-second matching for most licenses; optimized for large file handling.

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

### 2. Match a license

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

- `--diff`: Show a word-by-word diff between the input and the best-matching candidate.
- `--java`: Enable Tier 3 Java validation (requires `SPDX_TOOLS_JAR` and `jpype1`).
- `--pop`: Enable popularity weighting as a tie-breaker.
- `--json`: Output results in JSON format.
- `--db <path>`: Use a custom database path (global option). Supports SQLite URIs for in-memory databases (e.g., `file:test?mode=memory&cache=shared`).

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

JSON:

```bash
licenseid match LICENSE.txt --json
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

## Development

### Running Tests

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
