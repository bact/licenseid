---
Created: 2026-10-02
Last-Modified: 2026-10-02
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Matching rules redesign — areas and open decisions

See also: [`tech-debt-roadmap.md`](tech-debt-roadmap.md), where each item
number below is described in full.

Several open roadmap items are one rule fixed in one place at a time. This
note groups them into six areas, each needing a rule, a taxonomy or a
decision before any fix. Once an area has its rule, its items become test
cases for it, not separate fixes. Written from a roadmap review on
2026-10-02, after PR #68 (item 22).

## Order

Areas 1 → 2 → 3 are item 31 and go together, the grammar first, as
certainty and ranking build on it. Area 5 can go first: item 32
(Priority 24) needs none of the others. Areas 4 and 6 are small
decisions that can be made at any time.

## 1. SPDX grammar: one reader

Items 31, 33, 20, 19, 26, 30.

Six places each hold part of the grammar: `leading_expression`,
`is_simple_expression`, the "+" operator regex, `parse_expression`,
`markers._expression_flags`, and `qualify_trailing_grant` with the
deprecated-ID tables.

Decide:

- one reader that returns a typed tree, with the other judges derived
  from it;
- what it does with a non-ASCII letter (refuse the value, not cut it: item
  33), a grant inside an expression (carry it or refuse: item 20),
  `NONE` and `NOASSERTION`, and a "+" in prose (item 30);
- one depth cap on every Python version (item 19);
- whether to delegate to `py_spdx_license` once it parses "+" in linear
  time (item 26).

Test with a conformance table written from the grammar (SPDX Annex D), not
from the bugs.

## 2. Certainty: who may answer, and how sure

Items 31, 28, 30, 35.

Missing taxonomy: the kinds of evidence (declaration, exact ID or name,
look-alike name, phrase, whole text, close text) and the strongest answer
each may give.

Decide:

- whether a short phrase hit is evidence or an answer: `BSD` answers
  `0BSD` at 1, and `is-osi` then says yes (item 28);
- what an exact text is: today the whole normalised input equal to the
  licence's text, while the SPDX guidelines let replaceable and omittable
  text differ (a filled-in copyright line, a title);
- whether a byte order mark given through `--text` changes the answer;
- whether a deprecated row with no text stays a Tier 2 candidate
  (item 35).

## 3. Ranking: certainty apart from closeness

Items 31, 7, 13, and the score cap of item 22.

Each tier ranks on a scale of its own (1.0 to about 1.08); item 22 only
caps what is shown.

Decide:

- rank on two keys, certainty then closeness, so no cap is needed;
- whether family disambiguation (GPL family, item 7; Apache-2.0 and Pixar,
  item 13) is a ranking rule or a step of its own;
- whether the public `score` stays one number.

## 4. Flags for expressions and references

Item 34.

Decide:

- `is_osi_approved` and `is_fsf_libre` for `MIT OR Apache-2.0`: all of its
  licences, any of them, or null;
- `is_spdx` for a `LicenseRef-*` (false);
- how the text line writes an ID with spaces (quoted, or the spaces
  replaced), since `awk` splits it now.

## 5. Input and option precedence

Items 32, 5, 35 (`exclude`).

Missing taxonomy: whether a bare argument is a file, an ID or text, and
what decides.

Decide:

- whether an argument shaped like a path that names no file exits 2
  (item 32);
- for each conflicting pair, reject (exit 2) or document which wins:
  `--id` with `--text`, `--bold` with `--json`, `--diff` with `--exact`,
  and the options the declared paths ignore (`exclude`, `only_spdx`,
  `hint`);
- whether `--top` must be at least 1.

## 6. Exit codes and error taxonomy

Items 10, 12, 35.

Exit 1 means both "no" and "failed": Ctrl-C and a closed standard output
exit 1, so `is-osi` reads an interrupted run as "not OSI".

Decide:

- Ctrl-C exit code: 130 or 2;
- a failed write to standard output: exit 2;
- whether click's usage errors are reworded to
  `LEVEL: SUBJECT: CONDITION`;
- whether the API wraps `sqlite3` errors and `FileNotFoundError` in
  `LicenseIdError`, and in which layer.

## Not part of this redesign

Fixes that need no new rule: speed (items 27, 29, 23, and 11 with its
own plan), lint coverage (item 9), and upstream waits (items 2 and 26).
