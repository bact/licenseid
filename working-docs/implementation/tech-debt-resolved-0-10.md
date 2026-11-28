---
Created: 2026-11-26
Last-Modified: 2026-11-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Resolved tech debt, from item 64 (2026-11-26)

Items of [`../design/tech-debt-roadmap.md`](../design/tech-debt-roadmap.md)
resolved from item 64 on, split from
[`tech-debt-resolved-0-9.md`](tech-debt-resolved-0-9.md) at the size limit.

## Item 64: template variables in the search of whole texts (2026-11-26)

`TEXTS` compared a found text with the List text character by character, so a
copy that writes its own copyright holder or project name where the template
lets the text vary (SPDX matching guidelines B.3.3) lost 2 to 5 points on
those words. The look-alike rule (a hit under 0.98 doubted by a twin at 0.93)
or the 0.95 floor then refused the right name in all ten known cases (sympy,
numpy, lxml, prettytable, nodeenv, isodate, dill, json_flattener: BSD-3-Clause;
Pillow: MIT-CMU, X11). Built as option AKG of the plan: the variable parts are
left out of the fit of hits and look-alikes alike where the input's words
there match the part's `match` pattern, are at most 150 characters longer
than the List's words and sit between matched words; the key counts a fill
up to the length of its List words; two masked fits within 2 percent tie;
the look-alike rule stays. A review found the first key, the missing bound
and the missing tie; all three are fixed. A second review found a length
pre-filter that dropped a copy with short fills and a fill bound that kept a
longer text from doubting a shorter one inside it; both are fixed. Database
build 7 stores the
regions (0.34 MB). On 596 real files 22 names are gained
in 20 files, none lost, and no answer at 0.85 moves. Details, the CJK sweep
and the numbers:
[`whole-texts.md`](whole-texts.md), section 10.

## Item 13: Apache-2.0 and its look-alike `Pixar` (2026-11-28)

`Pixar` is `Apache-2.0` with another section 6. Pitloom found (on 0.9.4, and
it held on 0.10.0) that a verbatim Apache 2.0 file, rfc8785 0.1.4 `LICENSE`,
answered `Apache-2.0` 1.0 with `Pixar` 0.9947, `ImageMagick` 0.9871 and
`ECL-2.0` 0.9792 beside it, each row with `TEXTS=Apache-2.0`: a near tie it
left undecided when nothing else was stated. Built in PR #256 as rule A of
the maintainer's decision of 2026-11-28: where the search finds a text whole,
`ranking.under_found` leaves out every runner-up that nothing names; one a
marker or `hint` names (either twin) keeps the rule of 0.10.0 and stays under
the text found. The file answers `Apache-2.0` alone, and the List texts of
`Pixar`, `ImageMagick` and `ECL-2.0` each answer their own ID alone. Measured
on the built tree against 0.10.0, one process, 1,704 speed gate inputs and
1,099 golden texts: no first result differs in any field, no warning differs,
587 gate inputs lose 1,684 rows and 311 golden texts lose 881; `tools.golden`
moves nothing. Tests: `tests/test_whole_text_alone.py` (the rfc8785 file as
a fixture, a real `Pixar` text still `Pixar`), `tests/test_whole_text_rules.py`.
Plan: `../design/texts-ranking-evidence-plan.md`; as built:
[`whole-text-first.md`](whole-text-first.md), section 10.

## Item 68: `TEXTS` as ranking evidence (2026-11-28)

Left by item 59: on 25 of 596 real files `TEXTS` named one text and the top
row was a look-alike of it, under 0.85 or, in wcwidth's `LICENSE`, above it
(`JSON` 0.9238 over `MIT`). The 0.10.0 engine ranks a text found whole first
(task T5, [`whole-text-first.md`](whole-text-first.md), section 6), and
PR #256 leaves out the look-alikes nothing names beside it (item 13 above).
Read again on the tree of PR #256: of the 25 files, 17 answer the text found
at 0.85 or more and none a look-alike of it; wcwidth 0.2.13 answers `MIT`
0.9197 and mypy_extensions 1.1.0 `MIT` 0.9641 (Pitloom's C1 and C2); the two
Pillow files have no `TEXTS`. Of the 300 real files of the plan, 250 have one
text in `TEXTS`: 244 answer it at 0.85 or more. Closed by the maintainer on
2026-11-28 with its leftovers moved:

- To item 82: the 4 files whose top row names the text found under 0.85
  (`2e9aec16`, `aaf1f9bb`, `b87bd47e`, `e57d6584`: the MIT text and about as
  much again, coverage 1.85 to 2.21; `b87bd47e` and `e57d6584` are mdurl 0.1.2
  and tqdm 4.70.1, Pitloom's D1).
- To item 78: the 2 files that answer a licence a marker names, beside
  another text found (`83a1fcfd`: `LGPL-2.1-or-later` 0.9187, `TEXTS=NCL`;
  `f3b34c66`: `Apache-2.0` 0.9187, `TEXTS=BSD-3-Clause`, 211 ms).

Plan, measures and the rules rejected (rule B, runner-ups not scored):
`../design/texts-ranking-evidence-plan.md`, sections 3 and 9.
