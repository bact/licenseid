---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# The Python API

How to call `licenseid` from Python: `detect()` and `LicenseDetector`, the
predicates, `match()`, the results, errors and warnings. The
[README](../README.md#python-api) gives the overview; [match.md](match.md)
describes every field of `match()`'s result.

`licenseid.detect()` uses a
`LicenseDetector` on the database at the default path, kept while that file
is unchanged; make your own `LicenseDetector(db_path)` for another database:

```python
from licenseid import LicenseDetector

detector = LicenseDetector()  # on the database at the default path

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

`detect()` applies no threshold and no top: it returns every candidate it
ranks (dozens for a LICENSE file), best first. Filter on `score` and
`exact` yourself; the `is_*()` predicates use a bar of 0.85.

`detect()` takes the keyword options `enable_popularity`, `exclude`, `hint`,
`only_common` and `only_spdx`, and raises `licenseid.InvalidInputError`
for any other, such as a mistyped name. The options shape the
ranking of licence text; an explicit `license_id`, a bare ID or name and an
`SPDX-License-Identifier` tag are answered before they are read.

To record a licence a package *declares* (a `license` field, a model card),
use `licenseid.match()`. It returns the SPDX expression and each step taken,
so a caller can tell a changed case from a re-spelt ID. A bare deprecated ID
such as `GPL-3.0` is never narrowed to `-only`: it comes back as written
(category `assumed_only`) with both candidates.

`match()` needs no database, with an installed wheel (an editable install
ships no list). With none given (`source="auto"`), it reads the
database at the default path or the List shipped in the wheel, whichever is
newer; `source=` picks one, and `match(value, db)` reads `db`, a
`LicenseDatabase` or its path ([how it chooses][match-doc-list]).

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
([Match a declared value](../README.md#3-match-a-declared-value)), and
`licenseid match --json VALUE` prints the line that
`licenseid.json_line(match(VALUE))` returns. The types of a result are
exported too: `licenseid.Resolution`, `Category`, `Trust`, `Step`,
`Operand`, `ListInfo`, `ListSource`, `Source`, `Detection` and `Method`.
`licenseid.LicenseDatabase(path)` is an opaque handle, to open once and pass
to `match(db=...)` or `LicenseDetector`. It refuses a file licenseid did not
build (`DatabaseNotReadyError`, condition `invalid`), whatever `create` is. A
missing file is made by the first write (`update`), not by opening or
reading it: `match(value, handle)` on a missing file raises `not found`.

`detect()` and `match()` both say `exact`, and the two can differ:
`detect()`'s `exact` is per result, true when that answer was found
exactly (declared, a name in full, or the whole text); `match()`'s `exact`
is a category, the value written as the ID itself, with no step at all.
`detect GPL-2.0` is `GPL-2.0-only`, not exact (a guess); `match("GPL-2.0")`
is `GPL-2.0`, `assumed_only`. Routing `detect()`'s declared values through
`match()` is planned for 0.8. A compound (`MIT OR Apache-2.0`) has empty
top-level `candidates`; each operand's are in `operands[*].candidates`.

[match-doc]: https://github.com/bact/licenseid/blob/main/docs/match.md
[match-doc-list]: https://github.com/bact/licenseid/blob/main/docs/match.md#which-list-and-its-warnings

`licenseid.LicenseIdError` (a `RuntimeError`) is the base of
`licenseid.InvalidInputError` and `licenseid.DatabaseNotReadyError`. The
`LicenseDetector` constructor raises `DatabaseNotReadyError` when the
database is missing, empty, invalid (another program's file) or unreadable,
for example before the first `licenseid update`; its `condition` (`not found`,
`empty`, `invalid`, `unreadable`) and `detail` say which, apart from the
message, and are `None` when nothing was said. A `file_path` or `db_path`
takes a `str` or an `os.PathLike[str]`; any other type raises `TypeError`.
Any later call, such as `detect()`, raises `DatabaseNotReadyError` too if the
file is deleted, truncated or damaged in the meantime; then the `sqlite3`
error is its `__cause__`. A lookup creates nothing and writes nothing, except
that the constructor adds what a database of an earlier version lacks. A
database that an earlier version built is in WAL mode, and SQLite then leaves
`-shm` and `-wal` files beside it until the next `licenseid update`.

`licenseid.get_default_db_path()` returns the path used when none is given
(or raises `DatabaseNotReadyError` for an account with no home directory).

Each result is a `licenseid.Detection` with the same keys, `expression`,
`method` (a `licenseid.Method`), `exact`, `score`, `similarity`, `coverage`,
`is_spdx`, `is_osi_approved`, `is_fsf_libre` and `lists`, as in the CLI's
output above; `similarity` and `coverage` are `None` where nothing was
measured. `lists` names the list the answer rests on, in the shape of
`match()`'s `lists` (a `licenseid.ListInfo`): the database's SPDX License
List, its `version`, `source` `"database"`. For `detect(text="MIT")`:

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
        "lists": [...],  # one ListInfo: the database's SPDX License List
    }
]
```

## Warnings

licenseid warns through Python's `warnings` module, never by writing to
standard error: a guess said aloud (`input: variant not stated: GPL-2.0;
using GPL-2.0-only`), an outdated database, Latin-1 input, a fallback to the
shipped list or a cached file. Each is a `licenseid.LicenseIdWarning` (a
`UserWarning`), its text the line the CLI prints after `WARNING:`, its
parts the attributes `subject`, `condition`, `detail` and `action` (`None`
when not stated). Record, silence or raise them as any warning:

```python
import warnings
from licenseid import LicenseIdWarning, detect

with warnings.catch_warnings(record=True) as given:
    warnings.simplefilter("always", LicenseIdWarning)
    detect(text="SPDX-License-Identifier: GPL-2.0")
[(w.message.condition, w.message.action) for w in given]
# [("variant not stated", "using GPL-2.0-only")]

warnings.simplefilter("ignore", LicenseIdWarning)  # or "error" to raise
```

The command line prints each one as a `WARNING:` line on standard error.
