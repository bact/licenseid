---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# The Python API

How to call `licenseid` from Python: `detect()` and `LicenseDetector`, the
predicates, `resolve()`, the results, errors and warnings. The
[README](../README.md) gives the overview; [resolve.md](resolve.md)
describes every field of `resolve()`'s result.

`licenseid.detect()` uses a
`LicenseDetector` on the database at the default path, kept while that file
is unchanged; make your own `LicenseDetector(db_path)` for another database:

```python
from pathlib import Path

from licenseid import LicenseDetector

detector = LicenseDetector()  # on the database at the default path

# 1. Detect by Raw Text (Positional or Keyword)
# Programmatic API is explicit: positional 'text' is always treated as text.
results = detector.detect(Path("LICENSE.txt").read_text())  # a whole text
results = detector.detect(text="Licensed under the MIT license")  # a name

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
if detector.is_osi(file_path="LICENSE.txt") or detector.is_fsf(file_path="LICENSE.txt"):
    print("Open Source!")

if detector.is_spdx(text="Creative Commons Zero v1.0 Universal"):
    print("SPDX Match Found!")
```

`detect()` takes exactly one input, `text`, `license_id` or `file_path`:
none, or two, raise `licenseid.InvalidInputError` (a `RuntimeError`); a
`text` or `license_id` that is not a `str` raises `TypeError`, and a
`file_path` that is missing, is not a regular file, cannot be read, or is
binary raises `InvalidInputError` too (`input: not found: <path>`,
`input: unreadable: <path>: <reason>`, `input: binary file: <path>`).
`is_osi()`, `is_fsf()` and `is_spdx()` take the same inputs and no
options; `is_osi()` and `is_fsf()` return `None` when an operand of the
expression cannot be judged and the others do not decide it
(`MIT OR LicenseRef-x` is `True`, `MIT AND LicenseRef-x` is `None`).

`detect()` applies no threshold and no top: it returns every candidate it
ranks (dozens for a LICENSE file), best first. Filter on `score` and
`exact` yourself; the `is_*()` predicates use a bar of 0.85.

`detect()` takes the keyword options `enable_popularity`, `exclude`,
`hint`, `only_common`, `only_spdx` and `variant`, and raises
`licenseid.InvalidInputError` for any other, such as a mistyped name. A
flag must be a `bool`, and `exclude` and `hint` a list, tuple, set or
frozenset of `str`: any other value raises `TypeError` (a bare `"MIT"`, a
dict, a generator). Every call checks them. All but `variant` (below) act
only where licence text is matched (Tiers 1 and 2): `exclude`,
`only_common` and `only_spdx` drop candidates, `hint` adds candidates (and
those three drop them too), and `enable_popularity` lets popularity nudge the
ranking of every candidate and break its ties. The CLI has no option for
`exclude`, `hint`, `only_common` or `only_spdx`.

So these have no effect on a declaration, an input answered whole: an
explicit `license_id`, a value `resolve()` reads (an ID, a name, an
expression, a licence URL), an `SPDX-License-Identifier` tag, a manifest's
`license` field, or a text under 10 words with no answer. A text with an
`SPDX-License-Identifier: MIT` tag and a GPL body answers MIT, whatever
`exclude` says. They act on free text: the full-text candidates, and what a
title, a version phrase or a section of mixed content names. So
`exclude=["MIT"]` removes MIT from the answers for the MIT License text with
its title.

`exclude` and `hint` compare IDs in any ASCII case (`"mit"` is MIT). A bare
deprecated ID, such as `GPL-2.0` or `AGPL-1.0`, is ambiguous: it stands for
both of its twins (`GPL-2.0-only` and `GPL-2.0-or-later`), and the call warns
`option: deprecated ID: exclude GPL-2.0; using GPL-2.0-only,
GPL-2.0-or-later` (`hint` likewise; once for each ID). A deprecated ID with a
"+", such as `GPL-2.0+`, is its `-or-later` twin, as the List reads a "+": it
warns `option: deprecated ID: exclude GPL-2.0+; using GPL-2.0-or-later`. `hint`
adds the twins only. `exclude` also drops the deprecated forms a title can
still name: the bare ID, and `GPL-2.0+` for `-or-later`, when named or when
both twins are excluded (excluding only `GPL-2.0-only` leaves the ambiguous
bare ID). A deprecated `-with-` ID (`GPL-2.0-with-classpath-exception`) has no
twin, since its successor is an expression: it is taken as written. `exclude`
compares the whole ID, so `exclude=["GPL-2.0-only"]` does not drop the
font-exception candidate `GPL-2.0-only WITH Font-exception-2.0`; name it too.
With `variant="as-written"` a bare ID in `exclude` or `hint` is kept as
written, with no upgrade and no warning (a "+" still reads as `-or-later`);
`exclude` still drops both twins of a bare ID.

