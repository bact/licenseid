---
Created: 2026-08-19
Last-Modified: 2026-10-02
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Tech debt roadmap

See also: [`complexity-and-file-size-roadmap.md`](complexity-and-file-size-roadmap.md)
for code-health/complexity debt specifically. This doc tracks the rest.

Priority = (Impact + Risk) × (6 − Effort), each scored 1-5; same scale as
the complexity roadmap, so the two lists can be read together.

Item 9 (and the resolved items 3 and 8) come from a tech-debt audit on
2026-09-19; items 5 and 12 (and the resolved items 1, 4 and 6) from code
reviews of the diagnostics change and the Java removal; items 2 and 10 from
manual CLI testing under other locales and environments; items 15 to 18 from the
work on item 6, and item 19 from the work on items 15 and 17. Item 11 was
re-scored from the work on item 16, and items 21 to 25 come from the work on
item 18, items 26 and 27 from the work on item 24, items 28 and 29 from
the review of PR #66, items 30 and 31 from the work on item 21, and items
32 to 35 from the review of item 22, item 36 from the docs audit
after it, and item 37 from the work on item 29.

Next up: item 31, the revision of the license matching rules (decided
2026-10-01) and of the ranking (added 2026-10-02). Items 24, 25, 21 and 22,
in the order chosen on 2026-10-01, are done, and so are items 12, 27,
29, 36 and 37 (2026-10-02). Item 32 (Priority 24) is the
highest open priority but lies outside item 31; it has not been scheduled.
Item 2 waits on an upstream release. The open items that need a rule or a
decision before a fix are grouped in
[`matching-rules-redesign.md`](matching-rules-redesign.md) (2026-10-02).

## 2. `py-spdx-license` reads its data with the locale encoding — Priority 20

`py_spdx_license/ast.py` (v0.0.1) loads `data/licenses.json` and
`data/exceptions.json` at import time with `Path.open("r")` and no
`encoding`, so Python decodes the files with the locale's preferred
encoding. Both files are UTF-8 (JSON must be, RFC 8259), and
`licenses.json` holds non-ASCII text (`é` in `Licence Libre du Québec`,
the en dash `–` in `Data licence Germany – attribution – version 2.0`).

- **Symptom on a legacy locale**: `licenseid` cannot even start.
  `import licenseid.matcher` imports `py_spdx_license`, and under
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

A single word that is part of a licence's name answers it at 1.0 the same
way, through the token-set name match (`main` too; review of item 22,
2026-10-02): `BSD` answers `0BSD`, `the` answers `MirOS`, and a README
whose short text holds a "json" code fence answers the `JSON` licence.
Since item 22 these are `exact` false, but they still score 1 and pass
`is-*`.

- **Direction**: a verbatim hit on a few words is evidence, not an answer.
  Cap the score of a Tier 0 text hit below 1.0 when the phrase is shorter
  than some minimum, or require it to cover a share of the licence's
  distinctive words, so `is-*` answers no for it.
- Impact 2, Risk 2, Effort 2.

## 30. `GPL 2.0+` in prose loses its "+" in Tier 0 — Priority 6

Item 21 reads a lone SPDX expression as an ID, but a value that is not
SPDX-shaped still goes to Tier 0, which matches the normalised text, where
the "+" is gone: `GPL 2.0+` and `GPL-2.0 +` answer `GPL-2.0-only` at 1.02,
and `LGPL 2.1+` `LGPL-2.1-only`. Left out of item 21 on purpose
(2026-10-01): reading a "+" out of prose is a guess (`C++`).

- **Direction**: when a Tier 0 exact hit's raw text ends in a lone "+",
  answer its or-later form, or lower the hit below certain.
- Impact 1, Risk 2, Effort 2.

## 31. Revise the matching rules: grammar, certainty, ranking — Priority 12

Come back to this and think it through systematically, for one consistent
answer: so far each fix has patched the one case that was found. Whether a
value is an SPDX expression is decided in several places, each with its own
partial grammar:

