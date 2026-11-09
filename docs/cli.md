---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Command line reference

Every command of `licenseid`: `update`, `detect`, `resolve`, `clear-cache`
and the `is-*` predicates, with their options, inputs and exit codes. The
format of what they print is in [output.md](output.md). The
[README](../README.md) has a quick start.

## Update the licence database

Before matching, you need to build the local licence index:

```bash
licenseid update
```

Progress and warnings go to standard error; standard output carries only the
result, one line per list (`--json`: one JSON object per list):

```text
LIST=spdx-license-list	VERSION=3.29.0	STATUS=updated	PATH=/home/me/.local/share/licenseid/licenses.db
```

`LIST` is the list, by the ID `resolve()` gives it in `lists[*].id`;
`VERSION` is the release the database now holds; `STATUS` is `updated`, or
`unchanged` when the database already had that release.

Advanced update options:

- `--list <id>[@<version>]`: The list to install, and its release
  (`--list spdx-license-list@3.29.0`); without a version, the latest.
  Repeatable; with none, every list licenseid installs, at its latest
  release (today one: `spdx-license-list`). A release given is fetched
  without asking which release is the latest. An ID licenseid does not
  install, a version that is not a release number (`3`, `v3.29.0`) and a list
  named twice exit 2.
- `--force`: Force update even if the local database is already at
  the target version.
- `--no-cache`: Bypass the local cache for downloads.
- `--source auto|compact|upstream|packaged`: Where the licence data comes
  from. `auto` (default) tries `compact`, then `upstream`, then `packaged`;
  the other values use that one source only.
  - `compact`: our bundle of about 1 MB (JSON and licence texts, no XML), from
    `raw.githubusercontent.com`, so `licenseid update` works where only that
    host is reachable.
  - `upstream`: SPDX's own release tarball on GitHub (about 49 MB).
  - `packaged`: the bundle shipped in the package: the SPDX License List
    pinned for that release (3.29.0 for 0.8.3). `licenseid update` still
    works with no network, with data that may be older.

## Detect a licence, or resolve a declared value

Two commands answer two questions (as `detect()` and `resolve()` do in the
[Python API](python-api.md)):

```bash
# Which licence is in this file? The SPDX expression, e.g. Apache-2.0.
licenseid detect LICENSE.txt

# Which SPDX expression does this declared value stand for? The expression,
# or an empty line for a refusal; no database needed.
licenseid resolve "GPLv2 or later"

# The detail behind either answer (score, steps, reason): add -v.
licenseid detect -v LICENSE.txt
licenseid resolve -v "GPLv2 or later"
```

By default both print the SPDX expression alone, one line (an empty line
when there is no answer; exit 1). `-v` / `--verbose` prints the full
record, as [Output formats](output.md) describes. `-V` prints the
version.

`detect` identifies licence text from a file, an ID, or a string:

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
text. A URL, with or without its scheme, and licence IDs joined by `/`
(`MIT/Apache-2.0`) are not paths. Use `--text` to match any value as text.

Input is read as UTF-8. Text that is not valid UTF-8 is read as Latin-1,
with a warning on standard error; binary data is rejected (exit code 2).

Common options:

- `--db <path>`: Use a custom database path (global option).
  Supports SQLite URIs for in-memory databases
  (e.g., `file:test?mode=memory&cache=shared`).
- `--id <id>`: Explicitly treat input as one SPDX License ID (bypasses
  file/text matching). It declares a single licence, so it takes an ID, a
  `LicenseRef-*`, an ID with `+` (a `LicenseRef-*` takes none, nor does an
  ID that ends in `-only` or `-or-later`), and either
  `WITH <exception>`, in
  brackets or not: `MIT`, `(MIT)`, `Apache-2.0+`,
  `MIT WITH Font-exception-2.0`, `spdx:MIT` (the SPDX prefix). It does not take
  an `AND`/`OR` expression, a licence name, a URL
  (`https://spdx.org/licenses/MIT`) or prose — those name no single
  licence, so they exit 2 with
  `ERROR: option: invalid: --id: <value>; pass one license ID`. A file's tag
  may still hold any expression. Input that is, as a whole, one declared
  value, whether an argument, `--text`, standard input or a file, is read
  by `resolve()` (`--text GPL-2.0+` is `GPL-2.0-or-later`, `MIT OR ISC` is
  `ISC OR MIT`); anything else is matched as text from 10 words on
  (Chinese and Japanese at any length), unless a licence name matches it:
  `MIT but modified heavily by us` has no answer, not MIT.
  An argument that names no file is first checked for the shape of a path
  (see above). A value that is no licence, such as `GPL-2.0-only+` (a "+"
  after a stated qualifier), is a "no" as text (exit 1, and `detect()`
  returns no result; so is a short text with a "+" that is no operator, such
  as `"MIT++"` or `MIT License++`) and a usage error as `--id` (exit 2).
