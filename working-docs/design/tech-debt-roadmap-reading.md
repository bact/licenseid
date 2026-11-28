---
Created: 2026-11-24
Last-Modified: 2026-11-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Tech debt roadmap: reading values and names

The open items on reading a declared value or a name: `resolve()` and its
parser, the name tier (Tier 0), `--variant` and `EXACT`, and the lists page.
Split from [`tech-debt-roadmap.md`](tech-debt-roadmap.md) on 2026-11-24 at
the size limit; that file explains the priority score and the item numbers
(shared by both files, never reused) and links the resolved items.

Items 79 to 81 are what Pitloom, which reads licences through licenseid,
reported on 2026-11-28 (its notes are in the repository `bact/pitloom`,
under `working-docs/`). They run after or beside items 68 to 70 of the
other file; Pitloom's own order is 79, item 13 there, 80, 81. Rules for all
of them: run each reproducer again on the current release first and drop
what no longer shows, saying which release Pitloom last checked; ask the
maintainer before a public name or a return shape changes (an addition is
free); never edit Pitloom's files; end with a report for Pitloom (what
changed and in which release, new signatures, which of its workarounds and
ledger entries can go, what could not be reproduced). Pitloom 0.25.0 pins
`licenseid>=0.9.4,<0.10`; 0.25.1 is to pin `>=0.10.0,<0.11`.

## 26. Relax the parser guard once the parser is linear — Priority 10

