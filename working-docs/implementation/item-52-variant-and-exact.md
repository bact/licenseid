---
Created: 2026-11-16
Last-Modified: 2026-11-24
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Item 52: the variant option and `EXACT`

Roadmap item 52 of
[`../design/tech-debt-roadmap-reading.md`](../design/tech-debt-roadmap-reading.md).
Built in two pull requests: PR #211 (merged 2026-11-16) makes `exclude` and
`hint` act on free text only; PR #212 (merged 2026-11-16) adds `detect
--variant`, the record field `VARIANT_STATED` and the `EXACT` rule below.
User docs: `docs/cli.md`, `docs/output.md`, `docs/python-api.md`,
`docs/resolve.md`.

## The problem

The SPDX License List split `GPL-2.0` into `GPL-2.0-only` and
`GPL-2.0-or-later` and deprecated the bare ID. The two texts are the same, so
only the author's words (a grant of later versions, "only", a "+") say which
is meant. `resolve()` kept a bare `GPL-2.0` as written (`assumed_only`,
trust `none`); `detect()`, `--id` and a tag narrowed it to `-only` with
`WARNING: input: variant not stated`. The two paths disagreed, and
`detect()` guessed for the author.

## The design as built

Principle: a **declaration** stays as written; a **decision** by licenseid
never gives a deprecated ID, and says it is a decision.

- **Declared value** (argument, `--id`, tag, manifest field, a whole input
  `resolve()` reads): under `auto` (the default) a bare ID and a `-with-` ID
  stay as written, exact, `VARIANT_STATED=false`, no warning.
- **Text or name match**: never a deprecated ID under `auto`, `only` and
  `or-later`. `variants.settle_text` replaces a deprecated row by its twin
  (`_replaced`), puts `-or-later` first where the input grants later
  versions (`ranking.or_later_signal`) and `-only` first where it says
  "only" after a version (`ranking.only_signal`), else `-only` first with
  one warning. A pure licence text has neither signal: the GPL's "How to
  Apply" appendix holds the grant phrase. `as-written` leaves the two twins
  of a text as the bare ID (`_collapsed`).
- **`--variant`** (`auto`, `as-written`, `only`, `or-later`; API
  `variant=`): `as-written` never decides; `only` and `or-later` decide
  declared values too (`variants.fallback`, a context variable
  `variants.read_as` sets around one `detect()` call; outside it a reader
  reads `only`, as before). The
  option is a preference: words that state the variant win, with `WARNING:
  option: overridden by input: --variant only; using GPL-2.0-or-later`.
  `is-*` take no `--variant`.
- **Warnings**: `variant not stated` and the override are held until the
  results are known and given only for a result the output prints
  (`variants.output_bar`: `--threshold`, `--exact`, `--top`; 0.85 in the
  API), a text's guess only at `variants.ANSWER_SCORE` (0.85) or more. The
  DETAIL is the licence (`GPL-2.0`), never the text.
- **Output**: `VARIANT_STATED` is the last field of the `detect` record
  (JSON `variant_stated`): `true` when the input's words or an
  `-only`/`-or-later` ID state it, `false` for a guess or a bare ID kept,
  empty where no licence has a variant (`MIT`); a compound is `false` when
  any operand is. `is-*` records have no such field.
- **`is-osi` and `is-fsf`** judge a kept bare or `-with-` ID by its `-only`
  twin (`exprflags.judged_id`, `with_judged_flags`): the List's flags are
  not equal (`AGPL-1.0` is FSF libre, its twins are not judged; the
  `GPL-2.0-with-*` rows are 0/0).

## `EXACT`

`exact` is set where a result is made, from what defines the answer, never
from the score or the trust:

- **(a) A declared value** is exact when a list defines its reading: the
  SPDX License List or a list licenseid keeps (roadmap item 55). Every
  operand's category must be in `resolvefirst.EXACT_CATEGORIES` (`exact`,
  `lexical`, `listed_name`, `deprecated_equal_successor`,
  `plus_to_or_later`, `deprecated_ambiguous`, `stated_qualifier`,
  `assumed_only`, `alias_name`, `trove_name`, `text_title`,
  `license_url`); a rewrite rule (`separator`, `prose_form`,
  `version_spelling`) is no list. A kept bare ID (`assumed_only`) is exact
  only where the operand was written so, case aside (`GPL-2.0`, `gpl-2.0`,
  `(GPL-2.0)`), not where a rule re-spelt it (`GPL2`). A `-with-` ID a rule
  re-spelt (`GPL v2 with classpath exception`) is not exact. A slash pair
  of IDs (`MIT/Apache-2.0`) stays exact. A tag or field is judged by the
  expression it starts with, not by the words after it on its line
  (`ruleread.tag_inexact`; the ID before a grant is judged alone, so `GPLv2
  or later` is inexact as a tag, a field and the argument alike).
- **(b) A text** is exact when the whole non-empty normalised input equals
  the licence's `search_text`, as before.
- **(c) A variant licenseid chose is never exact**: `result.public_result`
  applies this one rule at the exit of `detect()` (`variants.guessed_of`),
  and `--exact` reads the same. So a pure GPL text is not exact: its
  variant is a guess.

Measured before the decision (2026-11-15, 2,516 inputs, List 3.29.0):
exact answers were 98.9% right, inexact ones 78.9%. On the PyPI sample,
583 of 7,795 resolved projects (7.5%) go from exact to not exact
(`separator` 306, `prose_form` 207, `version_spelling` 70).

## Evidence, `stated_of` and `decided`

Every result carries `evidence` (`types.Evidence`), set where it is made:
the declared `value` as written (`variants.read_from`), or for a text or
name match the signals that chose its form (`later`, `only`;
`settle_text`). `decided` lists the folded `-only`/`-or-later` forms
licenseid chose for a declared value: `looseid.read_inexactly` stores what
`looseid.decided_forms` finds, `looseid.mark_guessed` every variant form
of the match when no reader listed them (fail closed), and
`candidates.as_matches` carries them.

One reader judges it: `variants.stated_of` (the field) and
`variants.guessed_of` (rule (c), the warnings, the override). A form is
stated only by the input's words: the ID itself, "only", a grant read by
`classify.grant_end`, a "+", each beside its own licence in a compound
(`_supports`, `_family_pattern` with re-spellings such as `GPLv2` and `GPL
2.0`; another version's words, `GPL-2.0 version 3 only`, state nothing).
No evidence states nothing. A form in `decided` is never stated, whatever
another operand says: `identifiers` merges equal operands, so
`GPL-2.0-only AND GPL-2.0` reads as one `GPL-2.0-only`, and only the mark
can tell that the second was decided.

## Invariants

`tests/test_variant_invariants.py` checks value x channel x variant:

- I1: a value answers alike through every channel that answers (a tag takes
  only List IDs);
- I3: a variant is stated only by the input's words;
- I4: an answer licenseid chose is never exact;
- I5: under `auto` a declared bare ID is kept, not stated, exact.

## `exclude` and `hint` (PR #211)

API options of `detect()` only: no CLI flag, and `resolve()` has neither,
so default `detect()` and default `resolve()` agree. They act on free text
only: a declaration is never filtered or hinted. Prose markers, windows and
short-prose name hits obey `exclude`. Both fold case; a hint given twice is
added once. A bare deprecated ID stands for both twins (`GPL-2.0+` for the
`-or-later` one), kept as written under `as-written`, with `WARNING:
option: deprecated ID: exclude GPL-2.0; using GPL-2.0-only,
GPL-2.0-or-later` (`idoptions.upgraded_options`, once per call). A form the
option chose after `exclude` ran is no excluded ID
(`variants.settle_free_text`). Still pinned `# BUG:` (roadmap item 46): a
hint undoes `exclude`; a hint counts towards the fewer-than-5 test.