`variant` is a `str`, one of `"auto"` (the default), `"as-written"`, `"only"`
and `"or-later"` (another `str` raises `InvalidInputError`, `option: invalid:
variant: ...`; a value that is no `str` raises `TypeError`). Unlike the other
options it acts on every input, as `--variant` does on the command line
([cli.md](cli.md)). It says what to answer for a licence with an `-only` and an
`-or-later` form when the input does not state which. `"auto"` keeps a declared
value as written (`detect(license_id="GPL-2.0")` is `GPL-2.0`, `variant_stated`
`False`, as `resolve()` gives it) and, for a licence text or name, answers
`-or-later` where the input grants later versions of that licence (stated; a
tool's `Python 3.8 or later` grants nothing), else `-only` first
and `-or-later` second, both `variant_stated` `False`, with one `variant not
stated` warning. `-only` is the licensee's careful reading: it understates a
licensor's "or later" grant. `"as-written"` never decides: a bare deprecated ID
stays, in a text match too when the bare row is among its candidates (else as
under `auto`). `"only"` and `"or-later"` always decide, declared values too,
with the warning. The option is a preference, never a fact: words that state the
variant (`GPL-2.0 or later`, `GPL-2.0+`, `-only`, `-or-later`) win over `"only"`
and `"or-later"`, with `option: overridden by input: --variant only; using
GPL-2.0-or-later` (the API names the CLI option too). The API warns for results
scoring 0.85 or more (the CLI: those it prints). `variant_stated` of a result is
`True` when the input states the variant, `False` for a guess or a bare ID kept,
`None` where no licence of the answer has a variant (`MIT`); of a compound
`None` when none has one, `False` when any is `False`, else `True`. `resolve()`
takes no `variant`, and its answers do not change.

A text under 30 words that is no declaration, but names a licence ("released
under the terms of the MIT License"), is free text: `exclude` drops that
name hit too. With no options, `detect()` and `resolve()` agree on a short
value, and a name hit that `resolve()` read is never dropped. `exclude` and
`hint` are `detect()` options that `resolve()` has not, so `detect()` may then
answer differently from `resolve()` on purpose.

After an `exclude`, short prose may still answer a near name, but not a
deprecated ID whose replacement was excluded (except under
`variant="as-written"`): `exclude=["GPL-2.0-only"]` on "licensed under the GNU
General Public License v2.0 only" answers the nearest other licence
(`GPL-1.0-only`), as with both twins excluded. A text under 10 words with
nothing left answers `[]` and warns `too few words for text`. A short text
never uses `hint`: Tier 0 adds no candidates.

`hint` adds each ID it finds in the database as a candidate, after the
others (full-text search, a heading or title, the sections of mixed content),
so a hint never takes the place of the candidate a name or heading added for
the same licence, and never counts towards the five below which `detect()`
searches the sections of mixed content too. An ID given twice, or in another
case, is added once. Every filter wins over a hint: `exclude` drops a hinted
ID, `only_common=True` drops one that is not OSI-approved, FSF-libre or high
usage, and `only_spdx` (on by default) drops one not on the SPDX License List,
so a hint for such a row adds nothing unless `only_spdx=False` is given. A
database built by `licenseid update` holds only List rows, so there
`only_spdx` drops nothing.

The filters do not drop the same candidates. All of them drop a candidate of
full-text search and a hint. `exclude` also drops the candidates a heading,
title or version reading adds and the names found in the sections of mixed
content; `only_common` and `only_spdx` do not: a heading that names a licence
that `only_common` drops from full-text search still answers (the JSON License
text, with `only_common=True`, answers `JSON` first, exact, with or without
`hint=["JSON"]`).

A hinted candidate has its own text, so it ranks on its similarity to the
input, as any candidate does, for the first 50 entries of `hint` (a set in
sorted order; a bare deprecated ID counts as its two twins; an ID given
twice, with no row, or dropped by `exclude`, `only_spdx` or `only_common`
uses no place). Each costs a pass of the
second tier: on the full List the MIT text takes 0.8 s with no hint, 1.6 to
2.0 s with 50 and 3.4 to 3.8 s with 200, and would take about 10 s if all 740
IDs had their text. That is why an entry beyond the fiftieth is added with no
text and scores 0, last. A deprecated row that has no text does too: a bare
`GPL-2.0` (kept as written under `variant="as-written"`), or a `-with-` ID
such as `GPL-2.0-with-classpath-exception`. Under the other variants a bare
deprecated ID stands for its two twins, which have text.

To record a licence a package *declares* (a `license` field, a model card),
use `licenseid.resolve()`. It returns the SPDX expression and each step taken,
so a caller can tell a changed case from a re-spelt ID. A bare deprecated ID
such as `GPL-3.0` is never narrowed to `-only`: it comes back as written
(category `assumed_only`) with both candidates.

`resolve()` needs no database, with an installed wheel (an editable install
ships no list). With none given (`source="auto"`), it reads the
database at the default path or the List shipped in the wheel, whichever is
newer; `source=` picks one, and `resolve(value, db)` reads `db`, a
`LicenseDatabase` or its path ([how it chooses][resolve-doc-list]).

```python
from licenseid import resolve

r = resolve("Apache2")
r["expression"]  # "Apache-2.0"
r["category"]  # "version_spelling"
[s["kind"] for s in r["steps"]]  # ["separator", "version_spelling"]
r["resolver"]["purl"]  # who resolved it
r["lists"][0]["version"]  # from which list version
r["lists"][0]["source"]  # read from the "database" or the "packaged" list
```

The whole result, its categories and their trust, the reasons for a
refusal, licences joined by a `;` (`r["operands"]` lists each) and how quote
marks are read are in [resolve.md](resolve.md).
`licenseid resolve -v VALUE` prints the same result on the command line
([Resolve a declared value](cli.md#resolve-a-declared-value);
without `-v` only `r["expression"]`), and
`licenseid resolve --json VALUE` prints the line that
`licenseid.json_line(resolve(VALUE))` returns. The types of a result are
exported too: `licenseid.Resolution`, `Category`, `Trust`, `Step`,
`Operand`, `ListInfo`, `ListSource`, `Source`, `ToolInfo` (a tool of an
answer: its `resolver` and `components`, each with `name`, `version`, `url` and
`purl`), `Detection` and `Method`, and the types of the options of `detect()`:
`DetectOptions` and `Variant` (the values of `variant`).
`licenseid.LicenseDatabase(path)` is an opaque handle, to open once and pass
to `resolve(db=...)` or `LicenseDetector`. It refuses a file licenseid did not
build (`DatabaseNotReadyError`, condition `invalid`), whatever `create` is. A
missing file is made by the first write (`update`), not by opening or
reading it: `resolve(value, handle)` on a missing file raises `not found`.

`detect()` and `resolve()` both say `exact`, and the two can differ:
`detect()`'s `exact` is per result, true when that answer was found exactly
(declared, a name in full, or the whole text); `resolve()`'s `exact` is a
category, the value written as the ID itself, with no step at all. `detect
GPL-2.0` is `GPL-2.0` as written, exact (`--variant only` reads it as
`GPL-2.0-only`, a guess, not exact); `resolve("GPL-2.0")` is `GPL-2.0`,
`assumed_only`. `detect()` reads a whole input with `resolve()` first and
answers its expression (exact as the `EXACT` column of [the category
table](resolve.md#steps-and-categories) says); `license_id` reads its one ID as
`resolve()` does too (`CC0` is `CC0-1.0`). A tag still has its own reader for
now, which reads no title and no BSD alias (`SPDX-License-Identifier: CC0` and
`SPDX-License-Identifier: BSD-3` have no answer); a manifest field it does not
take (a quoted INI value, a title, a name) is read by `resolve()`. Both read a
licence URL with the reader of `resolve()` (`SPDX-License-Identifier:
https://spdx.org/licenses/MIT` is `MIT`). An input under 10 words that
`resolve()` refuses is not matched as text. A name or an ID can still match it,
except after a dropped mark, an unpaired bracket or a "+" that is no operator
(`MIT++`, `GPL-2.0 (+)`, not `C++`), which `normalize_text` would drop. With no
match it has no result, with the warning `input: too few words for text:
<reason>` (none for an input with no word). Chinese and Japanese, written
without spaces, are matched at any length. A compound (`MIT OR Apache-2.0`) has
empty top-level `candidates`; IDs joined by `/` (`MIT/Apache-2.0`) are read as
`OR`, as `resolve()` does; each operand's are in `operands[*].candidates`.

[resolve-doc-list]: resolve.md#which-list-and-its-warnings

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
`is_spdx`, `is_osi_approved`, `is_fsf_libre`, `lists` and `variant_stated`, as
in the CLI's JSON ([output.md](output.md#json)); `similarity` and `coverage` are
`None` where nothing was measured. `lists` names the list the answer rests on,
in the shape of `resolve()`'s `lists` (a `licenseid.ListInfo`): the database's
SPDX License List, its `version`, `source` `"database"`. For
`detect(text="MIT")`:

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
        "variant_stated": None,  # True, False, or None: no variant to judge
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
    detect(text="SPDX-License-Identifier: GPL-2.0", variant="only")
[(w.message.condition, w.message.action) for w in given]
# [("variant not stated", "using GPL-2.0-only")]

warnings.simplefilter("ignore", LicenseIdWarning)  # or "error" to raise
```

The command line prints each one as a `WARNING:` line on standard error.
