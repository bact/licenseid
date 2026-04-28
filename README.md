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

### 2. Match a license

Match text from a file:

```bash
licenseid match LICENSE.txt
```

Match with Java validation enabled:

```bash
licenseid match LICENSE.txt --java
```

Match with popularity tie-breaker enabled:

```bash
licenseid match LICENSE.txt --pop
```

The tie-breaker is triggered only when candidate similarity scores
differ by less than 0.02%.

### 3. Output formats

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
