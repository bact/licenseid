# LicenseID - A Portable SPDX License ID matcher

[![PyPI - Version](https://img.shields.io/pypi/v/licenseid)](https://pypi.org/project/licenseid/)
![GitHub License](https://img.shields.io/github/license/bact/licenseid)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/14002/badge)](https://www.bestpractices.dev/projects/14002)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/bact/licenseid/badge)](https://scorecard.dev/viewer/?uri=github.com/bact/licenseid)
[![DOI](https://img.shields.io/badge/doi-10.5281%2Fzenodo.19881009-blue)](https://doi.org/10.5281/zenodo.19881009)

Get the [SPDX License ID][spdx-license-id] from license text.

A portable license ID matcher with command line interface and Python API.
No database daemon or server needed.

*Used as a license detection engine for [Pitloom] software bill of materials generator.*

[spdx-license-id]: https://spdx.org/licenses/
[Pitloom]: https://github.com/bact/pitloom/

## Features

- **Hybrid matching pipeline**:
  - **Tier 0.5 (Marker detection)**: Detects `SPDX-License-Identifier` tags and
    structured markers (name fields, headings). An exact SPDX tag returns
    immediately with full confidence.
  - **Tier 0 (Shortcut)**: Fast path for short inputs (names, IDs, brief
    expressions). Includes:
    - Case-insensitive exact ID match.
    - Prose-context disambiguation for bare deprecated IDs (e.g.
      `"GPL-2.0 or later version"` → `GPL-2.0-or-later`).
    - Conservative `-only` fallback when no granting context is present.
  - **Tier 1 (Recall)**: Candidate retrieval using SQLite FTS5 trigram index,
    queried with the input's first 20 words, plus its last 20 for an input
    over 200 words (at most 25 more candidates), for consistent performance.
    Comment prefixes (`//`, `#`, `*`, `;`) are stripped before querying.
  - **Tier 2 (Precision)**: Adaptive ranking with RapidFuzz. Sliding-window
    alignment for fragments; coverage-aware scoring to prefer the tightest
    match. Marker confidence boosts applied only when confidence ≥ 0.85.
- **Deprecated ID normalisation**:
  - `GPL-2.0+` → `GPL-2.0-or-later` (SPDX `+` operator, unambiguous).
  - `Apache-2+` → `Apache-2.0+` (abbreviated base canonicalised, `+` retained).
  - Bare deprecated IDs (e.g. `GPL-2.0`) resolved conservatively to `-only`
    when no surrounding context is available.
- **SPDX License Expression support** (via [`py-spdx-license`][py-spdx-license]):
  - Structural normalisation of `AND`/`OR` expressions: duplicate operands
    collapse (`MIT AND MIT` → `MIT`) and operands are put in a consistent
    order, making equivalent expressions compare equal.
  - `WITH <exception>` expressions are validated and matched against the
    SPDX exception list, not just the license list — e.g.
    `licenseid match --id "MIT WITH Font-exception-2.0"` resolves correctly
    even though it isn't a single license row.
  - A `SPDX-License-Identifier` tag, and the `license` field of a JSON, TOML
    or INI file, are read as whole expressions, parentheses, `LicenseRef-*`
    and all: `MIT OR (Apache-2.0 AND BSD-3-Clause)` in a file resolves to
    one answer. `--id` is narrower on purpose — see below.
  - Package manifests are read for their `license` field, however small:
    `package.json` (with npm's old `license` object and `licenses` array),
    `pyproject.toml` (`license = "..."` or `license = {text = "..."}`, and
    Poetry's), `Cargo.toml` and `setup.cfg`.

[py-spdx-license]: https://github.com/JPEWdev/py-spdx-license

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

### Non-UTF-8 locales

A dependency, `py-spdx-license` 0.0.1, reads its bundled license data with
the locale's encoding. Under a multibyte locale that is not UTF-8, such as
`ja_JP.eucJP`, every command then fails at start-up with a
`UnicodeDecodeError`. Until a fixed release is out, set `PYTHONUTF8=1` to
run Python in UTF-8 mode:

```bash
export PYTHONUTF8=1
```

On Windows, use `set PYTHONUTF8=1` in Command Prompt or
`$env:PYTHONUTF8 = "1"` in PowerShell. UTF-8 locales and Python 3.15 or
later need no setting.

## Usage

### 1. Update the license database

Before matching, you need to build the local license index:

```bash
licenseid update
```

Progress and warnings go to standard error; standard output carries only the
result line.

Advanced update options:

- `--version <version>`: Download a specific SPDX License List version
  (e.g., `3.28.0`).
- `--force`: Force update even if the local database is already at
  the target version.
- `--no-cache`: Bypass the local cache for downloads.

### 2. Identify a license

Identify license text from a file, an ID, or a string:

```bash
# From a file (smart detection)
licenseid match LICENSE.txt

# From an ID (smart detection)
licenseid match MIT

# From a string (smart detection / piped)
echo "MIT License..." | licenseid match

# Explicit ID lookup (fastest, skips similarity check)
licenseid match --id MIT
```

Input is read as UTF-8. Text that is not valid UTF-8 is read as Latin-1,
with a warning on standard error; binary data is rejected (exit code 2).

Common options:

- `--db <path>`: Use a custom database path (global option).
  Supports SQLite URIs for in-memory databases
  (e.g., `file:test?mode=memory&cache=shared`).
- `--id <id>`: Explicitly treat input as one SPDX License ID (bypasses
  file/text matching). It declares a single license, so it takes an ID, a
  `LicenseRef-*`, an ID with `+` (a `LicenseRef-*` takes none), and either
  `WITH <exception>`, in
  brackets or not: `MIT`, `(MIT)`, `Apache-2.0+`,
  `MIT WITH Font-exception-2.0`. It does not take an
  `AND`/`OR` expression, a license name, an SPDX URL or prose — those name
  no single license, so they exit 2 with
  `ERROR: option: invalid: --id: <value>; pass one license ID`. A file's tag
  may still hold any expression. Input that is one such value and nothing
  else, whether an argument, `--text`, standard input or a file, is read as
  `--id` reads it (`--text GPL-2.0+` is `GPL-2.0-or-later`); anything else
  is matched as text: `MIT but modified heavily by us` is text, not MIT.
- `--text <text>`: Match the given text. Backslash escapes such as `\n`,
  `\t` and `\u00e9` are decoded, so write `\\` for a literal backslash
  (for example in a Windows path).
- `--bold`: Print only the top license ID (no other info).
- `--diff`: Show a word-by-word diff between the input and the top
  result, when it was matched as text and is not exact.
- `--json`: Output results as JSON Lines (see below).
- `--threshold <score>`: Keep results that score at least this, from 0 to
  1 (default 0.85). A value outside 0 to 1 exits 2.
- `--top <n>`: Keep at most this many results (default 3).
- `--exact`: Keep only exact results (`EXACT=true`, see below).
- `--pop/--no-pop`: Weigh results by popularity, or not (default off).

The system uses a **composite score** (similarity + coverage bonus/penalty +
optional popularity weight + marker confidence boost) to prefer the tightest
match. For example, it distinguishes a short permissive licence from a
superset that shares the same preamble.

### 3. Cache management

`licenseid` maintains a local cache of remote data to save bandwidth.

- `licenses.json`: Cached for 45 days.
- `popularity.csv`: Cached for 75 days.
- SPDX data tarballs are versioned and never expire.

To clear the cache manually:

```bash
licenseid --clear-cache
```

This deletes the database and the cache files beside it, so it refuses a
`--db` path holding a file licenseid did not build (exit 2,
`database: invalid`). A database it cannot read is still cleared: that is
what the command is for.

### 4. Output formats

Default (Unix-friendly), one result per line, best first (the examples
show the first two results):

```text
LICENSE_ID=Apache-2.0 METHOD=text EXACT=true SCORE=1.0000 SIMILARITY=1.0000 COVERAGE=1.0000
LICENSE_ID=ECL-2.0 METHOD=text EXACT=false SCORE=0.9584 SIMILARITY=0.9584 COVERAGE=0.9236
```

- `METHOD` is how the answer was found: `tag` (an `SPDX-License-Identifier`
  tag), `field` (a manifest's `license` field), `id` (a license ID), `name`
  (a license name) or `text` (the license text).
- `EXACT` is `true` when the answer was found exactly: declared (a tag, a
  field or an ID), a license name spelt out in full (for a name a
  deprecated license shares with its successor, only the successor), or the
  whole input equal to the license text as the SPDX License List writes
  it, after case, punctuation and white space are normalised.
  A filled-in copyright line or an added title makes a text not exact, as
  does a name that only shares the words of the input. Licenses with the
  same text (`GPL-2.0-only` and `GPL-2.0-or-later`) are all exact for it.
  `--exact` keeps only the exact results.
- `SCORE` is 0 to 1; `--threshold` reads it. Several results can score 1:
  the order tells them apart, and `EXACT` tells an exact one from a close
  one.
- `SIMILARITY` and `COVERAGE` are empty where nothing was measured: a tag,
  a field or an ID has neither, a name has no coverage. `COVERAGE` is the
  input's words over the license's, so it passes 1 when the input is longer.

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

Example output, in JSON Lines: one object per result per line, in the
JSON Canonicalization Scheme (RFC 8785), so equal results print equal bytes
(`jq -s .` makes an array of them):

```json
{"coverage":1,"exact":true,"is_fsf_libre":true,"is_osi_approved":true,"is_spdx":true,"license_id":"Apache-2.0","method":"text","score":1,"similarity":1}
{"coverage":0.9236,"exact":false,"is_fsf_libre":true,"is_osi_approved":true,"is_spdx":true,"license_id":"ECL-2.0","method":"text","score":0.9584,"similarity":0.9584}
```

Diff (visual comparison), here of an Apache-2.0 file with its copyright
line filled in:

```bash
licenseid match LICENSE --diff --top 1
```

Example output (a diff is shown for the top result when it was matched as
text and is not exact; any other results follow it):

```diff
LICENSE_ID=Apache-2.0 METHOD=text EXACT=false SCORE=1.0000 SIMILARITY=0.9978 COVERAGE=0.9987

WORD DIFF:
--- DATABASE
+++ INPUT
@@ -1502,11 +1502,9 @@
 party
 archives
 copyright
-yyyy
-name
-of
-copyright
-holder
+2024
+jane
+doe
 licensed
 under
 the
```

### 5. Exit codes

The CLI follows standard Unix exit code conventions,
making it suitable for use in scripts and CI/CD pipelines.

| Exit Code | Meaning | Scenarios |
| :--- | :--- | :--- |
| **0** | Success | Confident match found; predicate is TRUE; database updated or already up-to-date. |
| **1** | Logic Failure | No matching license found; predicate is FALSE; network error. |
| **2** | Usage or Setup Error | Missing subcommand (help on standard error); missing input text/file; invalid parameters; database not ready; output that cannot be written. |
| **130** | Interrupted | Ctrl-C (SIGINT); no message once started. |
| **141** | Reader gone | The reader closed the pipe (`head -1`); no message. |

A database is not ready when it is missing, empty (no licenses yet), invalid
(another program's file) or unreadable. `match` and the `is-*` commands refuse
to answer from one, rather than reporting "no license found" or `false`.

Errors and warnings go to standard error, one per line, in a fixed format:

```text
LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION]
```

For example:

```text
ERROR: database: not found: /tmp/x.db; run 'licenseid update'
ERROR: option: not found: --jsn; did you mean --json
WARNING: popularity.csv: download failed: timed out; using stale cache
```

`LEVEL` is `ERROR` (the command fails) or `WARNING` (it continues).
`SUBJECT` is the thing affected, such as `database`, `input` or a cache file
name, so `cut -d: -f1-3` gives the level, subject and condition.

### 6. License predicates (for CI/CD)

Predicate commands are designed for shell scripting.
They print `true`/`false` and exit with `0` (for true) or `1` (for false).

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

# 1. Match by Raw Text (Positional or Keyword)
# Programmatic API is explicit: positional 'text' is always treated as text.
results = matcher.match("Permission is hereby granted...")
results = matcher.match(text="Custom license text...")

# 2. Match by SPDX License ID (Explicit)
# This performs a fast database lookup and returns full metadata.
results = matcher.match(license_id="MIT")

# 3. Match by File Path (Explicit)
# The file is read as the CLI reads it: UTF-8, else Latin-1 with a warning;
# binary data raises licenseid.InvalidInputError.
results = matcher.match(file_path="LICENSE.txt")

# 4. Predicates
# Supports keyword arguments for precise control.
if matcher.is_osi(license_id="MIT"):
    print("OSI Approved!")

if matcher.is_open(file_path="LICENSE.txt"):
    print("Open Source!")

if matcher.is_spdx(text="Creative Commons Zero v1.0 Universal"):
    print("SPDX Match Found!")
```

`match()` takes the keyword options `enable_popularity`, `exclude`, `hint`,
`only_common` and `only_spdx`, and raises `licenseid.InvalidInputError` (a
`RuntimeError`) for any other, such as a mistyped name. The options shape the
ranking of license text; an explicit `license_id`, a bare ID or name and an
`SPDX-License-Identifier` tag are answered before they are read.

The constructor raises `licenseid.DatabaseNotReadyError` (a `RuntimeError`)
when the database is missing, empty, invalid (another program's file) or
unreadable, for example before the first `licenseid update`. The check opens
the file read-only: it never creates or changes the database itself, though
SQLite may leave its own `-shm` and `-wal` files beside it.

Each result is a `licenseid.LicenseMatch` with the same keys, `license_id`,
`method` (a `licenseid.Method`), `exact`, `score`, `similarity`, `coverage`,
`is_spdx`, `is_osi_approved` and `is_fsf_libre`, as in the CLI's output
above; `similarity` and `coverage` are `None` where nothing was measured.
For `match(text="MIT")`:

```python
[
    {
        "license_id": "MIT",
        "method": "id",
        "exact": True,
        "score": 1.0,
        "similarity": None,
        "coverage": None,
        "is_spdx": True,
        "is_osi_approved": True,
        "is_fsf_libre": True,
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

## License

Apache-2.0

## Citation

If you use this software, please cite it as follows:

> Suriyawongkul, A. (2026). LicenseID - A Portable SPDX License ID Matcher (Version 0.4.1) [Computer software]. <https://doi.org/10.5281/zenodo.19881009>

BibTeX:

```bibtex
@software{Suriyawongkul_LicenseID_-_A_2026,
    author = {Suriyawongkul, Arthit},
    doi = {10.5281/zenodo.19881009},
    license = {Apache-2.0},
    month = aug,
    title = {{LicenseID - A Portable SPDX License ID Matcher}},
    url = {https://github.com/bact/licenseid.git},
    version = {0.4.1},
    year = {2026}
}
```
