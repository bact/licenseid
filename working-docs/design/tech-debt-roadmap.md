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
for code-health/complexity debt specifically. This doc tracks the rest.

Priority = (Impact + Risk) × (6 − Effort), each scored 1-5; same scale as
the complexity roadmap, so the two lists can be read together.

Item numbers are the roadmap's own and never reused: a gap is an item in the
reading file below or a resolved item, kept in the four files under "Already
resolved" at the end. Each open item says where it came from. Item 51 (decided
and pinned, 2026-11-17), 53 (a known limit, 2026-11-18), 56 (a hang in the
CLI matrix, found 2026-11-16), 35 and 67 (the marker floor, 2026-11-25) are
resolved. Items 55 (PR #214, 2026-11-16), 54 (PR #217, 2026-11-16), 47
(PR #219, 2026-11-17) and 57 (2026-11-26) are built; their leftovers stay open.
Item 2 waits on an upstream release. Next, after release 0.9.4 (PR #246,
PR #247): the new detection engine of release 0.10.0, then item 68, then
items 69 and 70 (decided 2026-11-27). Items 71 to 75 were found while
that engine was built; 72 waits on 71. The open items
that need a rule or a decision before a fix are grouped in
[`matching-rules-redesign.md`](matching-rules-redesign.md) (2026-10-02); item 31
is that revision.

The open items on reading a declared value or a name (`resolve()`, the
name tier, `--variant`, `EXACT`, the lists page: items 26, 46, 47, 49, 50,
52, 54, 55, 58) are in
[`tech-debt-roadmap-reading.md`](tech-debt-roadmap-reading.md), split
2026-11-24 at the size limit. This file keeps the rest: text matching,
data, environment and docs.

## 2. `py-spdx-license` reads its data with the locale encoding — Priority 20

`py_spdx_license/ast.py` (v0.0.1) loads `data/licenses.json` and
`data/exceptions.json` at import time with `Path.open("r")` and no
`encoding`, so Python decodes the files with the locale's preferred
encoding. Both files are UTF-8 (JSON must be, RFC 8259), and
`licenses.json` holds non-ASCII text (`é` in `Licence Libre du Québec`,
the en dash `–` in `Data licence Germany – attribution – version 2.0`).

- **Symptom on a legacy locale**: `licenseid` cannot even start.
  `import licenseid.detector` imports `py_spdx_license`, and under
  `LC_ALL=ja_JP.eucJP` (macOS, checked on Python 3.10) every command dies
  with `UnicodeDecodeError: 'euc_jp' codec can't decode byte 0xe2 in
  position 103585` before any output. Other multibyte locales (cp932 on
  Windows, Big5, GBK) should fail the same way; not tested.
- **Silent variant**: a single-byte legacy encoding such as cp1252 (the
  Windows default in many Western locales) decodes without error and gives
  mojibake, for example `Data licence Germany â€“ attribution â€“ version
  2.0`. Seven license names are affected. `licenseid` uses only IDs and
  expressions from this package, so the visible effect there is none today,
  but the package's own `get_license()` data is wrong.
- **Not affected**: UTF-8 locales, `LC_ALL=C` (Python 3.7+ coerces it to
  UTF-8) and `PYTHONUTF8=1`. Python 3.15 makes UTF-8 the default
  (PEP 686), which hides the bug there.
- **Root cause**: missing `encoding="utf-8"` in two `open()` calls
  (`ast.py` lines 21 and 33). Pylint `unspecified-encoding` (W1514) and
  Python's `-X warn_default_encoding` flag exactly this.
- **Upstream fix** (report and send a pull request to
  `github.com/JPEWdev/py-spdx-license`): use
  `p.open("r", encoding="utf-8")`, or `json.loads(p.read_bytes())`, which
  lets the `json` module detect UTF-8 itself. Add a test that runs the
  import under `-X warn_default_encoding -W error`.
- **Workaround until a release**: `PYTHONUTF8=1`, documented in
  `README.md` (2026-09-28); vendoring the two JSON files was not chosen.
  Importing `py_spdx_license` lazily would only move the crash to marker
  detection, so it is not a cure.
- **Status (2026-09-28)**: upstream pull request
  <https://github.com/JPEWdev/py-spdx-license/pull/5> adds the encoding and
  a test (`tests/test_encoding.py`, import under `-X warn_default_encoding
  -W error::EncodingWarning`). With it, licenseid runs under `ja_JP.eucJP`.
  After a release, raise the minimum `py-spdx-license` version, drop the
  README section and close this item.
- **Status (2026-10-30)**: the pull request was still open and only 0.0.1 was
  on PyPI. 0.7.0 ships with the README workaround (the maintainer chose docs
  only over an import shim that would patch `Path.open` during the import,
  or a parser of our own); `licenseid detect` and `--version` fail the same
  way, at import.
- **Status (2026-11-18)**: the pull request was merged upstream on
  2026-11-10, and only 0.0.1 is on PyPI, so the floor stays and the README
  workaround stays (`docs/installation.md`).
- The CLI matrix flags of this item are `E2-082` to `E2-090` (bash) in
  `tools/cli_matrix/baseline.txt`.
- Impact 2, Risk 3, Effort 2.

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
  [`probe-anchored-windowing-plan.md`](probe-anchored-windowing-plan.md).

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

## 10. Environment failures in the database and the API — Priority 12

Found by running the CLI under odd environments (manual matrix, 2026-09-19).
Each case is outside the message grammar or hides a failure. The stream
and signal cases (closed streams, a closed pipe, an output write error,
Ctrl-C) were fixed on 2026-10-02 (`tech-debt-resolved.md`); a replaced
database in 0.4.2 (`database-readiness-gate.md`); a data directory `update`
cannot make, a `file://localhost/` path and symlink loops in PR #209
(2026-11-15, `tech-debt-resolved-0-5.md`). Open: the three cases below.

- **A valid but read-only database** (a read-only mount, a root-owned
  install): every database licenseid writes is in WAL mode, and SQLite must
  create `-shm` beside it even to read. The readiness check gives no verdict
  for this (`_no_verdict`), so the failure now comes from the real open, as
  `database: unreadable: attempt to write a readonly database` (and no
  `run 'licenseid update'` hint, which could not help). Main crashed here
  too, in `LicenseDatabase`. Fix options: copy the file, or open it with
  `immutable=1` when the directory is not writable (safe then, since no
  `update` can be running there).
- **Lock contention** (`database is locked`, for example the first `update`
  that switches a database to WAL, during a `detect`): the readiness check
  cannot tell a busy database from a hot rollback journal it may not replay,
  so it returns the condition `unknown`. A reader goes on and whatever opens
  the file next reports the failure, still worded `database: unreadable`;
  `update` and `--clear-cache` refuse, because a file they could not inspect
  may be anybody's and deleting one needs no lock at all. The probe waits
  `_BUSY_WAIT` (1 s), not SQLite's default 5 s, since the command that
  follows waits again.
- **Ctrl-C during imports** (the first ~30 ms, before click runs): Python
  prints a `KeyboardInterrupt` traceback and dies by SIGINT, which the shell
  reports as 130. Found in review of PR #70; `main` is the same.
- **Open**: `immutable=1` for a read-only valid database. Safe only when
  all hold: a read (never `update`/`clear-cache`); the `mode=ro` open failed
  on an existing regular file; the directory and the file are both not
  writable by this user; no non-empty `-wal` or `-journal` beside it. Another
  user (root, a package manager) updating it still gives torn reads, which
  is why `database-readiness-gate.md` dropped it. Recommendation: keep it
  dropped; only a legacy WAL database on read-only media is affected (since
  0.4.2 `update` leaves WAL).
- Impact 2, Risk 2, Effort 3.

## 13. Apache-2.0 vs Pixar near-duplicate confusion — Priority 6

Licenses that are near-identical modifications of another license (e.g.
`Pixar` is `Apache-2.0` with a modified section 6) can be misidentified
as the parent license. See
[`new-matcher.md`](new-matcher.md) for the background analysis and word-count
statistics; for this direction no fix has been designed yet. The other way
round, Apache-2.0 without its appendix answered Pixar: the core
text fixed that (PR #239), and a verbatim Pixar text still answers Pixar.

- Impact 2, Risk 2, Effort 4 (needs a design pass before an effort
  estimate is meaningful — treat this as provisional).

## 57. Keep the user docs true to the code — Priority 15

Found by five verifiers that ran every example and table row of the user
docs before 0.9.0 (2026-11-19). No example was wrong, but the text drifted: a
sample warning no code prints (`download failed: timed out`), `--no-cache`
for `--cache/--no-cache`, "fix waiting upstream" after the merge, two pages
missing from the README, a `—` count column in `docs/lists.md` for rows read
as `listed_name`, a reason in a generated table false for 7 of 13 rows,
promises the code did not keep (`InvalidInputError` for a `Path`, `MIT++`
warns), line numbers of an old commit. Why it slips: a PR that changes only
docs runs no test (`test.yml` skips `docs/**`, `README.md`, `CHANGELOG.md`
but `resolve.md` and `lists.md`; `lint.yml` skips `**.md`), and markdownlint
runs in no workflow.

Built 2026-11-26 (one PR, from a plan of 2026-11-26 that measured each check
on the docs first):

- `.github/workflows/docs.yml` runs on any Markdown change: markdownlint-cli2
  over `**/*.md` (`.markdownlint-cli2.jsonc` leaves out `tests/fixtures/`) and
  the doc tests below with `test_lists_page.py` and `test_resolver_shapes.py`.
- `tests/test_docs_vocabulary.py`: each click option and choice in its
  section of `docs/cli.md`; each step kind, step detail (one example per
  detail, run) and reason condition that `resolve()` gives on the 627 values
  of the resolver fixtures and the worked examples in `docs/resolve.md`, and
  each documented reason given by `resolve()` (`tests/docs_reasons.py` holds
  a value for each the corpus lacks); the keys of the result types and of the
  `detect` record; the category table of `resolve-flow.md`; README links each
  page; relative links and anchors resolve.
- `tests/test_docs_numbers.py`: a table of numbers the prose states
  (`NUMBERS`) against their constants.
- `tests/test_docs_status.py`: line numbers and releases only on the two
  pages pinned to 0.9.0; `TIME_BOUND` (a sentence and the version it was last
  read for); one version in `__init__`, codemeta, CHANGELOG and README; the
  licenseid version the docs show.
- `tests/test_lists_page.py`: each row of `ALIASES` and `TITLES` reads with
  the category and `EXACT` its section states; a key a sample value equals is
  counted. Counting by step stays: it is what a row reads (`New BSD License`
  reaches `new bsd` through P1). The named-rule check was dropped: T1 and T2
  read only tables, and the page computes `EXACT`.
- `tests/test_docs_examples.py` with `tests/docs_blocks.py`: each fenced
  block that shows a result runs (22 blocks: console, `# result` lines,
  Python, `resolve()` JSON, an output block under a `run:` marker), and the 33
  worked examples of `resolve-flow.md`; a block it cannot run carries a
  `skip:` marker; `COUNTS` pins the blocks of each page. In
  `tests/platform_files.py`: it drives the CLI and the default database path.
- Drift fixed: `cli.md` predicates named no input, "no licences yet";
  `resolve-flow.md` missed `assumed_only` on the GNU URL row; the step-detail
  table of `resolve.md` had no example for four details.
- The review habits are in `release-process.md` ("Checks before the tag").

Leftovers: numbers written inline and not in `NUMBERS` (Tier 1's 200 words,
Tier 0's 30) are not checked; the MPL-2.0 `SAME_TEXT` example of `output.md`
is skipped until a long-text fixture holds the MPL-2.0 text; the `bash`
instructions (install, update from the network) are checked by hand before a
tag.

- Impact 2, Risk 3, Effort 3.

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

## 62. 100,000 `License:` lines on the test database take 25 min — Priority 12

Found by `--run-benchmark` before 0.9.2 (2026-11-24); it fails on v0.9.0 and
v0.9.1 too. `test_100k_distinct_lines_detect_in_bounded_time` (bound 30 s)
takes about 14 ms a line on its seeded in-memory database: 2,000 lines run
about 60 SQL queries a line (119,000 in all), on v0.9.0 (22 s), v0.9.1 (28 s)
and 0.9.2 (35 s; the notice-free head normalises the text again, 1.3x). On a
database `update` built, 8,000 such lines take 1.4 s on 0.9.1 and 0.9.2
alike. Trace the queries per line first (the shared-cache memory database,
`dbcache` checks), then decide whether the test or the code is wrong.

Impact 2, Risk 2, Effort 3.

## 65. Concurrent first calls each load the text corpus — Priority 8

The text corpus is built or read once per database generation in
`dbcache.TableCache`, with no lock: threads that make their first `detect()`
call together each load it (0.016 s from `text_codes`, about 0.05 s since
build 7 stores the regions of item 64; 0.16 s coded). Wasted
work only; the result is the same and the corpus is immutable. Fix with a
lock around the first load if a measurement shows a cost.

Impact 1, Risk 1, Effort 2.

## 66. A misshaped optional table breaks `-v` and `update` — Priority 8

A `text_codes` (or `license_urls`) table that licenseid did not make, with
other columns or as a view, fails the read of `detect -v` and `--json` as
`database: unreadable: no such column` (terse `detect` and `is-*` still
answer), and `update` cannot repair it (`table text_codes has no column
named kind`). Found in review of PR #241; `license_urls` is the same on
0.9.2. Only a hand-edited file gets here. Fix: in `update`, drop an optional
table, or view, whose columns differ, before it is written again.

Since item 67 (2026-11-25) terse `detect`, `is-*` and `is_*()` also read
`text_codes` where a marker's floor binds above coverage 1.05 (the
`markerfloor` check), and since item 59 (2026-11-26) wherever the top result
is a text match of 40 tokens or more (`firsttext`), so a misshaped table fails
them on such an input as it fails `-v`.

Impact 1, Risk 1, Effort 2.

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

## 75. Database leftovers of the 0.10.0 review — Priority 10

Found 2026-11-28 in the review of the 0.10.0 database. None changes an answer
of a normal call; "old" means 0.9.4 does the same.

- During `update`, for 0.5 to 1 s between the commit of the rows and the
  commit of the fingerprints and list version, a fresh open is refused as
  `empty; run 'licenseid update'`. An interrupted update leaves the file so
  until the next update (old layout of transactions). A kept detector is not
  affected.
- `database: update failed: database is locked` lacks the `<Type>:` the
  grammar asks for (two updates at once, a read-only file). Old wording.
- A non-numeric `idf_norm` in `license_fingerprints` gives a traceback on
  `detect`. Old.
- A flag stored as the text `'false'` reads as true (`bool('false')`):
  `is-osi` answers true. Old.
- "One transaction a call" covers Tier 1 and the loading of entries only: the
  fingerprint hits and the `lists` metadata are read after the snapshot ends,
  so a rebuild to another release in that gap could mix them into one call
  (not observed to change an answer).
- A kept detector whose file is replaced in place by a 0.9.x file still
  answers names from it; texts fail with `unreadable: no such table:
  license_texts`.
- An outdated file in an install without the packaged bundle (editable,
  `LICENSEID_BUNDLE=skip`) makes `resolve` exit 2; 0.9.4 warned and answered.
  With the wheel it falls back to the packaged list.
- A text edited by hand without a new `last_update_datetime` is caught only
  when read; the answer can show `COVERAGE` above 1 (stale core text, word
  count and fingerprints beside the new text).
- The postings blobs carry no content check: swapped blobs keep the answer
  but `TEXTS` becomes none and the runner-ups change (the limit stated in
  the gram postings note).
- A refused `update` on a newer build's file still runs `leave_wal` first: a
  newer file in WAL mode is switched out of it.
- `errors.one_line` folds white space but leaves other control characters as
  they are: an ESC in a stamp or a value reaches the terminal
  (`errors.shown` escapes them).
- `tools/cli_matrix/baseline.txt` was recorded without a packaged bundle:
  against a wheel, cells D4-001, D4-002 and D8-003 flag (`update` falls back
  to `packaged` and exits 0); 0.9.4 flags the same.

Done when: each is fixed or decided not to be, with a test.

Impact 2, Risk 3, Effort 4.

## Already resolved

Kept out of this file to stay under the size limit: resolved before 0.5.0 in
[`../implementation/tech-debt-resolved.md`](../implementation/tech-debt-resolved.md);
from 0.5.0 on in
[`../implementation/tech-debt-resolved-0-5.md`](../implementation/tech-debt-resolved-0-5.md);
from 2026-11-17 in
[`tech-debt-resolved-0-9.md`](../implementation/tech-debt-resolved-0-9.md);
from item 64 (2026-11-26) on in
[`tech-debt-resolved-0-10.md`](../implementation/tech-debt-resolved-0-10.md).
