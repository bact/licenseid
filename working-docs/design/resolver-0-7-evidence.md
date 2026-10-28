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

## PyPI sample: how often each case occurs

The top 5,000 projects by downloads (hugovk's `top-pypi-packages` list of
2026-10-01); `info.license`, `info.license_expression` and the `License ::`
classifiers of each project's latest release from the PyPI JSON API, fetched
on 2026-10-28. 4,999 answered. The value a consumer would use is the first of
`License-Expression`, a short `License`, the classifiers.

| Source used | Projects |
| - | - |
| `License` (short, one line) | 2,494 |
| `License-Expression` | 1,571 |
| `License ::` classifiers only | 692 |
| none, or `UNKNOWN` | 205 |
| a long or multi-line `License` text only | 37 |

Of the 4,757 projects with a short value, `resolve()` 0.6.0 answers:

| Answer | Projects | Share |
| - | - | - |
| one id (`exact`, `listed_name`, `separator`, `version_spelling`, `plus_to_or_later`, `lexical`) | 3,796 | 79.8% |
| `unresolved` | 848 | 17.8% |
| `expression` (a compound, no expression returned) | 63 | 1.3% |
| `assumed_only` (a deprecated id, `-only` or `-or-later` unknown) | 40 | 0.8% |
| several classifiers | 9 | 0.2% |

The 848 unresolved short values, by what would resolve them (a first reading
of each value, not a tested rule set):

| Group | Projects | Share | Examples (projects) |
| - | - | - | - |
| A bare or family name: more than one licence | 348 | 41% | `BSD License` (155), `BSD` (150), `Apache` (14), `LGPL` (8) |
| A trove classifier name | 231 | 27% | `Apache Software License` (153), `Python Software Foundation License` (14), `Other/Proprietary License` (13), `ISC License (ISCL)` (8) |
| A prose form of one id | 139 | 16% | `Apache License, Version 2.0` (31), `Apache-2.0 license` (18), `BSD 3-Clause License` (13), `Apache License Version 2.0` (9) |
| Other | 61 | 7% | `Apache Software License 2.0` (8), `LGPL with exceptions` (2), `FreeBSD` (2) |
| Proprietary or custom | 35 | 4% | `NVIDIA Proprietary Software` (13), `LICENSE.txt` (3) |
| An alias or abbreviation | 14 | 2% | `PSF` (5), `Expat license` (3), `ISCL` (3) |
| A trailing parenthesis after a name | 12 | 1% | `The Unlicense (Unlicense)` (4) |
| A full trove path in `License` | 8 | 1% | `License :: OSI Approved :: Apache Software License` (4) |

Weighted by downloads, the compounds matter more than their count: the 63
carry about 6.6 billion downloads in the sample (`MIT OR Apache-2.0`,
`Apache-2.0 AND MIT` on widely installed projects), against 7.3 billion for
the 504 unresolved `License` values and 6.6 billion for the 344 unresolved
classifier names.

## What this says for the plan

1. **Compounds are a small share of projects (1.3%) but a large share of
   downloads.** 6 of the 57 values in the first corpus are compounds, and
   every one is answered by Pitloom's own parser, not by `resolve()`. Operands
   must be resolved first and the result canonicalised second:
   `normalize_identifier()` on the whole value upper-cases the "or" of prose
   and keeps unresolved operands, so it cannot be the first step.

2. **Prose forms of one id are the safest gain: 16% of the unresolved
   values.** `Apache License, Version 2.0`, `Apache-2.0 license`, `BSD
   3-Clause License` and `Apache License Version 2.0` state one id; they are
   lexical rules, not assumptions.

3. **Prose with a trailing short name** (`MIT License (MIT)`, `ISC License
   (ISCL)`, `... (MPL 2.0)`, `... (LGPLv3+)`) is 4 of the 17 unresolved short
   values of the first corpus, but about 1% of the PyPI sample's (the trove
   forms in item 4 carry most of it). A step that drops a trailing parenthesis when
   the head resolves, naming what it dropped (the design's `drop` step), would
   read all four.

4. **Trove classifier names are a closed vocabulary** (about 80 `License ::`
   entries; 27% of the unresolved values, mostly `Apache Software License`). A
   table with its ambiguity flags (`Apache Software License` is `Apache-2.0`
   by usage, not by statement; `BSD License` is several) would serve the
   classifier route without guessing in free text. Needs a decision on what an
   assumed reading is called in `trust`.

5. **Alternative names and aliases** (`Expat license`, `PSFL`, `3-Clause BSD
   License`, `Apache License, Version 2.0`) are lexical: check whether the
   List's `otherNames` and the common prose forms belong in the lexical table.

6. **A consumer still needs its own filters**: whole licence texts, trove
   categories (`OSI Approved`), `UNKNOWN`. None belongs in `resolve()`.

7. **Behaviours to pin as tests in 0.7.0**: the `sort()` failure on repeated
   terms, the narrowing of a bare deprecated id, `StandardML-NJ` to `SMLNJ`,
   the unresolved-operand handling, and the "or" of prose.

## Not yet collected

- Frequency beyond the top 5,000 projects, and across releases (the sample is
  each project's latest release).
- Rules tested against the 848: the groups above are a first reading by
  pattern; each rule needs a run against the sample before it is promised.
- The same table for package-lock, Cargo and npm `license` fields.
- `resolve()` timing on a compound of many operands (the design's budget is 1
  ms per leaf).
