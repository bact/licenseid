---
Created: 2026-10-28
Last-Modified: 2026-10-29
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
| one id (`exact`, `listed_name`, `separator`, `version_spelling`, `plus_to_or_later`, `lexical`) | 3,797 | 79.8% |
| `unresolved` | 848 | 17.8% |
| `expression` (a compound, no expression returned) | 63 | 1.3% |
| `assumed_only` (a deprecated id, `-only` or `-or-later` unknown) | 40 | 0.8% |
| several classifiers | 9 | 0.2% |

The 848 unresolved short values, by what would resolve them (a first reading
of each value, not a tested rule set):

| Group | Projects | Share | Examples (projects) |
| - | - | - | - |
| A bare or family name: more than one licence | 348 | 41% | `BSD License` (155), `BSD` (150), `Apache` (14), `LGPL` (8) |
| A trove classifier name | 224 | 26% | `Apache Software License` (153), `Python Software Foundation License` (14), `Other/Proprietary License` (13), `ISC License (ISCL)` (8) |
| A prose form of one id | 140 | 16% | `Apache License, Version 2.0` (31), `Apache-2.0 license` (18), `BSD 3-Clause License` (13), `Apache License Version 2.0` (9) |
| Other | 63 | 7% | `Apache Software License 2.0` (8), `LGPL with exceptions` (2), `FreeBSD` (2) |
| Proprietary or custom | 35 | 4% | `NVIDIA Proprietary Software` (13), `LICENSE.txt` (3) |
| An alias or abbreviation | 14 | 2% | `PSF` (5), `Expat license` (3), `ISCL` (3) |
| A trailing parenthesis after a name | 16 | 2% | `The Unlicense (Unlicense)` (4) |
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
   values of the first corpus, but about 2% of the PyPI sample's (the trove
   forms in item 4 carry most of it). A step that drops a trailing
   parenthesis when the head resolves, naming what it dropped (the design's
   `drop` step), would read all four.

4. **Trove classifier names are a closed vocabulary** (about 80 `License ::`
   entries; 26% of the unresolved values, mostly `Apache Software License`). A
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

## Reproducing

`python -m tools.pypi_licence_sample fetch` and `analyze` (see
`tools/pypi_licence_sample/README.md`) produce the PyPI tables from a fresh
sample. A new sample will differ from the one above: PyPI and the download
counts move. The first corpus (57 values from installed distributions and
sdists) was collected by hand and is not scripted.

## Not yet collected

