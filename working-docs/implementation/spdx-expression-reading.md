---
Created: 2026-09-28
Last-Modified: 2026-09-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Reading a whole SPDX expression (PR #61)

What shipped is in `CHANGELOG.md`; the open items are in
[`../design/tech-debt-roadmap.md`](../design/tech-debt-roadmap.md) items 19
and 20. This file records the decisions, the paths rejected, and the traps
that took several review rounds to find.

## The shape of the answer

One reader, one resolver, one judge:

- **Reader**: `identifiers.leading_expression` walks the tokens of a tag
  value and returns the longest prefix that can still be an expression.
  Only AND, OR and WITH join two parts, so a token none of them bridges
  ends it; a dangling or unbalanced value is no expression at all. It
  replaced a regex that held its own SPDX grammar and read
  `MIT OR (Apache-2.0 AND BSD-3-Clause)` as a certain `MIT`.
- **Resolver**: `MarkerDetector.resolve_license_value` serves every source
  of a license value (tag, JSON, TOML, INI and `license_id`). It tries the
  whole value as a name first (`MIT No Attribution` is MIT-0, not MIT), then
  the expression.
- **Judge**: `identifiers.is_simple_expression` decides what a declaration
  may hold. Both `--id` and `match(license_id=...)` read it.

## Decisions

- **A declaration is narrow; a file is not.** The PR first widened `--id`
  to any expression a tag accepts, then reversed that: `MIT OR Apache-2.0`
  declares neither license, and `is-osi`/`is-fsf` have no answer for it.
  `--id` takes an ID or `LicenseRef-*`, with an optional `+` and one
  `WITH <exception>`, in brackets or not. Anything else exits 2. A tag
  still holds any expression.
- **A bare CLI argument is a guess**, so it is read as an ID only when it
  would pass `--id`. Otherwise it is matched as text:
  `BSD-3-Clause but modified heavily by us` is text, not BSD-3-Clause.
- **"or later" is a grant, not the OR operator.** It qualifies the ID
  beside it, the license of a WITH rather than its exception, and it closes
  the brackets it stands in: `(GPL-2.0 or later)` reads as
  `(GPL-2.0-or-later)`. A value that goes on after a grant is refused: an
  answer without the later operands would understate the obligations
  (roadmap item 20).
- **A tag value ends at its line break or at the next tag**, whichever
  comes first. On a minified line with thousands of tags, running each
  value to the end of the line made the reading quadratic.
- **Brackets around a whole expression never reach the answer.**
  `_normalize_expression` drops them before the sort and before the
  40-operator cap. The sort drops them anyway, but it is skipped for a `+`
  (py-spdx-license issue #1) and past the cap, and the parser gives up
  on thousands of them.

## Traps

- **Each fix added the next quadratic path.** Three review rounds in a row
  found a slowdown that the previous round's fix had introduced. Each time
  it was a loop that re-sliced or rescanned its input once per item
  (`while s.startswith("("): s = s[1:-1]`, one pass over the whole line per
  tag). Write one pass.
- **Measure against `main`, with distinct values.** A dedupe made 4,000
  identical tags take 0.05 s while 4,000 distinct ones took 8.7 s against
  6.9 s on `main`. A CHANGELOG line once claimed a fix for a 36 s slowdown
  that only ever existed on the branch.
- **Time balanced payloads.** Unbalanced deep brackets fail early and prove
  nothing; a balanced 40,000-deep nest found two quadratic loops.
- **Python 3.10 is the slow one on a deep parse.** A deep-bracket test
  that took about 1 s locally took 5.3 s on CI's 3.10 and failed its 5 s
  limit; 3.14 passed. The cost was `py_spdx_license` failing on deep
  nesting. The fix kept deep nesting away from the parser rather than
  raising the limit (roadmap item 19 covers the depth itself).
- **A deprecated name must answer as its ID does.** A name shared with a
  deprecated row whose replacement is an expression
  (`GPL-2.0-with-GCC-exception`) returned the deprecated row until the name
  path was sent through the same normalisation as the ID path.
- **A `;` in an echoed value forges the ACTION** of the error grammar, so
  `errors.invalid_id_error` turns it into `,`.

## Habits that caught these

- Run the new tests against a `git archive` of HEAD's `src/` (through
  `PYTHONPATH`) to prove each one fails without the fix; mutation-check the
  new lines, clearing `__pycache__` between mutants.
- Compare every fixture's top three answers before and after (1,405 files,
  unchanged throughout).
- Re-read the PR description before merging: after the `--id` reversal it
  still described the opposite.