## Paths rejected

- **A `variant_guessed` flag** set at each reader: review rounds 7 to 9
  kept finding a reader that forgot it. Replaced by `evidence` and one
  fail-closed reader (I3 breaks in a probe: 14 to 0).
- **Counting heuristics**: `_supports` counted the places a value names a
  family against the operands of the form; each fix (rounds 15 to 18) broke
  a re-spelt copy (`(GPL-2.0-only OR MIT) AND (GPLv2-only OR X)`). Replaced
  by the operand marks of `decided`.
- **A raw scan of the text for `classify.OR_LATER_PHRASE`**: the GPL
  appendix would always grant later versions. The signal is the one the
  tie-breaker uses, and a pure text has none.
- **`exact = trust != "none"`**: it made a rule's reading exact (`Apache-1`
  as `Apache-1.0`, `MIT-` as `MIT`; roadmap item 54).
- **Category alone for `assumed_only`**: `GPL2` would be exact.
- **A per-reader override warning**: decided once, on the printed results.
- **A warning bar of 0.8**: junk input (lorem ipsum, shuffled licence words)
  scores 0.5 to 0.67, and seeded test databases score 0.836; the bar is
  the 0.85 of `is_*()` and of `--threshold`.

## Pinned and left cases

Each is a `# BUG:` test or a known gap, kept rather than fixed under the
stop rule of the last review rounds: fix only wrong output on a common
input, a crash, a hang, a cost regression, a dropped operand or a broken
invariant.