- Frequency beyond the top 5,000 projects, and across releases (the sample is
  each project's latest release).
- Rules tested against the 848: the groups above are a first reading by
  pattern (`GROUPS` in the tool); each rule needs a run against the sample
  before it is promised.
- The same table for package-lock, Cargo and npm `license` fields.
- `resolve()` timing on a compound of many operands (the design's budget is 1
  ms per leaf).

## Re-measure on 2026-10-29: 0.6.0 against main

Created 2026-10-29. The earlier sections above stay as they were; this one
measures the rules that followed them (T6 to T9) on the frozen corpus.

### Method and how to rerun

- Corpus: the 462 distinct values of the frozen PyPI sample
  (`tests/fixtures/pypi_values_2026-10.tsv`, the top 10,000 projects of
  2026-10; 9,353 projects with a short value, 124.5 billion downloads) and
  the 141 values of the parity corpus (`tests/fixtures/resolver_parity.tsv`).
  This is a larger sample than the 5,000 projects above, so the counts do not
  compare with the tables above.
- List: SPDX 3.29.0, a fresh database (build v2), opened read only.
- Tool: a scratch script (not in the repository) that reads the fixture rows
  as `tests/resolver_corpus.py` does, calls `licenseid.resolve(value, db)`
  and keeps expression, category, step kinds, trust and reason. One run per
  source tree, with the tree on `PYTHONPATH` and a scratch `HOME`:

  ```shell
  git archive v0.6.0 | tar -x -C "$W/v060"        # one tree per snapshot
  git archive <merge commit> | tar -x -C "$W/<n>"
  HOME="$SCRATCH_HOME" PYTHONPATH="$W/<n>/src" python run.py \
      "$W/<n>/src" licenses-3.29.0.db out-<n>.json <checkout>
  ```

  The script asserts that `licenseid.__file__` lies under the tree. Snapshots:
  `v0.6.0`, and the merge commits of #120, #121, #122, #125, #126, #128, #131
  and `ed9d1b1` (main, after #132). The shorter rerun that needs no script is
  `pytest tests/test_resolver_sample.py`, which fails on any value whose
  answer moved without an `EXPECTED_CHANGES` entry.
- Check: the live 0.6.0 run equals the answers pinned in the fixtures on all
  462 sample values and all 141 parity values (0 differences).
- "Resolved" means the result carries an expression. In 0.6.0 the category
  `expression` (a compound) never carried one.

### Result by category

Values are distinct values; projects and downloads (billions) are summed over
them.

| Category | Values 0.6.0 | Projects 0.6.0 | Downloads 0.6.0 | Values main | Projects main | Downloads main |
| - | - | - | - | - | - | - |
| `exact` | 64 | 5,639 | 91.30 | 94 | 5,681 | 95.66 |
| `listed_name` | 8 | 1,305 | 8.19 | 14 | 1,337 | 8.80 |
| `separator` | 15 | 305 | 3.64 | 14 | 304 | 3.64 |
| `version_spelling` | 15 | 70 | 0.32 | 15 | 70 | 0.32 |
| `assumed_only` | 25 | 124 | 0.24 | 30 | 166 | 0.28 |
| `lexical` | 7 | 10 | 0.01 | 44 | 79 | 2.25 |
| `plus_to_or_later` | 3 | 6 | 0.01 | 3 | 6 | 0.01 |
| `prose_form` | 0 | 0 | 0.00 | 18 | 177 | 1.16 |
| `trove_name` | 0 | 0 | 0.00 | 9 | 41 | 0.21 |
| `expression` (a compound) | 67 | 111 | 6.61 | 0 | 0 | 0.00 |
| `unresolved` | 258 | 1,783 | 14.16 | 221 | 1,492 | 12.14 |
| Resolved (an expression) | 137 | 7,459 | 103.70 | 241 | 7,861 | 112.32 |
| No expression | 325 | 1,894 | 20.76 | 221 | 1,492 | 12.14 |

Of the projects, 79.7% had an expression with 0.6.0 and 84.0% have one on
main; by downloads, 83.3% and 90.2%. The compounds moved mostly to `exact`
(the operands were already in canonical order) and `lexical` (reordered or
re-cased); these two categories grew because of T7, not because new names
became readable.

### What each rule added

Values that gained an expression between two snapshots, on the PyPI sample;
the parity corpus (141 values; 51 resolved with 0.6.0, 96 on main) in the
last column counts every value whose answer moved.

| Rule (PR) | Values gained | Projects | Downloads (billions) | Parity values moved | Step kinds that appear |
| - | - | - | - | - | - |
| T6 drop guard (#120) | 0 (1 lost) | 0 | 0 | 9 | `drop!` (5 values refused) |
| T6b quotes (#121) | 1 | 1 | 0.00084 | 0 | `unquote` |
| T7 compounds (#122) | 66 | 110 | 6.60 | 48 | `reorder` (34), `operator_case` (4) |
| R7 fixes (#125) | 0 | 0 | 0 | 2 | none (reasons only) |
| T9 trove names (#126) | 20 | 115 | 0.87 | 11 | `trove_name` (14), `trove_path` (3), `trailing_name` (5), `listed_name` (6) |
| T8 prose forms (#128) | 18 | 177 | 1.16 | 3 | `prose_form` (19), `separator` (12) |
| T8b semicolon lists (#131) | 0 | 0 | 0 | 0 | none |
| T5b list choice cache (#132) | 0 | 0 | 0 | 0 | none |

Net: 66 + 20 + 18 + 1 = 105, less the value T6 refused until T6b, gives the
104 more values with an expression (137 to 241). Readings:

- T6 refuses one sample value (`"MIT"` with its quotes, 843,066 downloads);
  T6b reads it again. For the parity corpus T6 moved 9 values: 6 that 0.6.0
  read are now refused (5 of them by the drop guard, which names the
  character), and 3 refusals gained a reason.
- T7 turned 66 of the 67 compounds into an expression. The one that did not
  (`BSD-3-Clause and Public-Domain`, 1 project) names an operand outside the
  List and is now `unresolved` with a reason; 6 other unresolved values
  gained a reason (`not an SPDX operator: /`, `operand not resolved: ...`).
- T9 added 6 values read through a listed name with a trailing short name
  (`MIT License (MIT)` and the like), 9 read through the trove table and 5
  deprecated IDs read as `assumed_only`.
- T8 read 18 prose forms (`Apache License, Version 2.0`, `BSD 3-Clause
  License`, ...) as `prose_form`, the weakest category that still gives an
  expression.
- T8b and T5b change no answer on either corpus. T8b targets lists with a
  semicolon; the sample has two values with one, both a licence followed by a
  notice or a second text (`MIT; Copyright (c) ...`), and both stay
  unresolved on purpose. T5b changes speed and the list choice, not answers.
  Their effect is in the generated-value check recorded in the review, not
  here.

### The values still unresolved

221 values, 1,492 projects (16.0% of the 9,353), 12.1 billion downloads. By
field: 212 values from `License`, 9 from classifiers. 215 carry no reason;
the 6 that do are compounds with an unknown operator or operand. The top 20 by
projects (1,187 projects, 8.97 billion downloads together):

| Projects | Value | Field | Reading |
| - | - | - | - |
| 354 | `Apache Software License` | classifier | trove name with no stated licence: Apache-2.0 by usage, not by statement (Q3, deferred) |
| 325 | `BSD` | `License` | several licences (family) |
| 271 | `BSD License` | classifier | trove family name: several licences |
| 37 | `Apache` | `License` | no version; the List holds several |
| 24 | `Apache Software License 2.0` | `License` | trove family name plus a version, in no trove entry and no prose rule |
| 22 | `Other/Proprietary License` | classifier | a category, no SPDX ID |
| 21 | `Python Software Foundation License` | classifier | trove name with no stated licence: PSF-2.0 by usage |
| 16 | `LGPL` | `License` | several licences (family, no version) |
| 14 | `NVIDIA Proprietary Software` | `License` | proprietary text, no SPDX ID |
| 14 | `Proprietary` | `License` | no SPDX ID |
| 14 | `Public Domain` | `License` | no SPDX ID |
| 10 | `LICENSE.txt` | `License` | a file name, not a licence |
| 9 | `BSD-3` | `License` | an abbreviation of no List name; BSD-3-Clause by guess |
| 9 | `GPL` | `License` | several licences (family) |
| 8 | `Apache Software License (Apache 2.0)` | `License` | trove family name with a trailing short name; neither part states a version-bearing List name |
| 8 | `CC0 1.0 Universal` | `License` | an alias of CC0-1.0, not a List name |
| 8 | `Intel Simplified Software License` | `License` | a vendor licence the List does not name |
| 8 | `MPL` | `License` | several licences (family, no version) |
| 8 | `New BSD` | `License` | an alias of BSD-3-Clause; the name is ambiguous |
| 7 | `GNU Library or Lesser General Public License (LGPL)` | classifier | trove name with no version: several licences |

By reading, the top 20 are 6 families or bare names with several licences, 2
trove names that mean one licence only by usage, 5 proprietary, custom or
public-domain texts, 1 file name, 3 aliases or abbreviations, 2 trove names
with a version or short name that no rule reads, and 1 trove name without a
version.

### What this says

1. The rules gained 104 values and 402 projects (4.3 points of projects, 6.9
   points of downloads). The compounds carry 6.6 of the 8.6 billion downloads
   gained.
2. What is left is mostly not lexical. The three largest groups (the trove
   names `Apache Software License` and `BSD License`, and the bare `BSD`) are
   950 of the 1,492 unresolved projects and 8.3 billion downloads; each
   needs a decision about what a usage reading may claim, not a better rule
   (Q3 of the review).
3. The next candidates by size that a rule could read are the single-licence
   aliases and abbreviations (`BSD-3`, `CC0 1.0 Universal`, `New BSD`,
   `APL 2`) and the trove family names plus a version
   (`Apache Software License 2.0`); each is 3 to 24 projects.

### Not measured here

- Frequency beyond the top 10,000 projects, and across releases.
- The semicolon rule (T8b) on real values with an operator: the sample has
  none that resolve.
- Timing: T5b's speed figures are in the review, not repeated here.