- `--text <text>`: Match the given text, taken as written: a backslash is
  a backslash (`C:\temp\new` is that path), and `\n` is two characters.
  For a line break, pass one (`--text "$(printf 'a\nb')"`) or pipe the
  text.
- `-v`, `--verbose`: Print the full record of each result ([output.md](output.md)),
  not the expression alone. It changes nothing with `--json`, which always
  prints the full record.
- `--diff`: Show a word-by-word diff between the input and the top
  result, when it was matched as text and is not exact, on standard error.
  An exact result has no diff, so `--diff --exact` prints none.
- `--json`: Output results as JSON Lines ([output.md](output.md#json)). It
  does not take `--diff`: both exit 2.
- `--threshold <score>`: Keep results that score at least this, from 0 to
  1 (default 0.85). A value outside 0 to 1 exits 2.
- `--top <n>`: Keep at most this many results (default 3); below 1 exits 2.
- `--exact`: Keep only exact results (`EXACT=true`, see [output.md](output.md)).
- `--pop/--no-pop`: Weigh results by popularity, or not (default off).

The system uses a **composite score** (similarity + coverage bonus/penalty +
optional popularity weight + marker confidence boost) to prefer the tightest
match. For example, it distinguishes a short permissive licence from a
superset that shares the same preamble.

## Resolve a declared value

`licenseid resolve VALUE` reads one value that someone wrote to declare a
licence (a `license` field, a trove classifier) with `resolve()`, and prints
the expression, or an empty line (exit 1) when the value resolves to none.
With `-v` it prints the whole resolution, one data point per line:

```console
$ licenseid resolve "GPLv2+ or MIT"
GPL-2.0-or-later OR MIT
$ licenseid resolve -v "GPLv2+ or MIT"
EXPRESSION=GPL-2.0-or-later OR MIT	CATEGORY=version_spelling	TRUST=resolver_rule
STEP=separator	FROM=GPLv2	TO=GPL-2.0
STEP=version_spelling	FROM=GPLv2	TO=GPL-2.0
STEP=operator_case	FROM=GPL-2.0-or-later or MIT	TO=GPL-2.0-or-later OR MIT
STEP=plus_to_or_later	FROM=GPLv2+	TO=GPL-2.0-or-later
```

- The first line is the answer: `EXPRESSION=` is empty when the value
  resolves to no expression. Why it did not (`REASON=`) is only in the
  verbose lines. Its category and trust are those of
  [resolve.md](resolve.md).
- `STEP=` lines are the steps applied, in order, then the qualifiers
  (`-or-later`) applied; a step that was declined is not printed.
- `REASON=` says why a value was refused (`character dropped: U+003F`).
- `OPERAND=`, `EXPRESSION=` and `CATEGORY=` lines follow for licences
  joined by `;` (`MIT ; Apache 2`), which say no operator.
- The fields are separated by one tab, as in `detect`'s lines
  ([Output formats](output.md)); read them with `cut -f` or
  `awk -F'\t'`. `--json` prints the whole result instead, as one RFC 8785
  object: `licenseid resolve --json "$v" | jq -r .expression`.

Options:

- `-v`, `--verbose`: the full resolution as the lines above, not the
  expression alone. No effect with `--json`.
- `--json`: the whole result of `resolve()`, as one JSON object.
- `--source auto|database|packaged`: the list read when `--db` is not
  given, as `resolve(source=...)` reads it (default `auto`: the database at the
  default path or the list shipped with licenseid, whichever is newer).
- `--db <path>` (global option): read that database, as `resolve(value, db)`;
  `--source packaged` with it exits 2.

`resolve` reads a declared value, not a licence text, so it refuses what only
`detect` answers, with exit 2, nothing on standard output and
`; run 'licenseid detect'`: `--text`, `-` (standard input), a
value with a line break, and one over 2,000 characters once its surrounding
white space is trimmed. A value that resolves is answered even when a file
of that name exists (`resolve MIT` beside a file `MIT`); one that resolves to
nothing and names an existing file or directory (`resolve LICENSE`) is
refused. An empty argument is a usage error too (`input: empty: argument`),
as is no argument (`input: missing; pass one declared licence value`):
`resolve` never reads standard input, so a pipe that stays open cannot hold
it. Exit 0 means the value resolved to an expression (`GPL-3.0`, kept as
`assumed_only`, included), 1 that it did not (a list joined by `;` included),
with no `ERROR` line.

`detect` and `resolve` answer different questions, so their answers to one
value can differ:

| Command | Prints | Means |
| :--- | :--- | :--- |
| `detect -v GPL2` | `EXPRESSION=GPL-2.0-only`, `EXACT=false`, with `WARNING: input: variant not stated` | the closest licence on the list, a guess said aloud |
| `resolve -v GPL2` | `EXPRESSION=GPL-2.0`, `CATEGORY=assumed_only` | what was declared, kept as written: no guess |

## Cache management

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

## Licence predicates

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
and `X WITH Y` as `X` is. An operand that cannot be judged (a
`LicenseRef-*`, an ID not on the List) counts as unknown: an `OR` with a
true operand is still true, and an `AND` with a false one still false. The
flag is empty (`null` in JSON), exit 1, when there is nothing to judge,
never a false "no": the input names no licence (`EXPRESSION` is empty too),
or the unknown operand decides the answer:

```console
$ licenseid is-osi --text "SPDX-License-Identifier: MIT OR LicenseRef-x"
EXPRESSION=MIT OR LicenseRef-x	IS_OSI_APPROVED=true
$ licenseid is-osi --text "SPDX-License-Identifier: MIT AND LicenseRef-x"
EXPRESSION=MIT AND LicenseRef-x	IS_OSI_APPROVED=
```

| Command | Key | Description |
| :--- | :--- | :--- |
| `is-spdx` | `IS_SPDX` | True if every licence and exception ID is on the SPDX License List (a `LicenseRef-*` is not). |
| `is-osi` | `IS_OSI_APPROVED` | True if the licence is OSI-approved. |
| `is-fsf` | `IS_FSF_LIBRE` | True if the licence is FSF-libre. |

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

## Exit codes

The CLI follows standard Unix exit code conventions,
making it suitable for use in scripts and CI/CD pipelines.

| Exit Code | Meaning | Scenarios |
| :--- | :--- | :--- |
| **0** | Success | Confident match found; `resolve`: the value resolved to an expression; predicate is TRUE; database updated or already up-to-date; cache cleared or nothing to clear. |
| **1** | Logic Failure | No matching licence found (an empty line; with `-v` one record, every field empty); `resolve`: no expression (an empty line; `-v` prints the resolution); predicate is FALSE, or cannot be judged (its record still printed); an update or a cache clear that failed (a network error, a delete the system refuses). |
| **2** | Usage or Setup Error | Missing subcommand (help on standard error); missing input text/file; two inputs; `--json` with `--diff`; invalid parameters; `resolve` given a text, `-`, or a path that resolves to nothing; database not ready (for `resolve`, no list to read); output that cannot be written. |
| **130** | Interrupted | Ctrl-C (SIGINT); no message once started. |
| **141** | Reader gone | The reader closed the pipe (`head -1`); no message. |

Exit 1 of `detect`, `resolve` and the `is-*` commands prints no `ERROR` line.
A `WARNING` about the input or the database can still come with it, as with
an answer: `detect --exact GPL-2.0` says `variant not stated` and finds no
exact match.

A database is not ready when it is missing, empty (no licences yet), invalid
(another program's file) or unreadable. `detect` and the `is-*` commands refuse
to answer from one, rather than exiting 1 for no licence or `false`;
`resolve` reads the list shipped with licenseid instead, unless `--db` or
`--source database` asks for the database.

`licenseid --version` prints `licenseid <version>`.
