---
Created: 2026-10-02
Last-Modified: 2026-11-18
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

Status (2026-11-18): areas 1 to 3 are open (roadmap item 31); areas 4 to 6
are decided and built (items 34, 32, 5, 10, 12). They stay below for the
decision they record.

## Order

Areas 1 → 2 → 3 are item 31 and go together, the grammar first, as
certainty and ranking build on it.

## 1. SPDX grammar: one reader

Items 31, 33, 20, 26 (19, 30, 33 and 43 are done; item 20 is not built).

Six places each hold part of the grammar: `leading_expression`,
`is_simple_expression`, the "+" operator regex, `parse_expression`,
`exprflags.expression_flags`, and `qualify_trailing_grant` with the
deprecated-ID tables.

Decide:

- one reader that returns a typed tree, with the other judges derived
  from it;
- what it does with a grant inside an expression (carry it or refuse: item
  20; decided 2026-11-17 not to build it, a tag refuses it), `NONE` and
  `NOASSERTION`, and a "+" in prose (item 30, read by
  `versionkey.version_key`); a non-ASCII letter refuses the value (item 33,
  done);
- one depth cap on every Python version (item 19, done: 150 operators
  and 150 brackets, `identifiers.parse_expression`);
- whether to delegate to `py_spdx_license` once it parses "+" in linear
  time (item 26).

A "/" between List IDs is one more spelling of OR in a whole declared value
(item 43, done: `resolveslash.py`, exact case, a table of refused pairs, no
tag). The grammar itself has no "/" and takes none.

Test with a conformance table written from the grammar (SPDX Annex D), not
from the bugs.

## 2. Certainty: who may answer, and how sure

Items 31, 28, 35.

Missing taxonomy: the kinds of evidence (declaration, exact ID or name,
look-alike name, phrase, whole text, close text) and the strongest answer
each may give.

Decide:

- whether a short phrase hit is evidence or an answer: `BSD` answered `0BSD`
  at 1 (a single word of a longer name no longer does, PR #168), but a
  phrase of ten words or more that several licences share still does (item
  28);
- what an exact text is: the whole normalised input equal to the licence's
  text, while the SPDX guidelines let replaceable and omittable text differ
  (a filled-in copyright line, a title); for a declared value item 52
  settled it (exact where a list defines the reading);
- whether a byte order mark given through `--text` changes the answer;
- whether a deprecated row with no text stays a Tier 2 candidate (item 35;
  one case closed by PR #212).

## 3. Ranking: certainty apart from closeness

Items 31, 7, 13, and the score cap of item 22.

Each tier ranks on a scale of its own (1.0 to about 1.08); item 22 only
caps what is shown.

Decide:

- rank on two keys, certainty then closeness, so no cap is needed;
- whether family disambiguation (GPL family, item 7; Apache-2.0 and Pixar,
  item 13) is a ranking rule or a step of its own;
- whether the public `score` stays one number.

## 4. Flags for expressions and references (decided, item 34)

`exprflags.py` judges them: a `LicenseRef-*` is `is_spdx` false with both
approval flags empty; for a compound, `OR` is true if any operand is, `AND`
only if all are, `WITH` takes its licence (D8 of `match-resolve-0-8.md`);
the text line keeps a value's spaces in `EXPRESSION=`, with tab-separated
fields.

## 5. Input and option precedence (decided, items 32, 5)

A missing file named as an argument exits 2 (`input: not found: <path>; pass
--text`); two inputs exit 2; `--json` with `--diff` exits 2; `--top` and
`--threshold` out of range exit 2. An option with no effect on an exact
answer is documented, not rejected (`--diff` with `--exact`; `exclude`,
`only_spdx`, `only_common`, `hint`, `enable_popularity` with a declaration).
`exclude` and `hint` act on free text only (PR #211); `only_spdx` is roadmap
item 46.

## 6. Exit codes and error taxonomy (decided, items 10, 12)

Decided on 2026-10-02: Ctrl-C exits 130 and a closed pipe 141, both quietly;
any other failed write to standard output exits 2 (PR #70); click's usage
errors are worded in the grammar, and the help for a missing subcommand goes
to standard error (item 12, PR #73). Every `sqlite3.Error` of a read becomes
`DatabaseNotReadyError` (`Connections.connection`).

## Not part of this redesign

Fixes that need no new rule: speed (items 27, 29, 23, and 11 with its
own plan), upstream waits (items 2 and 26).
