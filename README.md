# LicenseID - A Portable SPDX License ID matcher

[![PyPI - Version](https://img.shields.io/pypi/v/licenseid)](https://pypi.org/project/licenseid/)
![GitHub License](https://img.shields.io/github/license/bact/licenseid)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/14002/badge)](https://www.bestpractices.dev/projects/14002)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/bact/licenseid/badge)](https://scorecard.dev/viewer/?uri=github.com/bact/licenseid)
[![DOI](https://img.shields.io/badge/doi-10.5281%2Fzenodo.19881009-blue)](https://doi.org/10.5281/zenodo.19881009)

Get the [SPDX License ID][spdx-license-id] from license text.

A portable license ID matcher with command line interface and Python API.
No database daemon or server needed.

*Used as a license detection engine for [Pitloom] software bill of materials
generator.*

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
    by `detect()` when no surrounding context is available, as a guess said
    aloud: not exact, with `WARNING: input: variant not stated: GPL-2.0;
    using GPL-2.0-only`, whether the ID is an argument, `--id`, a tag or a
    manifest field; `match()` keeps them as written (below).
- **Declared-value resolution** (`match()`, and `licenseid match` on the
  command line): turns one declared licence value (a `license` field, a
  model card, a trove classifier) into an SPDX expression and the steps
  taken, without fuzzy matching, with or without a database. It reads loose
  IDs (`Apache2`, `GPLv3`), the List's names, prose forms (`BSD 3-Clause
  License`), quote marks, trove classifiers and compounds of one-word
  operands, and refuses, with a reason, what it would read only by dropping
  a mark or a word. What it reads, rule by rule, is in
  [docs/match.md][match-doc-reads].
- **SPDX License Expression support** (via
  [`py-spdx-license`][py-spdx-license]):
  - Structural normalisation of `AND`/`OR` expressions: duplicate operands
    collapse (`MIT AND MIT` → `MIT`) and operands are put in a consistent
    order, making equivalent expressions compare equal. The canonical order of
    `match()` differs from this one (`MirOS OR MIT` there, `MIT OR MirOS`
    here).
  - The flags of an expression are judged operand by operand: `AND` is
    OSI-approved (or FSF-libre) when every operand is, `OR` when any is,
    `X WITH Y` when `X` is. An operand that cannot be judged (a
    `LicenseRef-*`, an ID not on the List) leaves the flag empty (`null`),
    never a false "no". `is_spdx` is true only when every licence and
    exception ID is on the List: a `LicenseRef-*` makes it false.
  - `WITH <exception>` expressions are validated and matched against the
    SPDX exception list, not just the license list — e.g.
    `licenseid detect --id "MIT WITH Font-exception-2.0"` resolves correctly
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
`UnicodeDecodeError`. The fix is waiting upstream in
[JPEWdev/py-spdx-license#5](https://github.com/JPEWdev/py-spdx-license/pull/5).
Until a fixed release is out, set `PYTHONUTF8=1` to run Python in UTF-8
mode:

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
result, one line per list (`--json`: one JSON object per list):

```text
LIST=spdx-license-list	VERSION=3.29.0	STATUS=updated	PATH=/home/me/.local/share/licenseid/licenses.db
```

`LIST` is the list, by the ID `match()` gives it in `lists[*].id`;
`VERSION` is the release the database now holds; `STATUS` is `updated`, or
`unchanged` when the database already had that release.

Advanced update options:

- `--list <id>[@<version>]`: The list to install, and its release
  (`--list spdx-license-list@3.28.0`); without a version, the latest.
  Repeatable; with none, every list licenseid installs, at its latest
  release (today one: `spdx-license-list`). A release given is fetched
  without asking which release is the latest. An ID licenseid does not
  install, a version that is no release (`3.28.0` or `3.28`) and a list
  named twice exit 2.
- `--force`: Force update even if the local database is already at
  the target version.
- `--no-cache`: Bypass the local cache for downloads.
- `--source auto|compact|upstream|packaged`: Where the license data comes
  from. `auto` (default) tries `compact`, then `upstream`, then `packaged`;
  the other values use that one source only.
  - `compact`: our bundle of about 1 MB (JSON and license texts, no XML), from
    `raw.githubusercontent.com`, so `licenseid update` works where only that
    host is reachable.
  - `upstream`: SPDX's own release tarball on GitHub (about 49 MB).
  - `packaged`: the bundle shipped in the package, of the release that was
    newest when the package was built. `licenseid update` still works with
    no network, with data that may be older.

### 2. Detect a licence, or match a declared value

Two commands answer two questions (as `detect()` and `match()` do in the
[Python API](#python-api)):

```bash
# Which licence is in this file? Ranked candidates, with a score.
licenseid detect LICENSE.txt

# Which SPDX expression does this declared value stand for? One answer and
# the steps taken, or a refusal; no database needed.
licenseid match "GPLv2 or later"
```

`detect` identifies license text from a file, an ID, or a string:

```bash
# From a file (smart detection)
licenseid detect LICENSE.txt

# From an ID (smart detection)
licenseid detect MIT

# From a string (smart detection / piped); "-" names standard input
echo "MIT License..." | licenseid detect
echo "MIT License..." | licenseid detect -

# Explicit ID lookup (fastest, skips similarity check)
licenseid detect --id MIT
```

One input at a time: `--text` or `--id` with an argument (a file, a value
or `-`), or `--id` with `--text`, exits 2 with
`ERROR: option: invalid: --id: with --text; pass one input`. Standard input
is read only when nothing else is given, so a pipe beside an argument is not
read.

An argument names a file when one exists by that name. One that does not,
but is shaped like a path (one word with `/`, `\` or a file extension, such
as `LICENSE.txt` or `docs/LICENSE`), exits 2 with
`ERROR: input: not found: <value>; pass --text`, rather than be matched as
text. A URL, with or without its scheme, and license IDs joined by `/`
(`MIT/Apache-2.0`) are not paths. Use `--text` to match any value as text.

Input is read as UTF-8. Text that is not valid UTF-8 is read as Latin-1,
with a warning on standard error; binary data is rejected (exit code 2).

Common options:

- `--db <path>`: Use a custom database path (global option).
  Supports SQLite URIs for in-memory databases
  (e.g., `file:test?mode=memory&cache=shared`).
- `--id <id>`: Explicitly treat input as one SPDX License ID (bypasses
  file/text matching). It declares a single license, so it takes an ID, a
  `LicenseRef-*`, an ID with `+` (a `LicenseRef-*` takes none, nor does an
  ID that ends in `-only` or `-or-later`), and either
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
  An argument that names no file is first checked for the shape of a path
  (see above). A value that is no license, such as `GPL-2.0-only+` (a "+"
  after a stated qualifier), is a "no" as text (exit 1, and `detect()`
  returns no result) and a usage error as `--id` (exit 2).
- `--text <text>`: Match the given text, taken as written: a backslash is
  a backslash (`C:\temp\new` is that path), and `\n` is two characters.
  For a line break, pass one (`--text "$(printf 'a\nb')"`) or pipe the
  text.
- `--id-only`: Print only the top expression, or an empty line when there
  is none (exit 1).
- `--diff`: Show a word-by-word diff between the input and the top
  result, when it was matched as text and is not exact, on standard error.
- `--json`: Output results as JSON Lines (see below). It takes neither
  `--id-only` nor `--diff`: either with it exits 2.
- `--threshold <score>`: Keep results that score at least this, from 0 to
  1 (default 0.85). A value outside 0 to 1 exits 2.
- `--top <n>`: Keep at most this many results (default 3); below 1 exits 2.
- `--exact`: Keep only exact results (`EXACT=true`, see below).
- `--pop/--no-pop`: Weigh results by popularity, or not (default off).

The system uses a **composite score** (similarity + coverage bonus/penalty +
optional popularity weight + marker confidence boost) to prefer the tightest
match. For example, it distinguishes a short permissive licence from a
superset that shares the same preamble.

### 3. Match a declared value

`licenseid match VALUE` reads one value that someone wrote to declare a
licence (a `license` field, a trove classifier) with `match()`, and prints
its resolution, one data point per line:

```console
$ licenseid match "GPLv2+ or MIT"
EXPRESSION=GPL-2.0-or-later OR MIT	CATEGORY=version_spelling	TRUST=resolver_rule
STEP=separator	FROM=GPLv2	TO=GPL-2.0
STEP=version_spelling	FROM=GPLv2	TO=GPL-2.0
STEP=operator_case	FROM=GPL-2.0-or-later or MIT	TO=GPL-2.0-or-later OR MIT
STEP=plus_to_or_later	FROM=GPLv2+	TO=GPL-2.0-or-later
```

- The first line is the answer: `EXPRESSION=` is empty when the value
  resolves to no expression. Its category and trust are those of
  [docs/match.md][match-doc].
- `STEP=` lines are the steps applied, in order, then the qualifiers
  (`-or-later`) applied; a step that was declined is not printed.
- `REASON=` says why a value was refused (`character dropped: U+003F`).
- `OPERAND=`, `EXPRESSION=` and `CATEGORY=` lines follow for licences
  joined by `;` (`MIT ; Apache 2`), which say no operator.
- The fields are separated by one tab, as in `detect`'s lines
  ([Output formats](#5-output-formats)); read them with `cut -f` or
  `awk -F'\t'`. `--json` prints the whole result instead, as one RFC 8785
  object: `licenseid match --json "$v" | jq -r .expression`.

Options:

- `--json`: the whole result of `match()`, as one JSON object.
- `--source auto|database|packaged`: the list read when `--db` is not
  given, as `match(source=...)` reads it (default `auto`: the database at the
  default path or the list shipped with licenseid, whichever is newer).
- `--db <path>` (global option): read that database, as `match(value, db)`;
  `--source packaged` with it exits 2.

`match` reads a declared value, not a licence text, so it refuses what only
`detect` answers, with exit 2, nothing on standard output and
`; run 'licenseid detect'`: `--text`, `-` (standard input), a
value with a line break, and one over 2,000 characters once its surrounding
white space is trimmed. A value that resolves is answered even when a file
of that name exists (`match MIT` beside a file `MIT`); one that resolves to
nothing and names an existing file or directory (`match LICENSE`) is
refused. An empty argument, or no argument, is a usage error too
(`input: missing`): `match` never reads standard input, so a pipe that stays
open cannot hold it. Exit 0 means the value resolved to an
expression (`GPL-3.0`, kept as `assumed_only`, included), 1 that it did not
(a list joined by `;` included), with no `ERROR` line.

`detect` and `match` answer different questions, so their answers to one
value can differ:

| Command | Prints | Means |
| :--- | :--- | :--- |
| `detect GPL2` | `EXPRESSION=GPL-2.0-only`, `EXACT=false`, with `WARNING: input: variant not stated` | the closest licence on the list, a guess said aloud |
| `match GPL2` | `EXPRESSION=GPL-2.0`, `CATEGORY=assumed_only` | what was declared, kept as written: no guess |

### 4. Cache management

`licenseid` maintains a local cache of remote data to save bandwidth.

- `latest.json` (the compact bundle's version pointer) and `licenses.json`
  (spdx.org's): Cached for 45 days each. `--source upstream` asks spdx.org
  only, and `--no-cache` skips the caches.
- `popularity.csv`: Cached for 75 days.
- Compact bundles and upstream tarballs are versioned and never expire.

To clear the cache manually:

```console
$ licenseid clear-cache
STATUS=cleared	PATH=/home/me/.local/share/licenseid/licenses.db
```

This deletes the database and the cache files beside it, and prints one
record (`--json`: one object): `STATUS=cleared`, or `nothing` when there was
nothing of licenseid's to delete, and the database `PATH`. Cache files are
deleted only where they are licenseid's: in the default directory, or
beside any ready database. Beside a `--db` path with no ready
database, they are kept. It refuses a
`--db` path holding a file licenseid did not build (exit 2,
`database: invalid`); a delete the system refuses exits 1. A database it
cannot read is still cleared: that is what the command is for.

### 5. Output formats

Default (Unix-friendly), one result per line, best first (the examples
show the first two results):

```text
EXPRESSION=Apache-2.0	METHOD=text	EXACT=true	SCORE=1.0000	SIMILARITY=1.0000	COVERAGE=1.0000
EXPRESSION=ECL-2.0	METHOD=text	EXACT=false	SCORE=0.9584	SIMILARITY=0.9584	COVERAGE=0.9236
```

- One tab separates the fields; a key ends at the first `=`. Read them with
  `cut -f` or `awk -F'\t'`. A value is written as it is, except a tab, a
  carriage return, a line feed and a backslash, written `\t`, `\r`, `\n` and
  `\\`, and a character the locale of standard output cannot encode,
  written `\xHH`, `\uHHHH` or `\UHHHHHHHH`. `--json` is UTF-8 on every
  locale.
- `EXPRESSION` is the answer: one licence ID for `detect`.
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

The top expression only:

```bash
licenseid detect LICENSE.txt --id-only
```

Example output:

```text
Apache-2.0
```

JSON:

```bash
licenseid detect LICENSE.txt --json
```

Example output, in JSON Lines: one object per result per line, in the
JSON Canonicalization Scheme (RFC 8785), so equal results print equal bytes
(`jq -s .` makes an array of them):

```json
{"coverage":1,"exact":true,"expression":"Apache-2.0","is_fsf_libre":true,"is_osi_approved":true,"is_spdx":true,"method":"text","score":1,"similarity":1}
{"coverage":0.9236,"exact":false,"expression":"ECL-2.0","is_fsf_libre":true,"is_osi_approved":true,"is_spdx":true,"method":"text","score":0.9584,"similarity":0.9584}
```

Diff (visual comparison), here of an Apache-2.0 file with its copyright
line filled in:

```bash
licenseid detect LICENSE --diff --top 1
```

Example output (a diff is shown for the top result when it was matched as
text and is not exact; with `--id-only` too, not with `--json`). The result
lines go to standard output and the diff to standard error, so
`2>/dev/null` keeps only the results:

```diff
EXPRESSION=Apache-2.0	METHOD=text	EXACT=false	SCORE=1.0000	SIMILARITY=0.9978	COVERAGE=0.9987

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

#### Reading the output

Every command prints its result in one pattern, so one reader serves them
all:

- One record per line, `KEY=VALUE` fields with an uppercase key, one tab
  between fields, and `\t`, `\r`, `\n` and `\\` for a tab, a line break
  or a backslash inside a value.
- The first key of a line names its kind: `EXPRESSION` the answer, `STEP` a
  step of `match`, `REASON` a refusal, `OPERAND` a licence of a list,
  `LIST` the list `update` read, `STATUS` what `clear-cache` did.
- The answer is the first line. A command with no answer still prints its
  record, every field empty: `detect` on exit 1 prints
  `EXPRESSION=` and the other keys with nothing after the `=`.
- Fields are only ever appended to a line in a later release, never
  removed, renamed or moved: read a field by its key, not its place.
- `--json` prints the same record as one RFC 8785 JSON object per line,
  its keys the text keys in lower case (`EXPRESSION` is `expression`).
  `null` means nothing, where the text line has an empty value. The keys of
  `match --json`, which prints the whole result as one object, are mapped
  to its text lines in [docs/match.md][match-doc].

The only exceptions are `detect --id-only` (the expression alone),
`--version` and `--help`.

```bash
# The second field of the line, its value after the "="
licenseid is-osi MIT | cut -f2 | cut -d= -f2-          # true

# The answer: the first field of the line whose first key is EXPRESSION
# (match also prints EXPRESSION= after OPERAND= on a line of its own kind)
licenseid match "MIT ; Apache 2" | awk -F'\t' '
  $1 ~ /^EXPRESSION=/ { print substr($1, length("EXPRESSION=") + 1); exit }'

# The same with jq
licenseid detect --json LICENSE | jq -r .expression
licenseid match --json "GPLv2+" | jq -r '.steps[] | select(.applied) | .kind'
licenseid update --json | jq -r '"\(.status) \(.version)"'
```

### 6. Exit codes

The CLI follows standard Unix exit code conventions,
making it suitable for use in scripts and CI/CD pipelines.

| Exit Code | Meaning | Scenarios |
| :--- | :--- | :--- |
| **0** | Success | Confident match found; `match`: the value resolved to an expression; predicate is TRUE; database updated or already up-to-date; cache cleared or nothing to clear. |
| **1** | Logic Failure | No matching license found (one record, every field empty); `match`: no expression (the result is still printed); predicate is FALSE, or cannot be judged (its record still printed); an update or a cache clear that failed (a network error, a delete the system refuses). |
| **2** | Usage or Setup Error | Missing subcommand (help on standard error); missing input text/file; two inputs; `--json` with `--id-only` or `--diff`; invalid parameters; `match` given a text, `-`, or a path that resolves to nothing; database not ready (for `match`, no list to read); output that cannot be written. |
| **130** | Interrupted | Ctrl-C (SIGINT); no message once started. |
| **141** | Reader gone | The reader closed the pipe (`head -1`); no message. |

Exit 1 of `detect`, `match` and the `is-*` commands prints no `ERROR` line.
A `WARNING` about the input or the database can still come with it, as with
an answer: `detect --exact GPL-2.0` says `variant not stated` and finds no
exact match.

A database is not ready when it is missing, empty (no licenses yet), invalid
(another program's file) or unreadable. `detect` and the `is-*` commands refuse
to answer from one, rather than exiting 1 for no licence or `false`;
`match` reads the list shipped with licenseid instead, unless `--db` or
`--source database` asks for the database.

`licenseid --version` prints `licenseid <version>`.

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

### 7. License predicates (for CI/CD)

Predicate commands are designed for shell scripting.
They exit with `0` (for true) or `1` (for false, or no answer), and print
one line: the licence judged and the answer (`--json`: one JSON object):

```console
$ licenseid is-osi MIT
EXPRESSION=MIT	IS_OSI_APPROVED=true
$ licenseid is-osi --json MIT
{"expression":"MIT","is_osi_approved":true}
```

For an expression, `AND` is true when every operand is, `OR` when any is,
and `X WITH Y` as `X` is. The flag is empty (`null` in JSON), exit 1, when
there is nothing to judge: never a false "no". That is when the input names
no licence (`EXPRESSION` is empty too), or when an operand cannot be judged
(`MIT OR LicenseRef-x`).

| Command | Key | Description |
| :--- | :--- | :--- |
| `is-spdx` | `IS_SPDX` | True if every licence and exception ID is on the SPDX License List (a `LicenseRef-*` is not). |
| `is-osi` | `IS_OSI_APPROVED` | True if the license is OSI-approved. |
| `is-fsf` | `IS_FSF_LIBRE` | True if the license is FSF-libre. |

OSI-approved or FSF-libre is the two joined:
`licenseid is-osi X >/dev/null || licenseid is-fsf X >/dev/null`.

Example usage in a script:

```bash
# Check by ID
if licenseid is-osi MIT >/dev/null; then
  echo "This is an OSI-approved license."
fi

# Check by File: OSI-approved or FSF-libre
licenseid is-osi LICENSE.txt >/dev/null ||
  licenseid is-fsf LICENSE.txt >/dev/null ||
  echo "Neither OSI-approved nor FSF-libre"

# Check by Text (via stdin)
echo "MIT License..." | licenseid is-fsf >/dev/null && echo "FSF Libre!"
```

## Python API

`licenseid` answers two questions, with one call each:

- **What licence is in this thing?** `detect()` detects a licence in a file,
  a licence text, a source file's `SPDX-License-Identifier` tag or a short
  value. It weighs evidence (IDs, names, full-text search, similarity),
  needs the database, and returns ranked candidates with a score.
- **What does this declared value mean?** `match()` reads one value that
  someone wrote to declare a licence, such as a `license` field or a trove
  classifier. It follows rules only, needs no database, and returns one SPDX
  expression with each step taken, or refuses: it never guesses.

```python
from licenseid import detect, match

# A LICENSE file: which licence is it?
detect(file_path="LICENSE")[0]["expression"]
# "Apache-2.0" for this repository's LICENSE: method "text", a score and
# a similarity

# A package's license field: what did its author declare?
match("GPLv2 or later")["expression"]
# "GPL-2.0-or-later", with category, trust and the steps that read it
```

Use `detect()` to scan files; use `match()` to record what a package
declares, as an SBOM tool does. `licenseid.detect()` uses a
`LicenseDetector` on the database at the default path, kept while that file
is unchanged; make your own `LicenseDetector(db_path)` for another database.

You can use `licenseid` directly in your Python projects:

```python
from licenseid import LicenseDetector

# Initialize with default database
detector = LicenseDetector()

# 1. Detect by Raw Text (Positional or Keyword)
# Programmatic API is explicit: positional 'text' is always treated as text.
results = detector.detect("Permission is hereby granted...")
results = detector.detect(text="Custom license text...")

# 2. Detect by SPDX License ID (Explicit)
# This performs a fast database lookup and returns full metadata.
results = detector.detect(license_id="MIT")

# 3. Detect by File Path (Explicit)
# The file is read as the CLI reads it: UTF-8, else Latin-1 with a warning;
# binary data raises licenseid.InvalidInputError.
results = detector.detect(file_path="LICENSE.txt")

# 4. Predicates: the same one input, named as for detect()
if detector.is_osi(license_id="MIT"):
    print("OSI Approved!")

# OSI-approved or FSF-libre; None means an operand could not be judged
if detector.is_osi(file_path="LICENSE.txt") or detector.is_fsf(
    file_path="LICENSE.txt"
):
    print("Open Source!")

if detector.is_spdx(text="Creative Commons Zero v1.0 Universal"):
    print("SPDX Match Found!")
```

`detect()` takes exactly one input, `text`, `license_id` or `file_path`:
none, or two, raise `licenseid.InvalidInputError` (a `RuntimeError`); a
`text` or `license_id` that is not a `str` raises `TypeError`, and a
`file_path` that cannot be read raises `OSError` (such as
`FileNotFoundError`). `is_osi()`, `is_fsf()` and `is_spdx()` take the same
inputs and no options; `is_osi()` and `is_fsf()` return `None` when an
operand of the expression cannot be judged.

`detect()` takes the keyword options `enable_popularity`, `exclude`, `hint`,
`only_common` and `only_spdx`, and raises `licenseid.InvalidInputError`
for any other, such as a mistyped name. The options shape the
ranking of license text; an explicit `license_id`, a bare ID or name and an
`SPDX-License-Identifier` tag are answered before they are read.

To record a licence a package *declares* (a `license` field, a model card),
use `licenseid.match()`. It returns the SPDX expression and each step taken,
so a caller can tell a changed case from a re-spelt ID. A bare deprecated ID
such as `GPL-3.0` is never narrowed to `-only`: it comes back as written
(category `assumed_only`) with both candidates.

`match()` needs no database. With none given (`source="auto"`, the
default), it reads the database at the default path or the SPDX License List
shipped in the wheel, whichever holds the newer List; a tie goes to the
database only if this licenseid's build rules made its rows (not those of an
older or a newer licenseid). With no database file it reads
the shipped list; with a database that is there but unusable, the shipped
list after one `WARNING: database: <condition>: <detail>; using packaged data
v<version>` on standard error. `source="database"` reads only the database
(and raises for one that cannot answer, as `auto` would call it unusable) and
`source="packaged"` only the shipped list; `match(value, db)` reads `db`,
a `LicenseDatabase` or the path of one (a `str` or `os.PathLike`), opened
read-only: a missing file raises `DatabaseNotReadyError` (`not found`) and
is not created. Every database is checked ready before it is read, once
while its file is unchanged. A value that is not a `str`, and a `db` that
is neither, raise `TypeError`.
The answer is the same from either, and `lists[*].source` says which was
read. `licenseid.DatabaseNotReadyError` is raised only when the chosen
list cannot be read: with `auto`, when there is neither (an editable install
ships no list).
The choice is kept while the database file is unchanged (one `stat` per
call, no connection to choose), so a loop over many values is fast. A new,
deleted or updated file is seen at the next call, unless the file system
keeps coarse times (FAT, HFS+) and the update keeps the file's size within
one tick.

```python
from licenseid import match

r = match("Apache2")
r["expression"]  # "Apache-2.0"
r["category"]    # "version_spelling"
[s["kind"] for s in r["steps"]]  # ["separator", "version_spelling"]
r["resolver"]["purl"]  # who resolved it
r["lists"][0]["version"]  # from which list version
r["lists"][0]["source"]  # read from the "database" or the "packaged" list
```

The whole result, its categories and their trust, the reasons for a
refusal, licences joined by a `;` (`r["operands"]` lists each) and how quote
marks are read are in [docs/match.md][match-doc].
`licenseid match VALUE` prints the same result on the command line
([Match a declared value](#3-match-a-declared-value)), and
`licenseid match --json VALUE` prints the line that
`licenseid.json_line(match(VALUE))` returns. The types of a result are
exported too: `licenseid.Resolution`, `Category`, `Trust`, `Step`,
`Operand`, `ListInfo`, `ListSource`, `Source`, `Detection` and `Method`.
`licenseid.LicenseDatabase` is an opaque handle, to open once and pass to
`match(db=...)` or `LicenseDetector`.

`detect()` and `match()` both say `exact`, and the two can differ:
`detect()`'s `exact` is per result, true when that answer was found
exactly (declared, a name in full, or the whole text); `match()`'s `exact`
is a category, the value written as the ID itself, with no step at all.
`detect GPL-2.0` is `GPL-2.0-only`, not exact (a guess); `match("GPL-2.0")`
is `GPL-2.0`, `assumed_only`. Routing `detect()`'s declared values through
`match()` is planned for 0.8. A compound (`MIT OR Apache-2.0`) has empty
top-level `candidates`; each operand's are in `operands[*].candidates`.

[match-doc]: https://github.com/bact/licenseid/blob/main/docs/match.md
[match-doc-reads]: https://github.com/bact/licenseid/blob/main/docs/match.md#what-match-reads

The constructor raises `licenseid.DatabaseNotReadyError` (a `RuntimeError`)
when the database is missing, empty, invalid (another program's file) or
unreadable, for example before the first `licenseid update`; its `condition`
(`not found`, `empty`, `invalid`, `unreadable`) and `detail` say which, apart
from the message. So does any later
call, such as `detect()`, if the file is deleted, truncated or damaged in the
meantime; then the `sqlite3` error is its `__cause__`. A lookup creates
nothing and writes nothing, except that the constructor adds what a database of
an earlier version lacks. A database that an earlier version built is in WAL
mode, and SQLite then leaves `-shm` and `-wal` files beside it until the next
`licenseid update`.

`licenseid.get_default_db_path()` returns the path used when none is given
(it raises `DatabaseNotReadyError` when the account has no home directory).

Each result is a `licenseid.Detection` with the same keys, `expression`,
`method` (a `licenseid.Method`), `exact`, `score`, `similarity`, `coverage`,
`is_spdx`, `is_osi_approved` and `is_fsf_libre`, as in the CLI's output
above; `similarity` and `coverage` are `None` where nothing was measured.
For `detect(text="MIT")`:

```python
[
    {
        "expression": "MIT",
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

Run benchmarks and accuracy tests (expensive; CI runs them weekly and when
the matching code changes):

```bash
pytest --run-benchmark
```

## License

Apache-2.0

## Citation

If you use this software, please cite it as follows:

> Suriyawongkul, A. (2026). LicenseID - A Portable SPDX License ID Matcher
> (Version 0.7.0) [Computer software].
> <https://doi.org/10.5281/zenodo.19881009>

BibTeX:

```bibtex
@software{Suriyawongkul_LicenseID_-_A_2026,
    author = {Suriyawongkul, Arthit},
    doi = {10.5281/zenodo.19881009},
    license = {Apache-2.0},
    month = oct,
    title = {{LicenseID - A Portable SPDX License ID Matcher}},
    url = {https://github.com/bact/licenseid.git},
    version = {0.7.0},
    year = {2026}
}
```