- `identifiers.leading_expression` (where an expression ends in a value);
- `identifiers.is_simple_expression` and `_SIMPLE_SHAPES` (one license);
- `identifiers._RE_PLUS_OPERATOR` and `strip_plus_operator` (which "+" is
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
which tier may answer what, and with how much certainty (items 28 and 30
are the same question for short text).

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

## 32. A missing file named as an argument is matched as text — Priority 24

A bare argument is a guess between a file, an ID and text: one that names
no file is matched as text, and its name is short enough to answer by name
or phrase. `licenseid match LICENSE.txt`, with no such file, answers
`APL-1.0` at 1 and exits 0; `licenseid is-osi LICENSE.txt` prints `true`.
A typo in a path in a script gives a confident wrong answer. `main` does
the same; found in review of item 22 (2026-10-02).

- **Direction**: an argument shaped like a path (a separator, or a file
  name with an extension that is no licence ID) that names no file exits 2
  with `input: not found: <path>`; `--text` stays the way to match such a
  value as text.
- Impact 3, Risk 3, Effort 2.

## 33. A tag value with a non-ASCII letter is cut short — Priority 12

The tag reader stops a value at the first non-ASCII character, so
`LicenseRef-café` is read as `LicenseRef-caf`, `MIT-ü` as `MIT`, and
`MIT AND LicenseRef-ß` as `MIT AND LicenseRef`: a different licence, or a
reference that is no reference, answered with certainty. SPDX IDs are
ASCII, so such a value is invalid, but it should be refused whole, not
answered in part. `main` does the same; found in review of item 22
(2026-10-02).

- **Direction**: read the tag value up to white space or the next tag,
  as the expression reader does, and let the grammar refuse it (item 31).
- Impact 2, Risk 2, Effort 3.

## 34. Expressions and references carry the wrong flags — Priority 12

`is_spdx` is true for any `LicenseRef-*`, which is by definition not on
the SPDX License List, and a compound expression (`MIT OR Apache-2.0`)
reports `is_osi_approved` and `is_fsf_libre` false, though both its
licences are approved. The text output also puts an expression's spaces
inside `LICENSE_ID=`, so `awk` splits one value into several fields. `main`
does the same; found in review of item 22 (2026-10-02).

- **Direction**: decide what each flag means for an expression (all of its
  licences, any of them, or null) and for a reference (false), and how the
  text output writes a value with spaces (quoted, or spaces replaced).
- Impact 2, Risk 2, Effort 3.

## 35. Small gaps in the API and in Tier 2 — Priority 9

Found in review of item 22 (2026-10-02); `main` does the same:

- `exclude` is read only by Tier 1 retrieval, so a verbatim licence text
  still answers an excluded licence (item 5 covers the other options).
- `match(file_path=<missing>)` raises a bare `FileNotFoundError`, not a
  `LicenseIdError` worded `input: not found: <path>`.
- A licence text repeated three times answers a licence it barely
  resembles: `LICENSE` (Apache-2.0) three times over gives `BSD-4-Clause`
  at 0.9025, with similarity 0.0968 and coverage 20.08 (review of PR #68).
- A deprecated row the License List gives no text is still a Tier 2
  candidate, matched with similarity and coverage 0 but ranked by its
  markers: the README of a GPL-2.0-only project answers the deprecated
  `GPL-2.0` at 0.855.
- Impact 1, Risk 2, Effort 3.

## 5. Conflicting options and inputs are resolved silently — Priority 15

When several inputs are given, the CLI uses `--id`, then `--text`, then the
positional argument, then stdin; the API uses `license_id`, then `file_path`,
then `text`. `--bold` wins over `--json`, and `--diff` has no effect with
`--json`, `--bold` or `--exact` (an exact result has no diff). The README
documents none of this, and the losing option or input is dropped without a
warning. All of it is pinned as "current behaviour" in
`tests/test_option_matrix.py` and `tests/test_cli_output.py`.

- The same holds for the API options: `exclude`, `only_spdx`, `only_common`,
  `hint` and `enable_popularity` are read only by ranking, so an explicit
  `license_id`, a bare ID or name, and an `SPDX-License-Identifier` tag
  ignore them. Unknown option names are already rejected.
- An explicit `license_id` wins over `text` in `match()`, and the text is
  dropped unread.
- Values are not checked (review of item 22, 2026-10-02): `--top -1` drops
  the last result (a slice), and `--top 0` keeps none, so both say
  `no license found`. (`--threshold` outside 0-1 exits 2 since item 22.)
- **Fix**: decide per pair whether to reject it (usage error, exit 2) or
  document it, then flip the pins.
- Impact 2, Risk 3, Effort 3.

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
- Full plan: [`probe-anchored-windowing-plan.md`](probe-anchored-windowing-plan.md).

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

## 9. `scripts/` and `benchmarks/` are not linted in CI — Priority 12

`bench_single.py` (770 lines) and `generate_fixtures.py` (755) are near
the 800-line hard limit. Pylint rates the two directories 9.48/10;
`flake8` reports 11 findings. CI checks only `src/` and `tests/`.

- **Fix**: fix the findings, then add both directories to `lint.yml`.
  `tools/` (the CLI matrix) is in the same position: CI runs only `mypy`
  on it. `ruff` can join `lint.yml` at once (it is clean); `pylint` and
  `flake8` cannot until the judging code fits the complexity ceilings.
- Impact 1, Risk 2, Effort 2.

## 10. Environment failures in the database and the API — Priority 12

Found by running the CLI under odd environments (manual matrix, 2026-09-19).
Each case is outside the message grammar or hides a failure. The stream
and signal cases (closed streams, a closed pipe, an output write error,
Ctrl-C) were fixed on 2026-10-02; see `tech-debt-resolved.md`.

- **`update` when the default directory cannot be made** (unwritable
  `HOME`): the `mkdir` error is worded `database: update failed:
  PermissionError: ...`, with the wrong subject (the directory failed, not
  the database) and no action. (`--clear-cache` no longer makes the
  directory. A file licenseid did not build now exits 2 with
  `database: invalid`, and a delete the system refuses with
  `database: delete failed`.)
- **A valid but read-only database** (a read-only mount, a root-owned
  install): every database licenseid writes is in WAL mode, and SQLite must
  create `-shm` beside it even to read. The readiness check gives no verdict
  for this (`_no_verdict`), so the failure now comes from the real open, as
  `database: unreadable: attempt to write a readonly database` (and no
  `run 'licenseid update'` hint, which could not help). Main crashed here
  too, in `LicenseDatabase`. Fix options: copy the file, or open it with
  `immutable=1` when the directory is not writable (safe then, since no
  `update` can be running there).
- **`--db file://localhost/abs.db`**: SQLite accepts the `localhost`
  authority, so the readiness check passes, but `LicenseDatabase` turns the
  URI into a `Path`, which collapses the `//`, and the command exits 2 with
  `database: unreadable`. Pinned as an xfail in
  `tests/test_db_ready_adversarial.py`.
- **Lock contention** (`database is locked`, for example the first `update`
  that switches a database to WAL, during a `match`): the readiness check
  cannot tell a busy database from a hot rollback journal it may not replay,
  so it returns the condition `unknown`. A reader goes on and whatever opens
  the file next reports the failure, still worded `database: unreadable`;
  `update` and `--clear-cache` refuse, because a file they could not inspect
  may be anybody's and deleting one needs no lock at all. The probe waits
  `_BUSY_WAIT` (1 s), not SQLite's default 5 s, since the command that
  follows waits again.
- **DB replaced during a run**: on the CLI a `sqlite3` failure after the
  readiness check now exits 2 with `database: unreadable`. The Python API
  still raises a raw `sqlite3.OperationalError` from a live matcher whose
  file was deleted (pinned in `tests/test_db_ready.py`); wrapping it in
  `LicenseIdError` needs a decision on where (matcher, `LicenseDatabase`).
- **Ctrl-C during imports** (the first ~30 ms, before click runs): Python
  prints a `KeyboardInterrupt` traceback and dies by SIGINT, which the shell
  reports as 130. Found in review of PR #70; `main` is the same.
- **Fix**: word `update`'s directory failure with its own subject; open a
  read-only database with `immutable=1`; keep a `file:` URI a URI; decide
  where the Python API wraps `sqlite3` errors in `LicenseIdError`
  (matcher or `LicenseDatabase`).
- Impact 2, Risk 2, Effort 3.

## 23. The loose `License:` field reader resolves every match — Priority 12

`MarkerDetector._detect_explicit_identifiers` resolves each
`license:`/`license =` match in the text, each with database lookups. A file
of 10,000 such lines took 9 s on the real database. The manifest readers stop
at one value per form and table (`manifest.toml_license_values`), and since
item 18 this reader skips a manifest, but any other text still has no such
bound. Found on 2026-09-30 while checking item 18.

The INI reader has a cost of the same kind on Python 3.10: `configparser`
builds its error message one bad line at a time, so text with no file name
and 100,000 lines that are not `key = value` took 2 s (as on `main`; 0.3 s
on 3.14). Found on 2026-10-01 while checking item 18.

- **Fix**: resolve each distinct value once and stop at the first that
  resolves, or cap the number read. Time distinct values, not repeats. For
  INI, stop at the first bad line rather than collect them all.
- Impact 1, Risk 2, Effort 2.

## 19. How deep an expression may be depends on the Python version — Priority 9

`py_spdx_license` builds its AST with a plain recursive walk and no depth
guard, so `identifiers.parse_expression` reads a long chain differently per
interpreter: a 400-term `AND` of `LicenseRef-*` raises RecursionError on
Python 3.10 (read as "not an expression", no match) and parses on 3.14 (a
match). The cut-off is wherever the recursion limit falls, so the same file
can answer differently on two supported versions. Pinned as "either answer"
in `tests/test_matcher.py::test_match_pathological_expression_does_not_crash`.
A parse that fails this deep is also slow on 3.10: a deep-bracket test took
5.3 s on CI's 3.10 and passed on 3.14 (PR #61, where brackets around the
whole expression are now dropped before the parser sees them).

- **Fix**: cap the operator count before parsing, as
  `_MAX_CANONICALIZE_OPERATORS` already caps canonicalisation, so the
  cut-off is the same everywhere. Decide the cap from real expressions (the
  longest in the SPDX list is far below 40).
- Impact 1, Risk 2, Effort 2.

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

## Already resolved

Moved to
[`../implementation/tech-debt-resolved.md`](../implementation/tech-debt-resolved.md)
(2026-10-02), to keep this file under the size limit.