`identifiers.parse_expression` refuses an expression whose tokens' squared
lengths sum to more than `_MAX_PARSE_COST` (10**9, about 8 ms of tokenizer
time: one token of 31,622 characters), a workaround added with item 24.
A budget on the cost, not a cap on a token: SPDX sets no length on a
`LicenseRef-*`, and a 256-character cap refused real ones (found in review
of PR #66). A token is counted as the parser
splits it, at space, tab, line feed, carriage return and brackets only:
a run joined by a no-break space is one token there, and a guard that
split at `\s` let a million-character one through (found in review of
PR #66). `py_spdx_license` 0.0.1 parses in quadratic time, in two places
(`src/py_spdx_license/ast.py`):

- `tokenize` builds each token with `t.value += c`; on an attribute CPython
  cannot append in place, so each character copies the token: 0.11 s at
  100,000 characters, 0.35 s at 200,000, 6.8 s at 1,000,000.
- `create_ast` takes tokens with `tokens.pop(0)`, which shifts the list:
  0.18 s at 10,000 operands, 1.05 s at 40,000. The guard does not cover
  this; under 30 words an input cannot hold that many tokens, and longer
  inputs already pay it (and hit item 19's `RecursionError` first).

Item 24 opened the parser to inputs under 30 words, where a single long run
with no spaces would have cost the whole tokenizer time. The fix belongs
upstream (`JPEWdev/py-spdx-license`; the user is fixing it there). Found on
2026-10-01 while planning item 24.

- **Lift when**: licenseid depends on a release with linear parsing, and
  `test_short_tag.py::test_the_parser_refuses_an_overlong_token` and
  `test_a_long_tag_value_reads_in_linear_time` pass with the guard removed.
  Then remove the guard or raise the budget, and flip the over-budget
  cases.
- Impact 1, Risk 1, Effort 1.

## 46. Leftovers of the 0.7.0 whole-release review — Priority 12

Found in the review of 2026-11-02 to 11-03. The resolver, readers, BSD and
short-text leftovers are in `match-resolve-0-8.md`, section 7. Done: the
typed options, the lock-wait test, one long-text database and the `ruff
format` check (PR #210), and the free-text rules of `exclude` and `hint`
(PR #211); see `tech-debt-resolved-0-5.md`. Also done: `hint` against the
filters and the API names (`ToolInfo`, `DetectOptions`, `Variant`; PR #224),
the condition words for empty input (right already) and the dev METADATA
version (a line in `release-process.md`, 2026-11-18); see
`tech-debt-resolved-0-9.md`. Open:

- **Readers see `database: empty` during `update`** (1,074 errors over a
  13 s update with four reader threads; 0.6.0 does the same): the plan is a
  single transaction, a busy timeout and an OS lock; the atomic swap needs
  Windows care (`os.replace` fails on an open file). Design:
  [`concurrent-update.md`](concurrent-update.md).
- **`only_spdx` does nothing** on a database licenseid builds (every row
  `is_spdx=1`). Keep or redesign, not remove: more lists will come
  (AboutCode ScanCode, Blue Oak) and a source flag may be what it becomes.
  Decide with the multi-list design; until then it stays documented as a
  no-op on a built database.
- A tag that lists a licence elsewhere than right after the mark is still
  the first licence, exact: with "or"/"and" (`MIT, or ISC`), in brackets or
  quotes (`MIT, (ISC)`), after a full-width comma or a dash (`MIT - ISC`),
  or later in prose (`MIT, and also Apache-2.0`), or before an operator
  (`MIT - OR ISC`). #158 refuses a
  licence right after a mark (A-F6); it also refuses `MIT, Intel and
  others`, as the field reader does (the item ends at "and"). Belongs to
  the matching-rules redesign.
- `is-*` on a file with several tags judges the top one only; a garbage
  `--db` is `unreadable` or `invalid` depending on the path.
- `test_db_ready.py` (`wal_copy_without_wal`, 6 cases: `unreadable` against
  `empty`) and `test_db_ready_adversarial.py` (`damaged_fts_shadow_table`, 2
  cases: `table license_index_data may not be dropped`) fail on `main` on
  the local `licenseid310` (Python 3.10.18, SQLite 3.51.0), and the first
  also under uv's Python 3.14 (SQLite 3.43.2) on macOS; CI passes. They
  depend on the SQLite version, so every full local run shows these 8.
  Open (2026-11-18).
- **A repeated-paragraph input ranks wrong** (not investigated): on the
  real database, two copies of a prose paragraph, the full MIT text and
  two more copies give TekHVC first (0.61) and MIT outside the top 4. Check
  against `main` and the probe gate (`similarity.build_probe`).

- Impact 2, Risk 2, Effort 3.

## 47. Leftovers of the name tier on a few words — Priority 16

PR #168 (2026-11-06) stopped the name tier (`shorttext._partial_names`)
from reading words a longer licence name only holds as that name, and reads
a List name without its grant as the `-only` guess, said aloud. PR #170 read
the BSD aliases through `resolvealias.ALIASES`.

**Built** (PR #219, 2026-11-17): `namehits.settle()` drops a name
hit that the rest of the input doubts: tied names that are two licences,
a cut version, a fragment of a longer name, `with <exception>`, another ID
written whole, a dash glued to a word end (`namehits` weighs tied names,
`namerules` reads the words that touch one name). A dropped hit above 1
stops Tier 1 too. Also `vN` for `vN.0` as the `-only` guess and a fullwidth "+"
in a mixed-content section. See
[`tech-debt-resolved-0-9.md`](../implementation/tech-debt-resolved-0-9.md).
This fixed the cut IDs of item 54 and the sentences with a second name.

**Open leftovers** (counts: 134 pair probes of two List names; 708 names in
use):

- **Nested pair**: two names where one nests in the other answer the longer
  (`Creative Commons Attribution 4.0 International or Creative Commons
  Attribution Share Alike 4.0 International` gives CC-BY-SA-4.0): 1 of 134.
- **Two licences in prose, not tied**: `MIT License or BSD 3-Clause` answers
  MIT (pinned `# BUG: (item 47)`; a short BSD form is not held whole, so no
  tie); needs a rule that weighs every name the input holds, not only the tied
  ones. A grant-less GPL name beside a short name (`GNU General Public License
  v2.0 or MIT License`, bug 4 of item 58) is built: `namehits._names_another`
  reads the other name without its grant (`namehits._without_grant`); 133 of
  672 probes of `... version 2.0, requires <word> 3.8 or later` answered a
  wrong name, 0 now.
- **A list of two licences that names one whole**: `Eclipse Public License
  v. 1.0 - Cecill v. 2.0` answers EPL-1.0 (as `main` did; round 1 of the
  fix refused it): 4 of 12,723 windows. `with <one-word exception>` without
  the word "exception" (`Apache License 2.0 with LLVM`) answers Apache-2.0:
  30 of the 86 exceptions of the List.
- **One-word ID that is an ordinary word**: no second licence
  (`Unlicense, ISC License` gives ISC): 7 of 134.
- **A version the name lacks**: `MIT License 2` still answers. Refusing it
  lost 10 right `mixed` golden answers for 0 PyPI gain.
- **Wrong answers no rule touches**: `Licensed under the GNU Lesser General
  Public License v2.1` (and `v3.0`) gives BSD-Protection by text (0.867),
  `Licensed under the GNU Affero General Public License v3.0` gives MPL-2.0
  (0.86): name hits under 1, so Tier 1 answers. Text tier, found while
  building B1c (not a grant rule): `GNU Lesser General Public License
  version 2.0 or later` gives LGPL-3.0, `GNU Lesser General Public License,
  version 2, or any later version` gives GPL-3.0 and `GNU General Public
  License, either version 2.0 or later` gives LGPL-3.0. Name tier, found the
  same way: `Licensed under the GNU General Public License v2. Requires
  Python 2.0 or later to build` gives Python-2.0, `Functional Source License,
  Version 1.1, Apache 2.0 Future License` gives Apache-2.0 (the name has
  `ALv2`), `Sendmail License 8 or later` and `Sax Public Domain Notice 2 or
  later` give the ID whose name lacks the version (the `MIT License 2`
  leftover), `GNU General Public License (Lesser) v2.0 or later` and `General
  Public License, Lesser, v2.0 or later` give GPL-2.0-only (the modifier is
  not before "General Public"), `Apache License 2. Requires Java 1.8 or
  later` gives Apache-1.1
  (token set finds `1`; 1.8 is no cut of 1.1), and
  `with` more than three words after the name (`Apache License 2.0 as
  amended by us with the LLVM exception`) and `Modified Apache 2.0 License`
  still answer Apache-2.0. `GNU Lesser General Public License v2 or later`
  stays LGPL-2.1-or-later (the name `Lesser` is 2.1's), where `resolve()`
  reads `LGPL-2 or later` as LGPL-2.0-or-later.
- **`<name> Plus`** still answers the name (706 of 708 probes).
- **A name with "+"**: `GNU Lesser General Public License v3+` (1 project)
  gets no answer (`normalize_text` drops the "+"). It could be `-or-later`.
- **A manifest field** with a name less its grant (1 project):
  `license = "GNU General Public License v2.0"` gets no answer and no
  warning (`_try_manifest_value` takes a name hit of 1.02 only).
- **Not read, no measured count**: `Open Database License` (`ODbL-1.0`) and
  MulanPSL's Chinese title line (`木兰宽松许可证, 第2版`, 0.5 by text, was
  1.0): 0 values in any corpus.
- **A "+" in a sentence** (`Licensed under the MIT++ license`) and **a
  refused "+" at 10 to 29 words** (a compound of ten licences): as before
  the fix of item 44.

- Impact 2, Risk 2, Effort 2.

## 49. Hand a non-standard value from `resolve()` to `detect()` — Priority 12

Noted 2026-11-09, while planning item 43. Some declared values name no
licence on purpose, and the package supplies the text elsewhere:

- Cargo writes `license = "non-standard"` (crates.io field of
  `ring@0.16.20`) when a crate has a `license-file`. `resolve()` rightly
  refuses it; the answer is in that file, which `detect()` can read.
- A licence URL that is not from a licence steward, SPDX or the OSI
  (`ID_PAGES`, `URL_ALIASES`) names no licence either. The page behind it is
  text `detect()` could match. A guess from the URL is not allowed
  (`https://evil.com/licenses/MIT` names nothing), so the text is the only
  source.

Both want the same step: when `resolve()` refuses, say that the value points
at a text (a file or a page), so a caller can run `detect()` on it. Open
questions to design first: who fetches (never the library on its own: no
network in a lookup); how a refusal carries "the text is elsewhere" (a
`reason`, or a field); how the manifest reader (`manifest.py`) passes a
`license-file` or `license_files` entry on; what the CLI does with a path
beside a value.

- Impact 2, Risk 2, Effort 3 (a design item; no code yet).

## 50. Leftovers of item 48 (Tier 0 through `resolve()`) — Priority 10

Left over from the fix of item 48 (2026-11-09, resolved: Tier 0 asks
`resolve()` first). Measured on the 519 distinct values of the PyPI fixture
and the parity corpus: the whole input moved 6 times, a quoted INI field
190 times (all but 7 gained an answer).

Closed, so not listed below: the no-section `license = "MIT OR ISC"`
(PR #219: no answer, `too few words for text`), `looseid.disambiguate_whole`
(decided 2026-11-17: it stays, PR #221 restricted it), the partial
harness database (2026-11-18; PR #223), and a List name wrapped in
marks answering exact (PR #226); see
[`tech-debt-resolved-0-9.md`](../implementation/tech-debt-resolved-0-9.md).

Open:

- **`markers.resolve_license_value` and `_first_resolved`** still hold a
  reader of their own for a tag and a field (`MIT OR MirOS` order, a title
  and an alias are not read by a tag); route them through `resolve()` once
  item 43 has landed in `markers.py`.
- **`identifiers.is_qualified_plus`** (the guard of `_match_text`) repeats a
  "+" refusal of `resolve()` for a value too large to parse; `is_stray_plus`
  is gone (#232, item 58).
- **Two shapes of a wrapped name still answer** (known gaps of the fix of
  2026-11-18, recorded in
  [`tech-debt-resolved-0-9.md`](../implementation/tech-debt-resolved-0-9.md)):
  `*Apache License 2.0*.` (marks after an end mark) and `1. Apache License
  2.0` (a list number): `Apache-2.0`, exact, by name.
- **A `license` field with a mark only at the end** (`Apache License 2.0*`)
  still answers `Apache-2.0`, exact, where `resolve()` and `detect` on a text
  refuse it.
- **A sentence of 10 to 29 words with `MIT++`** is matched by name still
  (`MIT`, inexact; under 10 words it has no answer): only a word ending in
  "+" under 10 words is refused, so a README line with `C++` keeps its
  answer.

- Impact 2, Risk 2, Effort 3.

## 52. Leftovers of `detect --variant` — Priority 12

`detect()` once read a bare `GPL-2.0` as `GPL-2.0-only`, where `resolve()`
keeps it as written. Built and merged 2026-11-16 (PR #211: `exclude` and
`hint` act on free text only; PR #212: `--variant`, the last record field
`VARIANT_STATED`, `EXACT` by list, the twin flags of `is-osi` and `is-fsf`),
recorded in
[`tech-debt-resolved-0-5.md`](../implementation/tech-debt-resolved-0-5.md)
and written up in
[`../implementation/item-52-variant-and-exact.md`](../implementation/item-52-variant-and-exact.md)
(design as built, paths rejected, pinned cases, measures). What is left,
each a decision:

- **For the maintainer to revise**: the warning bar
  `variants.ANSWER_SCORE` (0.85); the grant signal misses a grant only the
  heading marker read (pinned
  `test_a_grant_the_marker_did_not_read_leaves_the_only_form`); whether the
  `-with-` rule of `EXACT` applies to every `deprecated_ambiguous` operand
  (`eCos 2.0` stays exact, as on `main`).
- **Channels that still differ** (rule I1): a deprecated List name (AGPL)
  answers `-only` as the argument under `auto` but the bare ID in a tag or
  a field (pinned `# BUG:` in `tests/test_variant_invariants.py`); a tag
  refuses `GPL-2.0 or later OR MIT` that the argument answers (decided
  2026-11-17: it stays, a tag refuses what it cannot read whole; 0 of 642
  values). A tag refuses `MIT OR GPL-2.0 only` now, as the argument and a
  field do.
- **Grant subject, left** (resolved 2026-11-17: a grant counts for the
  licence it names, `licenseid.grantsubject`; see
  [`tech-debt-resolved-0-9.md`](../implementation/tech-debt-resolved-0-9.md)):
  `markers._resolve_gpl_or_later` and
  `_detect_license_mentions` read a grant of any subject (a bias, settled by
  `variants.settle_text`); `or any version later` is no phrase of
  `OR_LATER_PHRASE` (`has_unowned_phrase` keeps an `-or-later` answer);
  `GFDL-1.3+` is no shorthand grant; a tool's `version N` with no word naming
  it is `(N, None)`; `variantstated.supports` reads any phrase in a declared
  value.
- After a `py-spdx-license` release with `upgrade()`, raise the floor in
  `pyproject.toml` and let it replace the `+` and rename code
  (`DEPRECATED_SPDX_LICENSE_IDS`, the rename rule of `listrules`); the bare
  and `-with-` tables stay with this item. Revisit `EXACT` then: its
  mapping of deprecated IDs settles which renames are List data.
- Found, not caused by this item: the text of
  `deprecated_GPL-2.0-with-classpath-exception` gets no result; three
  identical-text GFDL ties stay exact and wrong (a tie problem).
- Impact 2, Risk 2, Effort 3.

## 54. A truncated ID gets an answer — Priority 12

Found when measuring `EXACT` (2026-11-15; 2,516 inputs, SPDX List 3.29.0, a
sample, not the whole fixture set). Seven inputs that cut an ID short were
`EXACT=true` and wrong or doubtful: `Apache-1` gives `Apache-1.0` and `MIT-`
gives `MIT`. `resolve()` reads them as `version_spelling` and `separator`
(trust `resolver_rule`). Since item 52 (PR #212) a rewrite rule's reading is
not exact, so these are `EXACT=false` now, but they are still answered. A
cut version is a choice, not a spelling: `Apache-1` may mean `Apache-1.0` or
`Apache-1.1`.

- **Measured** (2026-11-16, `main` cbbf3e9): PyPI sample, 463 values: only
  `LGPLv2` (3 projects) is a bare major with a sibling minor; no value ends
  in a dash. sbomminbench (172 distinct inputs) and the parity corpus: none.
  The golden run feeds the loose reader 6 bare majors (`AFL-2`, `Apache-1`,
  `CDDL-1`, `EUPL-1`, `LGPLv2`, `OSL-2`) and 3 trailing dashes. A sweep of
  the List: 35 keys (36 rows, deprecated included) have a sibling.
- **Decided** (owner, 2026-11-16): a bare major the List has another minor of
  is refused (`version ambiguous: <IDs>`, no `detect` answer; `Apache 2` is
  read); an "or later" grant exempts it (`LGPLv2+`, `Apache-1+`,
  `LGPLv2 or later`, `--variant or-later` does not widen it); a run of `-`/`_`
  joined to the end of a loose ID is a dropped character (`MIT-`); tags keep
  their reading (`SPDX-License-Identifier: MIT-` is `MIT`); **changed by the
  owner the same day** ("fix the tag"): a tag cut by a dash or `_` that
  touches the expression is refused too (`dropguard.cut_by_joiners`).
- **Built** (PR #217, 2026-11-16): see
  [`tech-debt-resolved-0-5.md`](../implementation/tech-debt-resolved-0-5.md).
- **Decided 2026-11-17** (owner; record in
  [`tech-debt-resolved-0-9.md`](../implementation/tech-debt-resolved-0-9.md)):
  a dash glued to a comment closer in a tag (`MIT-*/`, `MIT-#}`, `MIT-}`,
  `MIT--]]`) is read as `MIT` on purpose (pinned in `tests/test_cut_tags.py`
  `STAYS`; 0 of 14,743 tag lines under `~/projects` do it); a closer glued to
  a reference's trailing `-`/`_` run (`MIT OR LicenseRef-a-->`, `-}`, `--]]`,
  `-#}`, `-*/`) gives no answer (`dropguard.cut_reference`, pinned in
  `tests/test_reference_dash.py`). "Strip the characters a LicenseRef lacks,
  then the trailing dashes" was weighed (Opus review) and rejected: it gives a
  wrong identity for `*/`, `#}`, `-}`, and turns today's refusals
  (`LicenseRef-a_b`, `LicenseRef-a-ä`) into new references.
- **Open leftovers**: a non-ID character inside a reference cuts it in a tag
  (`MIT OR LicenseRef-a>b` reads `LicenseRef-a`; `resolve()` refuses it), not
  checked against `cut_inside_word`; a refused tag above a licence fragment can
  fall to the text tier (`MIT-0` at 0.914). Fixed by item 47: `License:
  MIT-`, `Licensed under the Apache-1 license`, `MVT-1`, `Sendmail-8`,
  `Apache License 1`.
- Impact 1, Risk 2, Effort 2.

## 55. Publish the lists `resolve()` reads — Priority 12

**Built** (PR #214, 2026-11-16, its own pull request after #212). Decided
2026-11-15 with the `EXACT` rule of item 52: an answer from an authoritative
list is exact, so a user must be able to read each list. They lived in code
only: `resolvealias.ALIASES` (12), `resolvetitle.TITLES` (4),
`trovenames.TROVE_NAMES` (89), and in `resolveurl` `URL_ALIASES` (11),
`SCANCODE_NOT_SPDX` (13), `ID_PAGES` (4 hosts) and `DUAL_PAGES` (2), with
`resolveslash.REFUSED_PAIRS` (2) and `resolveprose.VERSIONED_NAMES` (2): about
140 rows.

- **Built**: `docs/lists.md`, generated by `python -m tools.lists_page`
  (`--check` tests it). `render.py` reads each table from its code object;
  `measure.py` computes what can be measured on the test corpus (the 3.29.0
  List fixtures and the PyPI sample of 2026-10); `evidence.py` holds what only
  a person knows (the source of a row; the survey count of a URL page, whose
  raw data is not committed); `rules.py` the named rules, each linked to its
  function by import, so a rename fails. `tests/test_lists_page.py` fails when
  the page and the code differ and checks that every row has its evidence.
  `docs/lists.md` is in the path filters of `test.yml`.
- **The named rules** (decided 2026-11-16): T1 to T3 (`resolvetrove`) and P1
  to P3 (`resolveprose`) stay named in code and tests. T1 and T2 are exact
  (`trove_name`, or the List's own category); T3 is exact when both parts are
  List names and not when its head needed a rewrite rule (`Apache2
  (Apache-2.0)` is `version_spelling`); P1 to P3 rewrite a value
  (`prose_form`), so they are not exact (rule (c) of item 52). A prose form
  that reduces to a name of a table takes the table's category, the weakest
  of the steps (`New BSD License` is `alias_name`, exact).
- **Growth rule kept**: a row is added only with a measured package count
  (`working-docs/paper-notes/licence-urls.md`); the test requires one for each
  alias and title and each URL page. Four URL pages the List gives a licence
  and its variants are the exception (closed 2026-11-18, PR #223); the dash of
  a trove name with no count is correct (see
  [`tech-debt-resolved-0-9.md`](../implementation/tech-debt-resolved-0-9.md)).
- **Left open**: a command (`licenseid resolve --lists`) or a JSON file with
  the same rows, so a script can read them. Not added: it would be a new CLI
  option (an axis of `tests/test_option_matrix.py`) and the page now exists
  to be read; decide when a script needs it.
- A new list (ScanCode, Blue Oak) gets its page section, its `CATEGORY` and
  its `EXACT` value when it is added (`render.py`). The Blue Oak idea:
  [`blue-oak-ratings.md`](blue-oak-ratings.md).
- Impact 2, Risk 1, Effort 2.

## 58. Honest `EXACT` and warnings: the 0.9.1 scope — Priority 16

Decided 2026-11-19 (maintainer): found by the 0.9.0 doc and API review, each
one a result that claims more than the code knows. Target release 0.9.1.
Rule for every PR: the narrowest fix, no right answer moves on any corpus,
net rules added at most zero (no new regex, list or special case; reuse or
delete), a time check against `main`.

Built as #230 to #233 (2026-11-19); the combined review of the four found
two things to fix after (below). One PR each, in this order (they shared
files):

0. **Free lines in `detector.py`** (#230), no behaviour change:
   `_rank_candidates` scoring moves to `similarity.score_candidates` and
   `similarity.boost_by_fingerprint` (735 to 675 lines). The pylint ceiling
   `max-module-lines` stays 735: `tests/test_option_matrix.py` is 735 too and
   `markers.py` 733; lowering it needs those split.
1. **The encoded "+" in a NuGet URL** (#231). `resolvefirst.is_exact()`
   says yes for `https://licenses.nuget.org/GPL-2.0%2B`, `detect()` says
   no: the variant evidence is the raw URL. Take it from the `license_url`
   step, through the one URL-to-ID reader of `markers.py` (moved to
   `resolveurl`), not a string replace. Regenerate `docs/lists.md`.
2. **No warning for a bare `MIT++`, `MIT +`, `GPL-2.0-only+`, `(MIT)+`**
   (#232). `detector._try_tier0_short_text` returned `[]` for a "+" refusal
   before `too_short` could warn; the quoted forms warn. Built: the
   predicate of a qualified "+" moved to `_match_text`, then `too_short`;
   `is_stray_plus` was redundant and is deleted. `C++` and `g++` warn too
   (true: no licence). **Regression to fix:** a stray-plus value of 10
   words or more once normalised (a long dashed `LicenseRef-*` and a
   trailing plus sign) now reaches Tiers 1 and 2 and can answer (Apache-2.0
   0.80); main gave `[]`. Fix: `_match_text` returns `[]` for any "+"
   refusal of `resolve()` on the whole input, whatever the length.
3. **`EXACT` after a cut mark** (#233). `MIT or later.`, `;`, `:`, `,` gave
   no `separator` step and were exact; `MIT;` is inexact. Built smaller than
   planned: `resolveleaf._single` adds the `end mark` step after the grant
   is read (reusing `trim_end_mark`), and a field is judged by
   `resolvefirst.was_cut` (`ruleread.tag_inexact(raw=)`). No regex change
   (tried: it refuses answers). The category becomes `separator`; the #221
   pin flips on purpose. Built 0.9.2 (`dropguard.grant_end_marks`): a run of
   end marks after a grant (`MIT or later..`) is refused as `MIT;;` is; a
   tag still reads it, and a licence name in a field (`GNU General Public
   License v2.0 or later..`). Known gaps left, in `docs/resolve.md`: a closing
   bracket after one end mark (`MIT or later.)`) is `MIT+`, exact; a wrapped
   value with a stray mark (`(GPL-2.0 or later).)`) answers exact in `detect`
   where `resolve()` refuses it; a tag `MIT. AND ISC` answers `MIT`, exact,
   and drops ISC (item 46; the argument and a field give `ISC AND MIT`,
   inexact, as `MIT or later. AND ISC` does in all three); the steps after
   the end-mark step of `GPL-2.0 - or later.` still read the mark (no chain
   check).

Bug 4, `Python-2.0` for `GNU General Public License version 2.0, requires
Python 3.8 or later`: a class (a short name whose words are scattered beside
a licence named whole without its grant), fixed after 0.9.1 by widening
`namehits._names_another`, not by a rule for one sentence (PR #235). Left:
`General Public License version 2.0, requires Python ...` (no "GNU") and
`GNU General Public License v2. Requires Python 2.0 or later to build`.

Not fixed, by decision (2026-11-19): `GPL-2.0 or later MIT` (a licence after a
grant without an operator), `MIT only AND Apache-2.0` and `GPL-2.0 only,
never any later version` (contrived, not seen in real text).

Other leftovers of the review are in the maintainer's `later.md` of the
0.9.0 release folder (CLI argument and `ELOOP`, `LicenseDatabase` path
types, `SISSL`, three ScanCode keys that could be read).
Impact 3, Risk 3, Effort 2.

## 63. `HPND/DOC` is refused where `DOC/HPND` reads — Priority 12

Found by `--run-benchmark` before 0.9.2 (2026-11-24),
`test_resolver_slash_props.py::test_all_pairs_read_as_or`; v0.9.1 gives the
same. `resolve("HPND/DOC")` refuses with `character dropped: U+002F`, while
`DOC/HPND` and `HPND OR DOC` give `DOC OR HPND`. A refusal, so no wrong
answer, but the slash reader should read both orders alike. Find the reader
that claims `HPND/...` before `resolveslash`.

Found again on 2026-11-28 by the benchmark run of 0.10.0, without this item
read first. The reader is the loose ID: `HPND-doc` and `HPND-Intel` are List
IDs, so `HPND/DOC` and `HPND/Intel` are each one ID with a dropped
character. They are the only two of 547,600 ordered pairs of List IDs; the
test fails on every tag from 0.8.4. In 0.10.0 the test and `docs/resolve.md`
state the refusal (PR #250), which made the benchmark green; that pins
today's answer and does not close the item. Three readings stay open: no
answer (now), `DOC OR HPND` (both orders alike, as above), or the one ID
(`HPND-doc`). The PyPI sample holds no such value: count real ones before
choosing.

Decided 2026-11-28: no answer stands until real values are counted (the
registry entries of the sbomminbench project are one place). The item
stays open as that measurement.

Impact 2, Risk 2, Effort 3.

## 79. Licence families and the relation of two licences — Priority 14

From Pitloom (2026-11-28; its brief is
`working-docs/implementation/licenseid/licence-families-handoff.md`, last
checked on 0.9.4). Pitloom compares the licence a package states, often a
trove classifier such as `BSD License` or `Apache Software License`, with
the ID detected from its licence file. A generic name and a specific ID of
one family is a narrowing, not a conflict, and no licence tool should keep
its own family table.

Asked for, as additions: `in_family(licence, family)` and
`family_of(licence)`; richer and optional, `relation(stated, detected)`
giving `same`, `narrowing`, `widening`, `disagree` or `unknown` with its
basis. Start from `trovenames` (`TROVE_NAMES` reads the generic names as
none; its docstring defers "reading by usage").

Before any code, answer the brief's seven questions in a working note, and
stop for the maintainer where one is a product decision: how a family is
named; whether a licence has more than one (`MIT-0`, `0BSD`); where the
data comes from (the classifier list, the List, a table of ours) and
whether it follows `TROVE_CLASSIFIERS_VERSION`; what a licence with no
family answers; how `-only`, `-or-later`, `AND` and `OR` map onto narrowing
and widening; whether free-text short names (`BSD`, `Expat license`) are
read; how a narrowing is reported.

Decided by the maintainer, 2026-11-28 (the working note starts here):

- **Name.** A family is named by its trove classifier (`BSD License`); no
  names of ours. `family_of("BSD-3-Clause")` gives that name.
- **Data.** A table of ours beside `TROVE_NAMES`: each row with its source
  and a measured count of real packages, on the generated lists page,
  pinned to `TROVE_CLASSIFIERS_VERSION`. The List has no family field. Its
  ID prefixes (`BSD-` 43 IDs, `GPL-` 19, `LGPL-` 12, `Artistic-` 5,
  `Apache-` 3, `ZPL-` 3) and names may propose rows and never answer alone:
  they take in `GPL-2.0-with-GCC-exception` and `BSD-Protection`, miss
  `0BSD`, and `AMPAS` has "BSD" in its name.
- **No classifier.** A family that no classifier names (Creative Commons,
  EUPL, CeCILL) answers nothing until a consumer shows packages that need
  it, with a count.
- **Scope.** `in_family()` and `family_of()` first; `relation()` waits, and
  with it the rules for narrowing and widening of `-only`, `-or-later`,
  `AND` and `OR`, and how a narrowing is reported.
- **Many or none.** `family_of()` gives a tuple, empty for none. Several is
  real: `GPL-3.0-only` is under `GNU General Public License (GPL)` and
  under `GNU General Public License v3 (GPLv3)`, as is every GPL and LGPL
  version. Still to decide by a count, row by row: `0BSD` under `BSD
  License` (it has a classifier of its own), `Python-2.0` under which
  Python classifier. `MIT-0` has its own and is not `MIT License`.
- **Short names.** Free-text names of a `License` header (`BSD`, `Expat
  license`, `PSFL`) are not read: classifiers only. In Pitloom's 15
  packages each such header has a classifier that answers.
- **Input.** One licence only: an ID, its `-only`, `-or-later` or `+` form
  read as that licence's family. An `AND` or `OR` expression answers None.

Of the 35 classifiers that name no ID today, 10 are not licences
(`Freeware`, `OSI Approved`, `Public Domain`, ...) and 25 name a licence or
a family (`BSD License`, `Artistic License`, `GUST Font License 1.0`):
which of the 25 are families is the table's first job.

Done when: the note is agreed, the functions answer Pitloom's cases with
tests, `docs/python-api.md` describes them, and Pitloom can drop its table.

Impact 4, Risk 3, Effort 4.

## 80. Pitloom's findings 2 to 10 on the contract — Priority 15

From Pitloom (2026-11-28; its file `upstream-issues.md` under
`working-docs/implementation/licenseid/`, "Index of findings" and "Issue
text", each with a reproducer; last checked on 0.8.4, findings 1 and 11
fixed in 0.7.2 and 0.7.3). For each: fix it, document the behaviour as
intended, or say why not, and list the workaround Pitloom could then drop.

- 2: which characters are white space (`\x0b`, a lone `\r`, U+2028,
  `\x1f` between operands).
- 3: `coverage` above 1 (up to 1.18 on real texts; Pitloom clamps it).
  Still so on 0.10.0: 1.0179 for a verbatim Apache-2.0 file.
- 4: messages of the API name `--db` and a command that needs the network
  (Pitloom prints its own line naming `--source packaged`).
- 5: when a database warning is given once is not documented.
- 6: the List names of deprecated IDs resolve to nothing (`GNU Free
  Documentation License v1.3`; Pitloom keeps 14 names of its own).
- 7: an answer of `trust: none` is hard to use (`GPL-3.0`, `GPLv3`;
  Pitloom special-cases the category).
- 8: `components` is empty for most answers.
- 9: the database is a black box: `LicenseDatabase` is public with 15
  methods and no word on which are stable.
- 10: a non-ASCII space before "or later" is read with no step.

Only finding 3 was run again here; the rest wait for the work itself.

Decided by the maintainer, 2026-11-28, each to be checked against the
reproducer on the current release first:

- 3: the public result caps `coverage` at 1, as it caps the score; ranking
  keeps the raw value. No key changes.
- 4: one message for the CLI and the API, and its action names the offline
  form too (`--source packaged`); a hint raised to an API caller names
  `db_path`, not `--db`.
- 6: a deprecated ID's List name is read as that ID is read: same category
  and candidates.
- 7: no new key. A short table in `docs/resolve.md` says what to do with
  each `trust` value (record, record with a note, do not record).
- 8: document the rule: a component is named only when it took part in the
  reading. No value moves.
- 9: document a small read API of the database as stable (the List's
  version, its IDs and names, one licence's details) and say the rest may
  change. No rename.

Findings 2, 5 and 10 have no decision yet.

Impact 3, Risk 2, Effort 3.

## 81. A licence file that is one `SPDX-License-Identifier` line — Priority 15

A question from Pitloom (2026-11-28; the open entry "An
SPDX-License-Identifier line in a licence file is read as text" of its
`working-docs/design/known-bugs/licences-and-licenseid.md`): should
`read_license_text`, or a helper, see that a licence file holds only that
line and return its expression? Pitloom records such a file as custom text.
Answer first whether this belongs in licenseid or in Pitloom; no code
unless the maintainer agrees.

Answered 2026-11-28: in Pitloom. `detect()` already reads such a file: one
line `SPDX-License-Identifier: MIT OR Apache-2.0` answers `Apache-2.0 OR
MIT`, method `tag`, exact (0.10.0); `read_license_text` is Pitloom's own
function. Pitloom can take an answer whose method is `tag` as the stated
expression. Left here: an example of that case in `docs/python-api.md`.

Impact 2, Risk 1, Effort 1.
