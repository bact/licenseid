---
Created: 2026-08-19
Last-Modified: 2026-11-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Tech debt roadmap

See also:
[`complexity-and-file-size-roadmap.md`](complexity-and-file-size-roadmap.md)
for code-health/complexity debt specifically. This doc and the two
files it names below track the rest.

Priority = (Impact + Risk) × (6 − Effort), each scored 1-5; same scale as
the complexity roadmap, so the two lists can be read together.

Item numbers are the roadmap's own and never reused: a gap is an item in the
reading file or the data file below, or a resolved item, kept in the four
files under "Already resolved" at the end. Each open item says where it
came from. Item 51 (decided
and pinned, 2026-11-17), 53 (a known limit, 2026-11-18), 56 (a hang in the
CLI matrix, found 2026-11-16), 35 and 67 (the marker floor, 2026-11-25) are
resolved. Items 55 (PR #214, 2026-11-16), 54 (PR #217, 2026-11-16), 47
(PR #219, 2026-11-17) and 57 (2026-11-26) are built; their leftovers stay open.
Item 2 (data file) waits on an upstream release. Release 0.10.0
(2026-11-28) is the
new detection engine (PR #249). Next: item 68, then items 69 and 70
(decided 2026-11-27); after or beside them what Pitloom reported on
2026-11-28: item 13 here, items 79 to 81 in the reading file. Items 71 to
75 were found while that engine was built; 72 waits on 71. Items 76 to 78
(2026-11-28) are for after 0.10.0. The open items
that need a rule or a decision before a fix are grouped in
[`matching-rules-redesign.md`](matching-rules-redesign.md) (2026-10-02); item 31
is that revision.

The open items on reading a declared value or a name (`resolve()`, the
name tier, `--variant`, `EXACT`, the lists page: items 26, 46, 47, 49, 50,
52, 54, 55, 58, 63, 79, 80, 81) are in
[`tech-debt-roadmap-reading.md`](tech-debt-roadmap-reading.md), split
2026-11-24 at the size limit.

The open items on the database, the environment, the cost of a call and
the user docs (items 2, 10, 57, 62, 65, 66, 75, 76) are in
[`tech-debt-roadmap-data.md`](tech-debt-roadmap-data.md), split
2026-11-28 at the size limit. This file keeps text matching.

## 28. A two- or three-word phrase from a licence text scores 1.0 — Priority 10

Any short phrase found verbatim in a licence text answers that licence with
certainty. `license identifier`, or an `SPDX-License-Identifier:` tag with
no value, answers `CAL-1.0` at 1.0, and `is-osi` then says yes. `main`
behaves the same; found in review of PR #66 (2026-10-01).

A tag that is no expression used to fall through to Tier 0 the same way:
under 30 words, `SPDX-License-Identifier: MIT OR` answered MIT at 1.01.
Fixed in PR #67, where refusing `LicenseRef-MIT+` made its tag answer MIT
too: Tier 0 now matches the input without its tags, which Tier 0.5 has
read (`MarkerDetector.without_spdx_tags`).

A single word that is part of a licence's name answered it at 1.0 the same
way, through the token-set name match (review of item 22, 2026-10-02):
`BSD` answered `0BSD`, `the` answered `MirOS`. Fixed in PR #168: words a
longer name only holds are no name. Under ten words, PR #161 already gives
no text match to an input `resolve()` refuses, so what is left here is a
phrase of ten words or more that several licences share
(`Redistribution and use in source and binary forms, with or without
modification, are permitted` answers BSD-2-Clause at 1.0). The leftovers of
PR #168 are item 47.

- **Measured 2026-11-25** (plan of item 67): this is not the marker floor. The
  phrase scores 1.0 in Tier 2 (fragment similarity 1.0, `text_evidence` 1
  from 40 characters, coverage 0.07), and several licences tie at 1.0 (the
  BSD phrase: BSD-2-Clause and BSD-2-Clause-Darwin; the MIT grant phrase and
  the warranty line: Clips). The rule "a fragment that several unrelated
  texts hold at 1.0 gives no answer", on the short fixtures: 569 answers tie
  at public score 1.0 with another text group; it would remove 327 wrong
  answers and lose 242 right ones, and move hundreds of `detect_short.tsv`
  rows. Its own PR under item 31 (certainty of a fragment), with a rule that
  keeps a fragment's unique words as evidence: Effort 4, Risk 3.
- **Direction**: a verbatim hit on a few words is evidence, not an answer.
  Cap the score of a Tier 0 text hit below 1.0 when the phrase is shorter
  than some minimum, or require it to cover a share of the licence's
  distinctive words, so `is-*` answers no for it.
- Impact 2, Risk 2, Effort 2.

## 31. Revise the matching rules: grammar, certainty, ranking — Priority 12

Come back to this and think it through systematically, for one consistent
answer: so far each fix has patched the one case that was found. Whether a
value is an SPDX expression is decided in several places, each with its own
partial grammar:

- `identifiers.leading_expression` (where an expression ends in a value);
- `identifiers.is_simple_expression` and `_SIMPLE_SHAPES` (one license);
- `plusoperator.PLUS_OPERATOR` and `strip_plus_operator` (which "+" is
  the operator, since `py_spdx_license` cannot parse it);
- `identifiers.parse_expression` (`py_spdx_license` with unknown IDs
  allowed, behind the cost budget of item 26);
- `exprflags.expression_flags` and `markers._synthetic_candidate` (a
  recognised ID);
- `identifiers.qualify_trailing_grant` and the deprecated-ID tables.

Cases found one at a time: a "+" after an exception (PR #61), a dangling
operator or an unbalanced bracket (PR #61), a "+" after a `LicenseRef-*`
(review of PR #67: it answered as a valid SPDX license from a tag, `--id`
and text), and "or later" after an ID with no or-later form (review of
PR #68: `SPDX-License-Identifier: MIT or later` answers `MIT OR later`,
as if `or` were the operator and `later` an ID). Each time the rule went
into one place, and the others were checked by hand. Found on 2026-10-01;
the user asked to return to it.

**Decided (2026-10-01)**: no more one-off fixes of these edge cases. The
last were in PR #67 (a "+" after a `LicenseRef-*`, and a short input's
refused tag matched as a name). The next step is a revision of the
license matching rules as a whole, of which this grammar is one part:
which tier may answer what, and with how much certainty (item 28 is the
same question for short text; item 30, resolved, was another).

**Ranking (2026-10-02)**: rethink the internal ranking in the same
revision. Each tier ranks on a key of its own scale (a tag 1.0, an exact
name or ID 1.0 or 1.02, a look-alike name 1.01, a text match up to about
1.08 with its bonuses), and the tiers never meet in one list, so the scales
were never made comparable. Item 22 caps the public score to 0-1 and adds
`exact`, which keeps the order but shows several answers at 1. Separate
certainty (how the answer was found, and whether exactly) from closeness
(how alike), and rank on both, so that a capped score is no longer needed.
Decide there too what an exact text is: item 22 asks for the whole input
equal to the License List's text after normalisation, so a filled-in
copyright line or a title makes a real licence file not exact, where the
SPDX matching guidelines let both differ (replaceable and omittable text).
A text with a leading byte order mark (BOM) given as `--text` keeps it and
is not exact, though the same file is.

- **Areas and decisions**: grammar, certainty and ranking are areas 1-3 of
  [`matching-rules-redesign.md`](matching-rules-redesign.md).
- **Direction**: one reader for the SPDX grammar (Annex D:
  `license-id ["+"]`, `license-ref`, `WITH`, `AND`, `OR`, brackets, and the
  case rules for operators and prefixes) that returns a typed tree, with
  the other judges derived from it; and a table-driven conformance test
  written from the grammar, not from the bugs. Decide `NONE` and
  `NOASSERTION` there too. Weigh delegating to `py_spdx_license` once it
  parses "+" (upstream issue #1) in linear time (item 26).
- Impact 2, Risk 2, Effort 3.

## 11. Probe-anchored windowing — Priority 15

The one large remaining lever on `fragment_similarity`'s dominant cost:
reuse the existing 60-word probe's match location instead of re-running
a full realignment scan. Deliberately deferred because it changes
the window that the CLI's `--diff` flag shows (recomputed through
`diff_pair`), not just an internal ranking score — needs its own
validation cycle (a `bench_compare.py` run plus a manual `--diff` output
quality check).

- Re-scored 2026-09-30 (Impact 2 → 3): ordinary license text pays for it,
  not only crafted input. On the real database a 3,000-character slice of
  Apache-2.0 (a probed query) takes 9 s, because many similar licenses pass
  the probe and each gets a full scan of the whole query. The scan's cost
  follows the query's characters (item 16), and item 16's guard does not
  apply: this query is prose, and its fixture twins (`head_3000`) must keep
  their answers. Blob around a licence-like middle pays it too: 200 words of
  Apache-2.0 among 120 random 25-character tokens (4,426 characters) takes
  134 s, as 141 candidates pass the probe and each scan takes about 1 s.
- `--diff` shows the window as RapidFuzz aligned it, which can start or end
  inside a word, so its first and last lines can be word fragments (review
  of item 22, 2026-10-02). Snap the window to word boundaries here too.
- Impact 3, Risk 2, Effort 3.
- Full plan:
After the engine of 0.10.0 (2026-11-28): the two inputs of the CPU table
(`roadmap:11`) take 17.79 s to 0.05 s in the final gate run
(`L27-vs-0.9.4-final.txt`, against 0.9.4). Tier 2 aligns a region the word codes
locate (`../implementation/word-region.md`), and `--diff` widens its
window to whole tokens. Open: the by-hand read of `--diff` output on
fragments, which the final run did not measure.

## 7. GPL/LGPL/AGPL family disambiguation (tail recall floor) — Priority 12

`tail_300`-`tail_500` benchmark subcategories lose 28-35 fixtures out of
top-50: GPL/LGPL/AGPL family members share boilerplate warranty text, so
a short tail-only fragment can't distinguish them by text similarity
alone.

- **Fix**: family-aware disambiguation using version number and/or the
  supersession chain (`superseded_by`) already in the DB schema, as a
  tie-breaker when top candidates are all in the same license family.
- Impact 3, Risk 3, Effort 4.
- See [`optimization-recommendation.md`](optimization-recommendation.md)
  ("Remaining open issues", item 5) for the original benchmark analysis
  this is based on — note that document predates the deprecated-ID fixes
  described in its own status note and has not been re-benchmarked since.

## 13. Apache-2.0 vs Pixar near-duplicate confusion — Priority 15

`Pixar` is `Apache-2.0` with a modified section 6 ([`new-matcher.md`](new-matcher.md)
has the word counts). Apache-2.0 without its appendix answered Pixar until
the core text (PR #239); a verbatim Pixar text answers Pixar.

Open, from Pitloom (2026-11-28, found on 0.9.4; its known-bugs entry "A
dependency's Apache 2.0 file with no licence stated stays unread", and
`bact/pitloom` issues 286 and 570): a verbatim Apache 2.0 file answers
`Apache-2.0` 1.0 with `Pixar` 0.995 beside it, a near-tie Pitloom leaves
undecided when nothing else is stated (rfc8785 0.1.4, rfc3161-client,
sigstore-rekor-types). Same on 0.10.0 for rfc8785's file: `Apache-2.0`
1.0000, `Pixar` 0.9947, `ImageMagick` 0.9871, and `TEXTS=Apache-2.0` on
each row, the evidence item 68 reads. Done when an unmodified Apache 2.0
text is decisively `Apache-2.0` (Pixar's clause is absent), with that file
as a fixture, and a real Pixar text still answers `Pixar`. Decided
2026-11-28: a runner-up that `TEXTS` does not name is not listed beside a
text found whole, so that file answers `Apache-2.0` alone.

- Impact 3, Risk 2, Effort 3.

## 61. Leftovers of the core text and the notice-free query — Priority 12

From the review of PR #239 (2026-11-24); none answers worse than `main`.

- **Cost.** A text whose copyright notices change Tier 1's top 10 scores
  about 100 candidates where `main` scores 50, each long one aligned as a
  fragment: 1.24x to 1.98x `main` where `main` is right, 4.8x for MIT under
  two copyright lines, which `main` gets wrong. Idea: a cheaper first pass
  on the added candidates only, measured as in AGENTS.md "Performance".
- **Cores alike.** OLDAP-1.1/1.2 and OLDAP-2.2.2/2.3 have one core: a core
  copy scores 1 for both. Dropping shared cores answered NBPL-1.0 instead.
- **Not retrieved.** HPND's core under "Copyright 1995 Acme Inc." finds no
  HPND among 96 candidates and answers HPND-Pbmplus (`main`: HPND-SMC).

Details: `../implementation/accuracy-optimizations.md` sections 12 and 13.
Impact 2, Risk 2, Effort 3.

After the engine of 0.10.0 (2026-11-28): the nine inputs of
`roadmap:61` take 3.76 s to 0.11 s (`L27-vs-0.9.4-final.txt`). The notice-free
query is removed with the FTS5 query, so the cost part goes; where the
report shows a first row (MIT, ISC, 0BSD, HPND, RHeCos-1.1 and others
under copyright lines) it is the same on both sides. Open: cores alike
(OLDAP) is untouched; the recall cases are not read apart from this run.

## 68. `TEXTS` as ranking evidence — Priority 18

Next: after the new detection engine of release 0.10.0, which changes the
ranking and the whole-text search this item reads; measure the 25 files again
on it first.

Left by item 59 (2026-11-26; `../implementation/whole-texts.md`, section 9).
On 25 of 596 real files `TEXTS` names one text and the top is a look-alike of
it under 0.85 (MIT under DocBook-XML, JSON, ICU, curl, Unicode-DFS-2015), so
there is no answer though the file holds a whole List text; the record of no
answer now shows it (`REASON=below threshold`, `TEXTS=MIT`). Idea: where the
search finds one text whole and the top is a look-alike, rank the text found
first. It makes answers, so measure what it adds wrong (real files, the
synthetic bundles, every fixture) before taking it: precision over recall.

Pitloom (handoff of 2026-11-26, items C1 and C2): wcwidth's `LICENSE` (the MIT
text, then a three-line grant) answers `JSON` 0.9238 above `MIT` 0.9197, with
`TEXTS=MIT` on both: a wrong answer above the threshold, not only a missing
one. mypy_extensions (one line, then the MIT text) gets no answer. The 0.9.3
records of no answer hid `TEXTS`; item 59 shows it. Item 64 (2026-11-26,
built) finds a project's own text where it fills the template's variable
parts: the first ID of `TEXTS` is now `BSD-3-Clause` in sympy 1.13.1 and in
numpy 2.4.6 `LICENSE.md` (both `MIT` before), `MIT-CMU` in Pillow 11.2.1
(`MIT`) and 11.3.0 (`BSD-2-Clause`). Measure this item on top of it: the
fragments of the HPND family that name a neighbour once the variable parts
cost nothing (item 64's fixture numbers) must not become answers.

Impact 3, Risk 3, Effort 3.

After the engine of 0.10.0 (2026-11-28): a text found whole ranks first
(task T5). `roadmap:68`, 27 inputs, takes 14.59 s to 0.44 s; the HPND
family gate shows no new answer; labels agree 182 to 193
(`L27-vs-0.9.4-final.txt`).
Of the 14 real files with one text in `TEXTS` (measured on the T5 tree,
`../implementation/whole-text-first.md` section 6): 8 answer, 4 name it
in the top row under 0.85, 2 stay as they were (guard). Open: those 2,
and `real:f3b34c66` at 211 ms (item 78); the 25 files were not read again.

## 69. A Mozilla Public License header as a notice — Priority 16

Next: after item 68.

Pitloom (handoff of 2026-11-26, item C6): certifi's `LICENSE` holds the
standard MPL-2.0 header ("This Source Code Form is subject to the terms of the
Mozilla Public License, v. 2.0 ...") between `BEGIN LICENSE BLOCK` and `END
LICENSE BLOCK`, and gets no answer (top `EFL-2.0` 0.51); an Apache-2.0 header
answers as a notice. The made-up case `mpl-header-notice` in
`tests/fixtures/several-texts/cases.json` pins today's no answer; the
long-text fixture database holds no MPL-2.0 text, so add it there first.

Impact 2, Risk 2, Effort 2.

## 70. Exception texts in a file — Priority 12

Next: after item 69; design first.

Pitloom (handoff of 2026-11-26, item C5): numpy's `LICENSE.txt` holds the
whole GCC Runtime Library Exception 3.1 after the GPL-3.0 text; `TEXTS` names
`GPL-3.0-only` and no exception (documented in `docs/output.md`). Pitloom asks
whether exception texts can be found and named, or at least flagged. Design
first: `TEXTS` holds licences only, and a `WITH` expression would be a
conclusion, not a finding.

Impact 2, Risk 2, Effort 3.

## 71. Store the List's standard licence headers — Priority 14

Next: after release 0.10.0 (decided 2026-11-27); measure first.

The List gives a `standardLicenseHeader` for 79 licences in use (3.29.0): the
notice a source file carries. The database holds none (only each licence's
text and its core), and hand-written rules in `markers` read the GNU ones
alone (12 of the 79). Measured while 0.10.0 was built (the 79 headers as
given; right, wrong, no answer at 0.85, same-text twins counted as one):
0.9.4 56, 11, 12; the 0.10.0 engine 54, 10, 15. With the placeholder lines
taken out: 52, 13, 14 and 49, 15, 15. Wrong on both: the GFDL-1.2 and 1.3
`-only` headers answer the GFDL-1.1 forms, `LGPL-2.0` and `LGPL-2.1` swap,
`Pixar` answers `Apache-2.0` (item 13). No answer on both: the AFL headers,
`UCL-1.0`, `SSPL-1.0`, `W3C`. The 0.10.0 engine also answers GFDL-1.1 for
the GFDL-1.2 `-or-later` headers (and the cut 1.3 ones), which 0.9.4 had
right by 0.014: their wording is the GFDL-1.1 text's own notice, only the
number differs, and such near ties move with the window Tier 2 aligns (it
gains `GPL-2.0-only` cut the same way). A header known as a text ends that.

Idea: a header is a second text of its licence, in the gram postings and the
whole-text search of 0.10.0; an input that holds it whole names that ID, and
the `-only` or `-or-later` form comes stated, not guessed. It could replace
the hand-written GNU patterns. Open before a design:

- Measure on real source-file headers first (wrapped, in comment marks,
  edited): the 79 clean headers are not what files hold.
- A header inside a licence's own text (the GPL's appendix) is not a second
  text; a header beside another licence's text (an Apache-2.0 header above a
  BSD-3-Clause text, item 68's file) is.
- Whether a header is in `TEXTS`, and under which `method`.
- The header's own template marks (`<alt>`, `<optional>`) go through the
  template reader.
- The data changes in all three sources (`compact`, `upstream`, `packaged`)
  and in the bundle format.

The benchmark harness of 0.10.0 keeps the 79 headers as a set, in both
forms. Release 0.10.0 ships two to three right answers short of 0.9.4 on it
(accepted 2026-11-27); this item is done when both forms beat 0.9.4's 56
and 52 right with no more wrong.

Impact 4, Risk 3, Effort 4.

## 72. A fragment that several List texts hold names one of them — Priority 18

Next: after item 71 (decided 2026-11-27: not in 0.10.0).

A fragment that two licences' texts hold word for word scores the same
against both; the sort decides which ID is printed. Measured on 12,136
slices of List texts (8 to 120 words; truth: the texts that hold the slice
whole), 2,557 of them held by several licences: 0.9.4 names one holder in
1,953 and another licence in 30; the 0.10.0 engine 1,989 and 3. The MIT grant
sentence answers `Clips`; a BSD disclaimer paragraph `BSD-2-Clause`.

Rule measured, not built: no answer when another licence's text scores the
same, or both hold the input whole (same-text twins and the `-only` and
`-or-later` forms are one licence; an exact text is exempt). It takes 1,963
of the 1,989 away and no real file of 300 moves, but it also refuses the
standard `GPL-3.0-or-later` header (`LGPL-3.0-or-later` holds the GPL's
text), the `BitTorrent-1.0` header and the Apache-2.0 header without its
copyright line (`FSL-1.1-ALv2` holds it). No reader of today settles those:
the name tier reads a bag of words, and `grantsubject.grants` loses the family
at "either version". Hence item 71 first. Also measured:

- "Holds the input" must ask the stored word codes (the input's codes as one
  run of the text's), not a similarity of 1: `token_sort_ratio` ignores word
  order and a window can end inside a word, which cost 4 right answers.
- The fingerprint bonus goes to the one text that lists a phrase several
  hold; giving it to all, or to none, loses real files (labels agree 187 to
  182 to 185): leave it.
- The cap of 20 candidates can cut inside a group of equal gram scores (81
  texts hold one BSD disclaimer); the rule above refuses every such input.
- What a tie prints is open: a new `REASON`, or the rows without an answer.

Impact 3, Risk 3, Effort 3.

## 73. A GNU header that `markers` reads right gets another answer — Priority 20

Found 2026-11-27 with item 71's headers. `markers` reads all 12 GNU standard
headers as their own ID, yet `detect()` answers `LGPL-2.0-only` (0.88) for
the `LGPL-2.1-only` header and `LGPL-2.1-only` (0.89) for the `LGPL-2.0-only`
one, and gives no answer for the `GPL-3.0-only` and `AGPL-3.0-only` headers
(their own ID at 0.84): the text match outranks the marker's reading. Same in
0.9.4. Find where the marker candidate loses (the floor, the merge, the
ranking) before a fix; it belongs with item 7.

Impact 3, Risk 2, Effort 2.

## 74. Filters of `detect()`: names under `only_common`, markers — Priority 12

Left by the filter rule of 0.10.0 (2026-11-27; `gramselect.beyond_bar`,
`idoptions.free_text_hits`; `../implementation/gram-candidates.md`, section
8). `only_common` does not act on name hits: of 1,416 sentences naming a
List licence, 828 that name a rare one still answer it. A marker candidate
is not cut with its text: the `GPL-3.0-only` text with both GPL-3.0 IDs
excluded answers `AGPL-3.0-only` (0.99), because the text names it; cutting
every marker whose text was cut removes 7 wrong answers and 5 right ones on
the whole-text sets, so it needs a better rule. `exclude` with a `hint` of
the near text answers it: the caller's own choice, left.

Impact 2, Risk 2, Effort 3.

## 77. A text that holds another List text, its own part edited — Priority 15

Found 2026-11-28 by the review of 0.10.0; left to after it (decided the same
day). Thirteen pairs of List texts hold one another whole: `MPL-1.1` in
`NPL-1.1`, `Caldera-no-preamble` in `Caldera`, `SSLeay-standalone` in
`OpenSSL`, `ANTLR-PD` in `ANTLR-PD-fallback`, `SSH-short` in `SSH-OpenSSH`,
`Linux-man-pages-copyleft-2-para` in four texts, the `GPL-3.0` text in the
`LGPL-3.0` one. The gram score is the share of the smaller side, so the
inner text scores 1.0 and the outer one, which shares more grams, can fall
out of the selection. With every fifth word of the outer text's own part
replaced, `NPL-1.1` answers `MPL-1.1` (0.96), `Caldera` answers
`Caldera-no-preamble` (0.86) and `ANTLR-PD-fallback` answers `ANTLR-PD`
(0.92); 0.9.4 answers them right. Edits a file would have (a fork renamed,
the amendments edited: 10 inputs) move nothing.

A fix was built and taken out again. Its rules: Tier 2 also scores the one
text that shares strictly the most grams, and a runner-up whose text holds
the text found whole is not left out (decision Q1). They brought back 8
answers. An independent review then found 17 right answers turned wrong and
7 wrong answers where there was none, at 0.85:

- The inner text with the first words that follow it in an outer text, or
  without its first five to seven words, answers an outer text at 1.0
  (`Linux-man-pages-copyleft-2-para` as `Latex2e-translated-notice`,
  `SSH-short` as `SSH-OpenSSH`): Tier 2 aligns a short input with the best
  window of a long text, and the inner text, compared whole, gets 0.99.
- A whole short licence with a fragment of a long one answers the long one
  (`ISC` with a tenth of `CC-BY-SA-4.0`: 0.91), while `TEXTS` names the
  short one.
- The added text costs up to 24 times the call on such inputs (5 ms to
  0.12 s).

A narrower form was measured on the review's sets only (not the speed gates,
not the golden): add the text that shares the most grams only where its text
holds a selected text, and keep a runner-up that holds the text found only
where it shares strictly more grams than every member of the group and every
other such runner-up. It gives back all 24 and keeps `NPL-1.1`, `Caldera`
and `OpenSSL`; `ANTLR-PD-fallback` and a `Sleepycat` fragment stay lost. It
is two rules for thirteen pairs: weigh that against closing the item.

The inputs, both reviews' scripts, the answers of each tree and the rules as
built are kept outside the repository (`.claude/speed-0-10/reviews/`). The
`HPND-sell-variant-MIT-disclaimer-rev` fragment that 0.10.0 answers as
`HPND-sell-variant` (0.97) is a neighbour, not this: no text there holds
the other.

Done when: the nested inputs answer the outer text with no answer lost on
the review's sets, the speed gates and the golden, or the item is closed as
inputs no file has.

Impact 2, Risk 3, Effort 3.

## 78. Engine leftovers of the 0.10.0 review — Priority 12

Found 2026-11-28 in the review of the 0.10.0 engine; left to after it. The
figures are CPU time of one call, measured on 0.10.0 and 0.9.4.

- A short text that quotes a long licence costs whole alignments:
  `freertos-exception-2.0` with 3 % of its words changed takes 0.18 s, 2.6
  times 0.9.4 (0.07 s). The gram score selects three GNU texts of 19,000 to
  25,000 characters, the words do not place the input in them (word
  alignment under 60), and each gets a character alignment of about 70 ms;
  0.9.4 only probed them. A cure moves scores.
- The real file of item 68 (`real:f3b34c66`) spends its time in one alignment
  of the whole Apache-2.0 text, the same call 0.9.4 makes: no bound by counts
  keeps the score (under 0.6 the alignment score is the similarity). It takes
  211 ms against the plan's limit of 200 (2,059 ms in 0.9.4): accepted for
  0.10.0 by the maintainer on 2026-11-28.
- Memory on a very long input stays above 0.9.4: 300,000 Han characters peak
  at 90 MB against 69 MB; 1 MB of two-letter words at 121 to 138 MB against
  118 MB.
- Old, same in 0.9.4: a 3.6 MB minified blob with no white space answers
  `MIT` (0.9025) through the name tier (1.8 s now, 49.7 s in 0.9.4); a Han or
  kana text wrapped again every 17 characters scores 0.49 to 0.85; fragments
  of `EUPL-1.2` answer `EUPL-1.1` (0.89).
- `popular=` passed to `variants.settle_free_text` at the Tier 0 call in
  `detector` decides nothing (short-text rows carry no popularity); at Tier 2
  it settles only an exact tie of scores between popularity 0 and 1 (marker
  candidates). A candidate for removal.
- Under the answer bar, on 12 many-text files distorted by 5 %, no text is
  found whole and the rows are what the selection gives; lower thresholds
  (0.8, 0.75) answer 17 and 18 files right and 8 and 9 wrong, about as 0.9.4
  (20 and 22 right, 8 and 10 wrong).

Done when: each is fixed or decided not to be, with its number measured again.

Impact 2, Risk 2, Effort 3.

## Already resolved

Kept out of this file to stay under the size limit: resolved before 0.5.0 in
[`../implementation/tech-debt-resolved.md`](../implementation/tech-debt-resolved.md);
from 0.5.0 on in
[`../implementation/tech-debt-resolved-0-5.md`](../implementation/tech-debt-resolved-0-5.md);
from 2026-11-17 in
[`tech-debt-resolved-0-9.md`](../implementation/tech-debt-resolved-0-9.md);
from item 64 (2026-11-26) on in
[`tech-debt-resolved-0-10.md`](../implementation/tech-debt-resolved-0-10.md).
