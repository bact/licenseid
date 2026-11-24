---
Created: 2026-08-19
Last-Modified: 2026-11-24
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
reading file below or a resolved item, kept in the three files under "Already
resolved" at the end. Each open item says where it came from. Item 51 (decided
and pinned, 2026-11-17), 53 (a known limit, 2026-11-18) and 56 (a hang in the
CLI matrix, found 2026-11-16) are resolved. Items 55 (PR #214, 2026-11-16), 54
(PR #217, 2026-11-16) and 47 (PR #219, 2026-11-17) are built; their leftovers
stay open. Item 2 waits on an upstream release. The open items that need a rule
or a decision before a fix are grouped in
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

## 35. Small gaps in the API and in Tier 2 — Priority 9

Found in review of item 22 (2026-10-02). Closed: `exclude` read only by
Tier 1 (PR #211) and a deprecated row with no text answering a GPL README
(PR #212); see
[`tech-debt-resolved-0-9.md`](../implementation/tech-debt-resolved-0-9.md).
Open, `main` does the same:

- A licence text repeated three times answers a licence it barely
  resembles: `LICENSE` (Apache-2.0) three times over gives `BSD-4-Clause`
  at 0.9025, with similarity 0.0968 and coverage 20.08 (review of PR #68).
  Measured again 2026-11-17: still so; the score is the marker floor
  (`0.95 * 0.95`), so a BSD clause marker misfires.
- Impact 1, Risk 2, Effort 3.

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
statistics; no fix has been designed yet, only the problem is documented.
The other way round, Apache-2.0 without its appendix answered Pixar: the core
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
runs in no workflow. The plan, in build order (an Opus proposal of
2026-11-19):

- **`docs.yml`**: a workflow on Markdown paths that runs the doc tests below
  and markdownlint, so the PR that breaks a doc fails.
- **`tests/test_docs_vocabulary.py`** (~150 lines): every click option form
  and choice is in its section of `docs/cli.md`; every result key and step
  `detail` is in `docs/resolve.md`; every `docs/*.md` is linked from the
  README; the category table check also covers `resolve-flow.md`.
- **`tests/test_docs_status.py`** (~120 lines): refuse `file.py:NNN` line
  numbers and "Before 0.x"; list time-bound words ("for now", "waiting",
  "yet", an upstream PR link) with the version last checked, so a version bump
  fails until each is reread; `__version__`, codemeta, the CHANGELOG heading
  and the README citation agree (`CITATION.cff` is written by a workflow).
- **Self-checks in `tests/test_lists_page.py`**: count projects by value, not
  by step; check a section's stated category and `EXACT` on every row; give
  each named rule an example that is not exact.
- **`tests/test_docs_examples.py`** (~200 lines, last): run the fenced
  examples on the `bundle_db` fixture (the 3.29.0 List, offline); a block it
  cannot run carries a skip marker with a reason.
- **Review habits, not tests**: a row's reason names its source and is
  checked against it; a sentence that promises behaviour (`always`, `any`, an
  error type, a warning) names an example a test runs; each rule has one home
  in `docs/` and other pages link to it; before a tag, rerun every prose
  example and check each claim that depends on the install kind (wheel or
  editable) against a built wheel. Add them to AGENTS.md and
  `release-process.md` when the tests exist.
- Check each new test against `tests/platform_files.py` (no file system or
  stream use: not needed) and keep it free of timing and network.
- Impact 2, Risk 3, Effort 3.

## 59. Several licence texts in one input (B2) — Priority 8

Refused for 0.9.2 (2026-11-23): one licence per input stays. An input that
holds two licence texts (the LGPL-2.1 text under a NumPy notice, say) gets one
ranking and no note that the file holds another text. Splitting the file needs
the boundary of each text, which is a guess (a title line, a copyright line, a
blank line), and a wrong guess gives a wrong licence: precision over recall.

Idea for later: report a flag when `COVERAGE` is well above 1, since the input
then holds more than the answer's text. Not settled by the sample to hand: the
4,598-word file of the LGPL-2.1 text under a NumPy notice had `COVERAGE` 1.05
on build 4, so the threshold needs measuring on real multi-licence files, on
main and on the branch.

Impact 2, Risk 2, Effort 4.

## 60. Twenty copies of the Apache-2.0 text answer BSD-4-Clause — Priority 15

Found 2026-11-23 on main and on the branch alike, so the core-text work did not
cause it. An input of 20 copies of the Apache-2.0 text, one after another,
gets BSD-4-Clause. On the 0.9.1 database (build 4) the branch gives SCORE
0.9025, SIMILARITY 0.0153 and COVERAGE 134. The score is a marker's floor
(0.95 times a marker confidence of 0.95), not the text: the sorted-word
similarity of 20 copies is bounded near 0.1 by the length ratio. So the marker
reader is what to trace before a fix. The flag of item 59 would catch it: its
`COVERAGE` is far above 1.

Impact 3, Risk 2, Effort 3.

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

## Already resolved

Kept out of this file to stay under the size limit: resolved before 0.5.0 in
[`../implementation/tech-debt-resolved.md`](../implementation/tech-debt-resolved.md);
from 0.5.0 on in
[`../implementation/tech-debt-resolved-0-5.md`](../implementation/tech-debt-resolved-0-5.md);
from 2026-11-17 in
[`tech-debt-resolved-0-9.md`](../implementation/tech-debt-resolved-0-9.md).
