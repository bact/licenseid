---
Created: 2026-08-19
Last-Modified: 2026-11-17
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

Items 3, 8 and 9 (all resolved) come from a tech-debt audit on
2026-09-19; items 5 and 12 (and the resolved items 1, 4 and 6) from code
reviews of the diagnostics change and the Java removal; items 2 and 10 from
manual CLI testing under other locales and environments; items 15 to 18 from the
work on item 6, and item 19 from the work on items 15 and 17. Item 11 was
re-scored from the work on item 16, and items 21 to 25 come from the work on
item 18, items 26 and 27 from the work on item 24, items 28 and 29 from
the review of PR #66, items 30 and 31 from the work on item 21, and items
32 to 35 from the review of item 22, item 36 from the docs audit
after it, item 37 from the work on item 29, item 38 from the
review of PR #80, items 39 to 42 from the review of PR #82, and items 43
to 45 from the reviews of PR #99 (items 43 to 45 resolved 2026-11-09,
2026-11-09 and 2026-11-08), item 46 from the 0.7.0 whole-release review,
item 47 from PR #168, item 50 from the work on item 44, item 51
from the work on item 43, and item 52 from the work on the upgrade of
deprecated IDs in `py-spdx-license` (2026-11-14), item 53 from the work
on item 40 (PR #207), item 54 from the review of `EXACT`, item 55 from
the decision on `EXACT` and our own lists (2026-11-15). Item 56 (a hang in
the CLI matrix, found 2026-11-16) is resolved.

Open: the list below, in the order of its headings. Item 55 is built
(PR #214, 2026-11-16); its leftovers stay open. Item 2 waits on an upstream
release. The open items that need a rule or a decision before a fix are
grouped in [`matching-rules-redesign.md`](matching-rules-redesign.md)
(2026-10-02); item 31 is that revision. Resolved items are in the two files
under "Already resolved" at the end.

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
- **Status (2026-10-30)**: the pull request is still open and only 0.0.1 is
  on PyPI. 0.7.0 ships with the README workaround (the maintainer chose docs
  only over an import shim that would patch `Path.open` during the import,
  or a parser of our own); `licenseid detect` and `--version` fail the same
  way, at import.
- The CLI matrix flags of this item are `E2-082` to `E2-090` (bash) in
  `tools/cli_matrix/baseline.txt`.
- Impact 2, Risk 3, Effort 2.

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
- `markers._expression_flags` and `_synthetic_candidate` (a recognised ID);
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

Found in review of item 22 (2026-10-02); `main` does the same:

- `exclude` is read only by Tier 1 retrieval, so a verbatim licence text
  still answers an excluded licence (the other options are documented as
  read by ranking only).
- A licence text repeated three times answers a licence it barely
  resembles: `LICENSE` (Apache-2.0) three times over gives `BSD-4-Clause`
  at 0.9025, with similarity 0.0968 and coverage 20.08 (review of PR #68).
- A deprecated row the License List gives no text is still a Tier 2
  candidate, matched with similarity and coverage 0 but ranked by its
  markers: the README of a GPL-2.0-only project answers the deprecated
  `GPL-2.0` at 0.855.
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

## 20. A grant inside an expression loses the value — Priority 9

An "or later" grant ends the expression that `identifiers.leading_expression`
reads, because the phrase sits where an operator would (`classify`
`OR_LATER_PHRASE` is the one reader of it). A tag whose value goes on after
the grant, such as `MIT AND GPL-2.0 or later AND Apache-2.0`, is therefore
refused outright: answering `MIT AND GPL-2.0-or-later` would drop an operand
and understate the obligations, so no answer is the safe reading, but the
value does name three licenses a reader could resolve.

- **Fix**: let the walk carry the grant instead of stopping at it — rewrite
  the ID it qualifies to its `-or-later` form and go on scanning — so
  `leading_expression` returns the expression the value means rather than a
  prefix of it. That makes `qualify_trailing_grant` part of the walk;
  `is_simple_expression` then needs the end offset of what was read, not a
  string comparison, to tell a whole value from a cut one.
- Impact 2, Risk 2, Effort 3.

## 13. Apache-2.0 vs Pixar near-duplicate confusion — Priority 6

Licenses that are near-identical modifications of another license (e.g.
`Pixar` is `Apache-2.0` with a modified section 6) can be misidentified
as the parent license. See
[`new-matcher.md`](new-matcher.md) for the background analysis and word-count
statistics; no fix has been designed yet, only the problem is documented.

- Impact 2, Risk 2, Effort 4 (needs a design pass before an effort
  estimate is meaningful — treat this as provisional).

## 46. Leftovers of the 0.7.0 whole-release review — Priority 12

Found in the review of 2026-11-02 to 11-03. The resolver, readers, BSD and
short-text leftovers are in `match-resolve-0-8.md`, section 7. Done: the
typed options, the lock-wait test, one long-text database and the `ruff
format` check (PR #210), and the free-text rules of `exclude` and `hint`
(PR #211); see `tech-debt-resolved-0-5.md`. Open:

- **Readers see `database: empty` during `update`** (1,074 errors over a
  13 s update with four reader threads; 0.6.0 does the same): the plan is a
  single transaction, a busy timeout and an OS lock; the atomic swap needs
  Windows care (`os.replace` fails on an open file). Design:
  [`concurrent-update.md`](concurrent-update.md).
- **`hint` against the filters**, pinned `# BUG:` in
  `tests/test_detect_options_paths.py`. Decided 2026-11-15, not built:
  `exclude` wins over `hint`; today a hint is added after the filters, so it
  undoes `exclude` and passes `only_common` and `only_spdx`. Undecided, with
  a recommendation: a hint counts towards the fewer-than-5 test that gates
  the mixed-content search (`detector.py`) and can lose a licence that
  search found: count only candidates with text; a hint buries a marker
  candidate of the same licence (JSON 1.0 to 0.025 with `hint=["JSON"]`;
  not rechecked after PR #211): merge markers before hints; a hint has no
  text, so it scores 0: give it its text or say it only lists.
- **`only_spdx` does nothing** on a database licenseid builds (every row
  `is_spdx=1`). Keep or redesign, not remove: more lists will come
  (AboutCode ScanCode, Blue Oak) and a source flag may be what it becomes.
  Decide with the multi-list design; until then it stays documented as a
  no-op on a built database.
- A tag that lists a licence elsewhere than right after the mark is still
  the first licence, exact: after a grant (`GPL-2.0 or later, ISC`), with
  "or"/"and" (`MIT, or ISC`), in brackets or quotes (`MIT, (ISC)`), after a
  full-width comma or a dash (`MIT - ISC`), or later in prose (`MIT, and
  also Apache-2.0`), or before an operator (`MIT - OR ISC`). #158 refuses a
  licence right after a mark (A-F6); it also refuses `MIT, Intel and
  others`, as the field reader does (the item ends at "and"). Belongs to
  the matching-rules redesign.
- `is-*` on a file with several tags judges the top one only; the condition
  words for empty input; a garbage `--db` is `unreadable` or `invalid`
  depending on the path.
- One API pass: `Resolver`, `Component` and `DetectOptions` are not in
  `licenseid.__all__` (A-F7: the names need a decision; `licenseid.Resolver`
  reads as a class and both are the same shape).
- The METADATA of a dev build keeps `0.7.0-dev.0` as written (C4).
- `test_db_ready.py` (`wal_copy_without_wal`) fails 6 cases under uv's
  Python 3.14 (SQLite 3.43.2) on macOS, on `main` too (`unreadable` against
  `empty`); CI's 3.14 passes. It depends on the SQLite version.
- `update --source packaged` sample outputs in the README are unverified
  against a built wheel: check them at the final release gate.
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

**Built** (2026-11-17; open until merged): `namehits.settle()` drops a name
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
- **Two licences in prose, not tied**: `GNU General Public License v2.0 or
  MIT License`, `MIT License or BSD 3-Clause` answer MIT (a grant-less GPL
  name or a short BSD form is not held whole, so no tie); needs a rule that
  weighs every name the input holds, not only the tied ones.
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
  (0.86): name hits under 1, so Tier 1 answers. `GNU Lesser General Public
  License v2.0 or later` gives GPL-2.0-or-later; `Apache License 1 or later`
  gives Apache-1.1 (a grant exempts the cut).
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

- **A file with no section** (`license = "MIT OR ISC"`, no `[metadata]`)
  is no manifest, so the whole text goes to the name tier, which answers
  `ISC`, inexact. `resolve()` refuses it (an `=`); a text that is a
  `key = value` line could be read as that value.
- **`markers.resolve_license_value` and `_first_resolved`** still hold a
  reader of their own for a tag and a field (`MIT OR MirOS` order, a title
  and an alias are not read by a tag); route them through `resolve()` once
  item 43 has landed in `markers.py`.
- **`identifiers.is_qualified_plus` / `is_stray_plus`** (the first guard of
  `_try_tier0_short_text`) repeat the "+" refusals of `resolve()`; they
  return no result where the `resolve()` guard returns None (a warning), so
  removing them adds a `too few words for text` warning. Decide, then drop.
- **`looseid.disambiguate_whole`** reads a bare deprecated ID and its prose
  in the raw text for a value `resolve()` refuses (comment-wrapped grants,
  `tests/test_readers_grants.py`); no corpus value needs it otherwise.
  Measure it on fields, then fold it into `resolve()`.
- **A wrapped name answers exact**: `*Apache License 2.0*` is `not found`
  for `resolve()` and still `Apache-2.0` by name; apply `dropguard.dropped`
  to name hits.
- **A sentence of 10 to 29 words with `MIT++`** is matched by name still
  (`MIT`, inexact; under 10 words it has no answer): only a word ending in
  "+" under 10 words is refused, so a README line with `C++` keeps its
  answer.
- **Hidden characters and escapes inside a quoted field**: a quoted INI
  `"MIT\u200b"` and a TOML `"\"MIT\""` (backslashes kept by the manifest
  reader) answered `MIT` by name before item 48 and have no answer now,
  because `resolve()` refuses them (`control or format character`, dropped
  backslash). Trim a hidden character inside quotes in `resolve()`, and
  unescape the TOML string in `manifest`.
- **The harness database is partial**: the long-text fixtures hold no
  deprecated rows, so `GPL-2.0` (`id_deprecated`) has no answer there
  (`tests/harness_changes_wrappers.py`); build the golden database from the
  full List.

- Impact 2, Risk 2, Effort 3.

## 51. A lone ID with a stray slash or bracket gives no answer — Priority 10

Before PRs #195 and #197 (item 48), `detect(text=...)` answered an ID with
one stray mark through Tier 0: `/MIT`, `MIT/`, `(MIT` and `MIT)` gave `MIT`,
and `GPL-2.0+)` gave `GPL-2.0-or-later`, all exact. Now `resolve()` refuses
each (`character dropped: U+002F`, `parse failed: Unexpected '('`, `Missing
matching '('`) and `detect()` follows it with no answer. The refusals are
deliberate (a dropped mark may be the author's doubt, `dropguard`), and the
"/" rule of item 43 keeps `/MIT` and `MIT/` refused (an empty piece). Decide
whether a lone mark of this kind is read, which marks, and with what category
and step; measure it on the PyPI sample and the manifests before choosing.

- Impact 2, Risk 2, Effort 2.

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
  `variants.ANSWER_SCORE` (0.85); the grant signal reads the whole input,
  not the licence's own words (a README's "Python 3.8 or later" counts;
  pinned `# BUG:` in `tests/test_variant.py`), and misses a grant only the
  heading marker read (pinned
  `test_a_grant_the_marker_did_not_read_leaves_the_only_form`); whether the
  `-with-` rule of `EXACT` applies to every `deprecated_ambiguous` operand
  (`eCos 2.0` stays exact, as on `main`).
- **Channels that still differ** (rule I1): a deprecated List name (AGPL)
  answers `-only` as the argument under `auto` but the bare ID in a tag or
  a field (pinned `# BUG:` in `tests/test_variant_invariants.py`); a tag
  answers `MIT OR GPL-2.0 only` that the argument and a field refuse
  (pinned `test_a_tag_reads_an_only_after_an_operand_of_a_list`); a tag
  refuses `GPL-2.0 or later OR MIT` that the argument answers.
- After a `py-spdx-license` release with `upgrade()`, raise the floor in
  `pyproject.toml` and let it replace the `+` and rename code
  (`DEPRECATED_SPDX_LICENSE_IDS`, the rename rule of `listrules`); the bare
  and `-with-` tables stay with this item. Revisit `EXACT` then: its
  mapping of deprecated IDs settles which renames are List data.
- Found, not caused by this item: the text of
  `deprecated_GPL-2.0-with-classpath-exception` gets no result; three
  identical-text GFDL ties stay exact and wrong (a tie problem).
- Impact 2, Risk 2, Effort 3.

## 53. A cut `-shm` file of a legacy WAL database kills the reader — Priority 12

Found in review of the item 40 fix. SQLite maps the `-shm` file of a WAL
database whatever `mmap_size` says. A database left in WAL mode by a version
before 0.4.2 (until `update` runs `Connections.leave_wal`), with its `-shm`
cut to 0 by another program (a `cp db*` over it), kills the reader with
SIGBUS, and the parent on `close()`. It needs one held connection, a
`reading()` block or a single `detect()` call: two separate `detect()` calls
open fresh connections and answer normally (reproduced in review: `-shm` cut
to 0, inside a block SIGBUS, outside a block fine).

- **Fix**: measure first (is the reader's `-shm` cut realistic?); then refuse
  a WAL file with a `-shm` in the readiness check, or open it with
  `PRAGMA locking_mode=exclusive`, or leave it as a known limit in
  `cross-platform.md`.
- Impact 1, Risk 2, Effort 2.

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
- **Built** (PR #217, 2026-11-16; open until merged): see [`tech-debt-resolved-0-5.md`](../implementation/tech-debt-resolved-0-5.md).
- **Open leftovers**: a dash glued to a comment closer in a tag (`MIT-*/`,
  `MIT-#}`, `MIT-}`) is still read as `MIT`; a tag compound ending in a
  reference that ends in a dash (`MIT OR LicenseRef-a-`) loses the dash
  downstream; a refused tag above a licence fragment can fall to the text
  tier (`MIT-0` at 0.914); `detect` of `GPL-2.0 or later-` still answers
  through `disambiguate_whole`, as for `GPL-2.0 or later?` (also
  `LGPL-2.1 or later-`, `GPL-2.0 or later--`); a joiner run before a word
  grant (`GPL-2.0-- or later`, `MIT__ or later`) is still read; `LGPLv2 or
  above` and `LGPL-2 WITH Classpath-exception-2.0+` give `version
  ambiguous`, not the reason of their own fault (no answer changes). Fixed
  by item 47: `License: MIT-`, `Licensed under the Apache-1 license`,
  `MVT-1`, `Sendmail-8`, `Apache License 1`.
- Impact 1, Risk 2, Effort 2.

## 55. Publish the lists `resolve()` reads — Priority 12

Its own pull request, after PR #212 (decided 2026-11-16): the page is not
part of the `EXACT` change. **Built** (PR #214, 2026-11-16).

Decided 2026-11-15 with the `EXACT` rule of item 52: an answer from an
authoritative list is exact, so a user must be able to read each list. They
lived in code only: `resolvealias.ALIASES` (12), `resolvetitle.TITLES` (4),
`trovenames.TROVE_NAMES` (89), and in `resolveurl` `URL_ALIASES` (11),
`SCANCODE_NOT_SPDX` (13), `ID_PAGES` (4 hosts) and `DUAL_PAGES` (2), with
`resolveslash.REFUSED_PAIRS` (2) and `resolveprose.VERSIONED_NAMES` (2).
About 140 rows in all; ScanCode and Blue Oak lists are planned.

- **Built**: `docs/lists.md`, generated by `python -m tools.lists_page`
  (`--check` tests it). `render.py` reads each table from its code object, so
  there is no second copy; `measure.py` computes what can be measured on the
  test corpus (the 3.29.0 List fixtures and the PyPI sample of 2026-10): the
  projects that declare each alias, title and classifier name, and the
  answer, category and `EXACT` of each rule example; `evidence.py` holds what
  only a person knows (the source of a row; the survey count of a URL page,
  whose raw data is not committed); `rules.py` the named rules, each linked
  to its function by import, so a rename fails. `tests/test_lists_page.py`
  fails when the page and the code differ, pins what the rules decide, and
  checks that every row has its evidence. `docs/resolve.md` lost its
  `REFUSED_PAIRS` table for a link; `docs/lists.md` is in the path filters
  of `test.yml` so a hand edit of it runs the test.
- **The named rules** (decided 2026-11-16): T1 to T3 (`resolvetrove`) and P1
  to P3 (`resolveprose`) stay named in code and tests; the page lists each
  with its function, `CATEGORY` and `EXACT`. T1 and T2 are exact
  (`trove_name`, or the List's own category); T3 is exact when both parts are
  List names and not when its head needed a rewrite rule (`Apache2
  (Apache-2.0)` is `version_spelling`); P1 to P3 rewrite a value
  (`prose_form`), so they are not exact (rule (c) of item 52). Found while
  building: a prose form that reduces to a name of a table takes the table's
  category, the weakest of the steps (`New BSD License` is `alias_name`,
  exact), as the page says.
- **Growth rule kept**: a row is added only with a measured package count
  (`working-docs/paper-notes/licence-urls.md`); the page shows that count,
  and the test requires one for each alias and title. The four URL pages of
  variants (`mozilla.org/mpl/2.0`, `opensource.org/license/mpl-2-0`,
  `opensource.org/license/ofl-1-1`, the SIL `ofl_web` page) have no recorded
  count and are named in `evidence.UNMEASURED_URLS`: measure them or drop them.
- **Left open**: a command (`licenseid resolve --lists`) or a JSON file with
  the same rows, so a script can read them. Not added: it would be a new CLI
  option (an axis of `tests/test_option_matrix.py`) and the page now exists
  to be read; decide when a script needs it. A trove classifier with no
  recorded count shows a dash: the count of the survey is the PyPI sample
  only.
- A new list (ScanCode, Blue Oak) gets its page section, its `CATEGORY` and
  its `EXACT` value when it is added (`render.py`). The Blue Oak idea:
  [`blue-oak-ratings.md`](blue-oak-ratings.md).
- Impact 2, Risk 1, Effort 2.

## Already resolved

Moved to
[`../implementation/tech-debt-resolved.md`](../implementation/tech-debt-resolved.md)
(2026-10-02), to keep this file under the size limit; those resolved from
0.5.0 on are in
[`../implementation/tech-debt-resolved-0-5.md`](../implementation/tech-debt-resolved-0-5.md)
and, from 2026-11-17,
[`tech-debt-resolved-0-9.md`](../implementation/tech-debt-resolved-0-9.md).
