---
Created: 2026-10-28
Last-Modified: 2026-10-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Evidence for the 0.7.0 resolver

See also: [`expression-resolution.md`](expression-resolution.md) (the design
this feeds).

What `resolve()` 0.6.0 does on licence values that real packages declare,
beside what Pitloom 0.21.0 does with them itself. Input to the 0.7.0 plan; no
code changes here.

## Method

57 distinct declared values, taken from the `License-Expression`, `License`
and `Classifier` fields of 164 installed distributions' `METADATA` and 21
sdists' `PKG-INFO`, plus `pyproject.toml` (`license`, `license.text`,
classifiers, Poetry `license`) and `setup.cfg` `license` of those sdists and
of Pitloom's test projects. A further 26 synthetic values cover the gaps named
in the design (compounds, deprecated ids, prose). Each value went through
`licenseid.resolve()` (0.6.0, database 3.29.0), through Pitloom's own reading
(`classify_license`, which calls `resolve()` for a single value and
`py-spdx-license` for compounds) and through `normalize_identifier()`.

## Real values (57)

| `resolve()` category | Pitloom result | Count |
| - | - | - |
| `exact` | an expression | 23 |
| `expression` (a compound, no expression returned) | an expression, Pitloom's own parse | 6 |
| `listed_name` | an expression | 5 |
| `separator` (`Apache 2.0`) | an expression | 1 |
| `unresolved` | text | 22 |

Of the 22 unresolved, 5 are whole licence texts in `License:` (out of scope
for `resolve()`; a consumer filters them). The other 17 are short values:

| Value | Field | Why it stays unresolved |
| - | - | - |
| `MIT License (MIT)` (2 fields), `ISC License (ISCL)`, `Mozilla Public License 2.0 (MPL 2.0)` | classifier, `License`, `license.text` | a trailing parenthesised short name after a listed name |
| `GNU Lesser General Public License v3 or later (LGPLv3+)` | classifier | a listed name with "or later" and a trailing short name |
| `Apache Software License`, `BSD License` | classifier, `License` | the trove names of a family: Apache-2.0 is the usual meaning, not a stated one |
| `Python Software Foundation License`, `PSFL` | classifier, `License` | PSF-2.0 is the List id; neither spelling is a name or an alias |
| `Expat license` | `License` | an SPDX alternative name of `MIT` |
| `3-Clause BSD License` | `License` | a spelling of `BSD-3-Clause` with a leading count |
| `BSD`, `Dual License` | `License` | several licences or none: correctly unresolved |
| `Public Domain`, `Public domain` | classifier, `License` | no SPDX id; correctly unresolved |
| `OSI Approved` | classifier | a trove category, not a licence: correctly unresolved |

## Synthetic values: where the three readers differ

| Value | `resolve()` | Pitloom | `normalize_identifier()` |
| - | - | - | - |
| `MIT OR ISC OR MIT OR ISC` | `expression`, none | `ISC OR MIT` | unchanged (its `sort()` fails) |
| `GPL-3.0 OR MIT` | `expression`, none | as written | `GPL-3.0-only OR MIT` (narrows) |
| `StandardML-NJ` | `SMLNJ` (renamed) | as written | as written |
| `Apache2 OR MIT` | `expression`, none | text | `MIT OR Apache2` (keeps the unresolved operand) |
| `GPLv3+ OR MIT` | `expression`, none | text | unchanged |
| `GNU General Public License v3 or later (GPLv3+)` | unresolved | text | `... v3 OR later ...` (prose "or" upper-cased) |
| `Apache License, Version 2.0` | unresolved | text | unchanged |
| `The MIT License (MIT)` | unresolved | text | unchanged |
| `MIT/Apache-2.0`, `MIT OR Foo`, `MIT AND`, `(MIT` | unresolved | text | unchanged |
| `GPL-2.0+ OR MIT` | `expression`, none | `GPL-2.0-or-later OR MIT` | same |
| `Apache-2.0 WITH LLVM-exception`, `(MIT OR Apache-2.0) AND BSD-3-Clause` | `exact` / `expression` | as written, sorted | same |

## What this says for the plan

1. **Compounds are the largest single gap.** 6 of the 57 real values are
   compounds and every one is answered by Pitloom's own parser, not by
   `resolve()`. Operands must be resolved first and the result canonicalised
   second: `normalize_identifier()` on the whole value upper-cases the "or" of
   prose and keeps unresolved operands, so it cannot be the first step.
2. **Prose with a trailing short name** (`MIT License (MIT)`, `ISC License
   (ISCL)`, `... (MPL 2.0)`, `... (LGPLv3+)`) is 4 of the 17 unresolved short
   values and common on PyPI. A step that drops a trailing parenthesis when
   the head resolves, naming what it dropped (the design's `drop` step), would
   read all four.
3. **Trove classifier names are a closed vocabulary** (about 80 `License ::`
   entries). A table with its ambiguity flags (`Apache Software License` is
   `Apache-2.0` by usage, not by statement; `BSD License` is several) would
   serve the classifier route without guessing in free text. Needs a decision
   on what an assumed reading is called in `trust`.
4. **Alternative names and aliases** (`Expat license`, `PSFL`, `3-Clause BSD
   License`, `Apache License, Version 2.0`) are lexical: check whether the
   List's `otherNames` and the common prose forms belong in the lexical
   table.
5. **A consumer still needs its own filters**: whole licence texts, trove
   categories (`OSI Approved`), `UNKNOWN`. None belongs in `resolve()`.
6. **Behaviours to pin as tests in 0.7.0**: the `sort()` failure on repeated
   terms, the narrowing of a bare deprecated id, `StandardML-NJ` to `SMLNJ`,
   the unresolved-operand handling, and the "or" of prose.

## Not yet collected

- Frequency: the corpus is 57 distinct values, not their counts across PyPI. A
  sample of PyPI metadata would rank items 2 to 4.
- The same table for package-lock, Cargo and npm `license` fields.
- `resolve()` timing on a compound of many operands (the design's budget is 1
  ms per leaf).
