---
Created: 2026-11-07
Last-Modified: 2026-11-07
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# The flow of `resolve()` and the canonical form of an expression

Two user-facing documents give the material for the "how it works" part of a
paper, each with run examples, source lines and the test that pins each rule:

- `docs/resolve-flow.md`: the readers in the order they run, as a Mermaid
  flowchart and a numbered list; what each accepts and refuses; step kinds,
  categories and trust.
- `docs/expression-canonicalisation.md`: the canonical form rule by rule
  (stages A to D), with each difference from SPDX Specification 3.0.1,
  Annex D.

Findings worth citing, all observed by running the code at `main`
`7276ee4` (2026-11-07):

1. The canonical form is licenseid's own convention. Annex D states only
   that `AND` and `OR` are commutative; operand order, duplicates and
   redundant brackets are unspecified.
2. Two canonical orders exist in the package. `resolve()` and `detect()` on
   a whole input use `exprcanon` (case-folded, leaves before groups); a tag
   in a file uses `py_spdx_license` `sort()`. `Zlib OR MirOS OR MIT` gives
   `MirOS OR MIT OR Zlib` and `MIT OR MirOS OR Zlib`. Both are equivalent
   expressions; a consumer comparing strings sees a difference.
3. The reader accepts more than Annex D (mixed-case operators, `[]` and
   `{}`, a line break as white space, `licenseref-x`) and writes the strict
   form. It keeps `LicenseRef-A` and `LicenseRef-a` apart where the Annex
   calls them one identifier.
4. `MIT Or ISC` is pinned as `ISC OR MIT`, category `lexical`
   (`tests/test_resolver_compound_limits.py:25`), so the leniency is
   deliberate, though it differs from Annex D.
5. A trove name the table reads as `none` is reported as `not found`, which
   hides that the table knows the name.
