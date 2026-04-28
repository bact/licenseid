# LicenseID

[![PyPI - Version](https://img.shields.io/pypi/v/licenseid)](https://pypi.org/project/licenseid/)

A portable license ID matcher. Get the SPDX License ID from license text.

`licenseid` takes license text as input and identifies the closest matched SPDX License ID using a hybrid search strategy (trigram + token ratio ranking).

## Features

- **Hybrid strategy**:
  - **Tier 1**: Broad recall using SQLite FTS5 with trigram tokenization.
  - **Tier 2**: Precision ranking using RapidFuzz (token set ratio) + Popularity weighting.
  - **Tier 3**: Optional final validation via `tools-java` if available.
- **Unix philosophy**: Parseable CLI output.

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

- `--version <version>`: Download a specific SPDX License List version (e.g., `3.26.0`).
- `--force`: Force update even if the local database is already at the target version.
- `--no-cache`: Bypass the local cache for downloads.

### 2. Match a license

Identify license text from a file:

```bash
licenseid match LICENSE.txt
```

Or match from a string:

```bash
licenseid match --text "MIT License"
```

Common options:

- `--java`: Enable Tier 3 Java validation (requires `SPDX_TOOLS_JAR` and `jpype1`).
- `--pop`: Enable popularity weighting as a tie-breaker.
- `--json`: Output results in JSON format.
- `--db <path>`: Use a custom database path (global option).

The popularity tie-breaker is triggered when candidate similarity scores differ by less than 0.2%.

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
LICENSE_ID=Apache-2.0 SCORE=0.9850
```

JSON:

```bash
licenseid match LICENSE.txt --json
```

## Configuration

- `SPDX_TOOLS_JAR`: Path to the `tools-java` jar for Tier 3 validation.

## License

Apache-2.0
