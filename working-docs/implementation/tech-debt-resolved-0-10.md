---
Created: 2026-11-26
Last-Modified: 2026-11-26
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