- `tests/test_variant.py`: the grant signal is the input's, not the
  licence's, so a grant of the LGPL beside it chooses `-or-later` for
  this licence too, and a README's "Python 3.8 or later" counts.
- `test_a_grant_the_marker_did_not_read_leaves_the_only_form`
  (`tests/test_variant_readers.py`): a README "GNU GPL v2 or (at your
  option) any later version" is `GPL-2.0-only` from the heading marker,
  with a false warning; the `-or-later` row scores far lower, so it is no
  peer to swap with. Widening the signal to the marker's own words would
  fix it; reading the whole input would flip the Python case above.
- `test_a_tag_reads_an_only_after_an_operand_of_a_list`
  (`tests/test_variant_operands.py`): a tag answers `MIT OR GPL-2.0 only`
  as `main` did; the argument and a field refuse it (I1). Refusing would
  lose an answer `main` gave.
- `tests/test_variant_invariants.py`: a deprecated List name (AGPL)
  answers `-only` as the argument under `auto`, the bare ID in a tag or a
  field (I1); one name reader needs a larger change.
- Not pinned: `eCos 2.0` (`deprecated_ambiguous` and `separator`) stays
  exact, as on `main`; `--id GPL2+` is exact where the argument is not; a
  notice before a full GPL text is not read for its grant (the pure-text
  rule); an ID a marker finds in prose counts as declared.

## Measured

- Golden answers: 44 `detect()` moves in `tests/harness_changes_variant.py`
  (33 declared values kept as written; 11 long texts of GPL, AGPL, LGPL and
  GFDL, now `-only` and not exact) and 29 CLI digests (the new field), on
  top of 87 `exact` moves in `tests/harness_changes_exact.py` (46 values,
  27 IDs, 14 names).
- sbomminbench manifests (inputs only: 172 distinct licence values of 640
  registry entries, as the argument and a JSON field, and 31 manifest
  files; 375 rows per variant against `main`): 0 bugs and 0 exceptions.
  Intended differences 45 (`auto`), 39 (`only`), 45 (`as-written`), 47
  (`or-later`): a rule's reading no longer exact (`Apache 2.0`, `The MIT
  License`, `EPL 1.0`); a licence URL to a deprecated ID kept
  (`gpl-3.0.html` is `GPL-3.0`); one operand order in a field or tag, as
  the argument; `or-later` decides two junk text matches below the
  warning bar. Four cases are in `tests/test_variant_registry_values.py`.
- Cost: `_supports` splits lines only for a declared value; a text's
  evidence returns first (a split per result cost 2.5 times `main` on
  400,000 blank lines).
