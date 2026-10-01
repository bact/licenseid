---
Created: 2026-08-19
Last-Modified: 2026-10-01
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
item 18.

Next up (chosen 2026-10-01): items 21 and 22, ahead of their priority
order; item 2 waits on an upstream release. Items 24 and 25 were found after
that choice and outrank both by priority.

## 21. `--text GPL-2.0+` answers GPL-2.0-only — Priority 20

The same value gives two answers. As a bare argument, `licenseid match
GPL-2.0+` reads it as an ID and answers `GPL-2.0-or-later`. Through `--text`,
or the API's `match(text=...)`, Tier 0 matches the normalised text, which
has lost the `+`, and answers `GPL-2.0-only` at 1.02: a certain answer that
drops the "or later" grant. Found on 2026-09-30 while checking item 18;
`main` behaves the same.

- **Fix**: let Tier 0 see a trailing `+` (or send a lone simple expression
  through the ID path, as the CLI's bare argument does). Pin first.
- Impact 2, Risk 3, Effort 2.

## 22. `--json` prints internal ranking keys — Priority 12

A Tier 2 result is the ranking's own record, so `match --json` prints
`base_score`, `pop_score`, `is_deprecated`, `superseded_by` and
`best_window` (a slice of license text) beside the keys the README shows.
Found on 2026-09-30 while checking item 18.

The output is not stable either: `json.dumps(results, indent=2)` prints keys
in the order each tier happened to build them, Python's float form (`1.0`),
and `is_deprecated` as `0` rather than `false`.

`score` is a ranking key, not a confidence, and its scale depends on the
tier: a tag or a manifest field scores 1.0, a Tier 0 exact ID 1.02 and a
name 1.01, and a Tier 2 text match can reach about 1.05 through its
additive tie-breakers (`similarity.calculate_final_score`, and
`_FP_BOOST` × `idf_norm` in `matcher._rank_candidates`; the first 400
characters of the Apache-2.0 text score 1.0 + 0.05). One `match()` answers
from one tier, so the order is sound, but a fuzzy text match prints a
higher score than a certain tag.

**Decided (2026-10-01)**: publish both how the answer was found and a 0-1
`score`.

- A new key names the method: tag, field, ID, name or text.
- Public `score` is the ranking key capped to 0-1. It keeps the `is-*` bar
  (0.85, `matcher.resolve_record`) reproducible from the output, and it is
  the one value comparable across methods. Two results above 1 both print
  `1`, so the list order is the ranking. The score is closeness, not a
  probability: below 1 it still carries the tie-breakers.
- Ranking and the internal checks keep the raw key (`> 1.0` marks Tier 0 as
  definitive; `_try_manifest_value` needs `EXACT_MATCH_SCORE`), so the cap
  is applied in one place, at the end of `match()`.
- Every result has the same keys; `similarity` and `coverage` are `null`
  where nothing was measured (a name match prints `coverage: 0.0` today).
- The text output gains `SCORE=` and the method, so it agrees with JSON.

- **Fix**: build the public key set above in one place at the end of
  `match()` (keeping `best_window` internal for `--diff`), and pin it.
  Serialise it with the JSON Canonicalization Scheme (JCS, RFC 8785) through
  `rfc8785` (Trail of Bits, Apache-2.0, no runtime dependencies; 0.1.4
  checked on 2026-10-01): sorted keys, no white space, ECMAScript number
  form, so equal results give equal bytes and a line of output is one value.
- JCS normalises numbers, which is wanted: `1.0` prints as `1`, one value
  one spelling.
- **Decided (2026-10-01)**: JSON Lines, one JCS object per result per line.
  It fits the line-delimited CLI rule, and `wc -l`, `awk` and `xargs` work
  on it as on the text output.
- **Decided (2026-10-01)**: `best_window` stays internal, for `--diff` only.
  It is normalised text (lower case, no punctuation), not the license as
  written, and when no alignment ran it is the candidate's whole text,
  repeated for every result. It is also the one value that carries
  non-ASCII text (the Japanese licenses), so without it the output is
  ASCII and JCS writing UTF-8 as is, where `json.dumps` escaped it, meets
  no stdout encoding question.
- A new runtime dependency: add it to `pyproject.toml` and `codemeta.json`.
- Breaking for `--json` readers (an array becomes lines; keys and score
  change): mark it so in `CHANGELOG.md` with the migration, and update the
  README example.
- Impact 2, Risk 1, Effort 2.

## 24. A short input never reads its `SPDX-License-Identifier` tag — Priority 24

Under 30 words, `matcher._try_tier0_5_markers` reads only a manifest's
license field (item 18); the tag reader never runs, so the line goes to
Tier 0 as a license name. `SPDX-License-Identifier: MIT OR Apache-2.0`
answers `Apache-2.0` at 1.01, dropping MIT, and
`// SPDX-License-Identifier: GPL-2.0-or-later WITH Classpath-exception-2.0`
answers `CAL-1.0` at 0.667. `SPDX-License-Identifier: MIT` comes out right
only because Tier 0 finds the name. A one-line header (`head -1 file.c |
licenseid match`) is a common input. Found on 2026-10-01 while reviewing
item 18; `main` behaves the same.

- **Fix**: under 30 words, also run the tag reader, which is cheap and
  certain, as item 18 did for the manifest field. Pin first.
- Impact 3, Risk 3, Effort 2.

## 25. `GPL-2.0-with-classpath-exception` is not redirected — Priority 20

`identifiers.DEPRECATED_WITH_IDS` maps six of the seven deprecated `-with-`
IDs in the License List to `<license> WITH <exception>`; it lacks
`GPL-2.0-with-classpath-exception`, so that ID answers itself (deprecated)
where the others answer `GPL-2.0-only WITH ...`. Found on 2026-10-01 while
reviewing item 18; `main` behaves the same.

- **Fix**: add `GPL-2.0-only WITH Classpath-exception-2.0`, and add a test
  that every deprecated `-with-` ID in the License List has an entry, so
  the next one cannot be missed. Check the exception ID against the
  exceptions list.
- Impact 2, Risk 2, Effort 1.

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

## 5. Conflicting options and inputs are resolved silently — Priority 15

When several inputs are given, the CLI uses `--id`, then `--text`, then the
positional argument, then stdin; the API uses `license_id`, then `file_path`,
then `text`. `--bold` wins over `--json`, and `--diff` has no effect with
`--json` or `--bold`. The README documents none of this, and the losing
option or input is dropped without a warning. All of it is pinned as
"current behaviour" in `tests/test_option_matrix.py` and
`tests/test_cli_output.py`.

- The same holds for the API options: `exclude`, `only_spdx`, `only_common`,
  `hint` and `enable_popularity` are read only by ranking, so an explicit
  `license_id`, a bare ID or name, and an `SPDX-License-Identifier` tag
  ignore them. Unknown option names are already rejected.
- **Fix**: decide per pair whether to reject it (usage error, exit 2) or
  document it, then flip the pins.
- Impact 2, Risk 3, Effort 3.

## 11. Probe-anchored windowing — Priority 15

The one large remaining lever on `fragment_similarity`'s dominant cost:
reuse the existing 60-word probe's match location instead of re-running
a full realignment scan. Deliberately deferred because it changes
`best_window`, which is user-facing via the CLI's `--diff` flag, not
just an internal ranking score — needs its own validation cycle (a
`bench_compare.py` run plus a manual `--diff` output quality check).

- Re-scored 2026-09-30 (Impact 2 → 3): ordinary license text pays for it,
  not only crafted input. On the real database a 3,000-character slice of
  Apache-2.0 (a probed query) takes 9 s, because many similar licenses pass
  the probe and each gets a full scan of the whole query. The scan's cost
  follows the query's characters (item 16), and item 16's guard does not
  apply: this query is prose, and its fixture twins (`head_3000`) must keep
  their answers. Blob around a licence-like middle pays it too: 200 words of
  Apache-2.0 among 120 random 25-character tokens (4,426 characters) takes
  134 s, as 141 candidates pass the probe and each scan takes about 1 s.
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

## 10. Environment failures end in a traceback or lost output — Priority 12

Found by running the CLI under odd environments (manual matrix, 2026-09-19).
Each case is outside the message grammar or hides a failure:

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
- **Closed standard input** (`<&-`): `AttributeError: 'NoneType' object has
  no attribute 'isatty'` from `read_input`.
- **Closed standard output** (`>&-`): exit 0 and the result is lost. A
  script sees success with no data.
- **Output error** (`ulimit -f 0` with output to a file): `OSError`
  traceback and exit 120, instead of one `ERROR:` line. The matrix no longer
  shows it (cell `E4-028` left the baseline): under that limit SQLite cannot
  create the `-shm` file, so the readiness check now refuses first, with
  `database: unreadable: <path>: disk I/O error` and exit 2. The failing
  write of standard output is still unhandled; a cell that reaches it needs a
  database the check can read on a filesystem the output cannot be written
  to.
- **DB replaced during a run**: on the CLI a `sqlite3` failure after the
  readiness check now exits 2 with `database: unreadable`. The Python API
  still raises a raw `sqlite3.OperationalError` from a live matcher whose
  file was deleted (pinned in `tests/test_db_ready.py`); wrapping it in
  `LicenseIdError` needs a decision on where (matcher, `LicenseDatabase`).
- **Ctrl-C (SIGINT)**: prints `Aborted!` (click's own wording, outside the
  message grammar) and exits **1**, the code for "no". A script that tests
  `licenseid is-osi X` reads an interrupted run as "not OSI". Exit 130
  (128 + 2, the shell convention) or 2 would be safe; `update` interrupted
  during its first download also leaves an empty `licenses.db`
  (the readiness check now reports that database).
- **Fix**: handle `OSError` and `sqlite3.Error` once at the top of the CLI
  and print `ERROR: <subject>: <condition>: <detail>`; treat a `None`
  `sys.stdin` as no input; flush standard output at the end and exit 2 when
  it fails. The `sqlite3.Error` part is done for the CLI in
  `DatabaseErrorGroup`; the API is left.
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

## 12. Usage and click errors skip the stream and message rules — Priority 8

Running with no subcommand prints the help text to standard output (exit 2),
and click's own usage errors (`No such option`, missing argument) go to
standard error in click's format, not `LEVEL: SUBJECT: CONDITION`.
`tests/test_cli_output.py` asserts the exit code and that the usage text
appears, not which stream carries it.

- **Fix**: send the no-subcommand usage to standard error; decide whether
  click errors should be re-worded through `console.error()`.
- Impact 1, Risk 1, Effort 2.

## 13. Apache-2.0 vs Pixar near-duplicate confusion — Priority 6

Licenses that are near-identical modifications of another license (e.g.
`Pixar` is `Apache-2.0` with a modified section 6) can be misidentified
as the parent license. See
[`new-matcher.md`](new-matcher.md) for the background analysis and word-count
statistics; no fix has been designed yet, only the problem is documented.

- Impact 2, Risk 2, Effort 4 (needs a design pass before an effort
  estimate is meaningful — treat this as provisional).

## Already resolved (kept for record)

- A manifest's license field was lost or unflagged (item 18, Priority 16;
  2026-09-30). A TOML or INI field scored 0.95, not the 1.0 of JSON, so it
  went on to ranking and came out at 0.902 with no SPDX flags, and
  `is_spdx()` said false for `pyproject.toml` with `MIT OR Apache-2.0`. A
  Tier 0 or Tier 2 result carried no flags at all, so
  `GPL-2.0-with-GCC-exception` was not "SPDX" either. Checking it found two
  worse faults: the PEP 639 string form (`license = "MIT OR Apache-2.0"`,
  now the usual `pyproject.toml` form, and Poetry's and Cargo's) was not
  read, and no marker ran under 30 words, so a small `package.json`,
  `pyproject.toml` or `Cargo.toml` was matched by name and answered
  `Apache-1.0` at 1.01. Now:
  - the manifest readers live in `licenseid.manifest`; a JSON, TOML or INI
    field that resolves scores 1.0 and is read at any length
    (`MarkerDetector.detect_structured`);
  - the string form is read only in `[project]`, `[tool.poetry]`,
    `[package]` and `[workspace.package]` (a Cargo workspace root, which
    answered `Apache-1.0` at 1.01), so a Python `license = "MIT"` in
    `--text` is not a field, and never inside a multi-line string;
    PEP 621's table is also read written out, as `[project.license]` or
    `license.text` (a small one answered `Apache-1.0` at 1.01);
  - text with no file name is read as TOML, in either form, only if its
    first line that is not blank or a comment is a whole table header: a
    README piped in with a `[project]` example, or opening with a
    `[![badge](...)]`, answered the example's MIT at 1.0;
  - a run of white space inside a line is collapsed before `configparser`
    reads it: on Python 3.10 it scans the run once per character of the key
    before it, so 50,000 spaces after `license` took 9 s;
  - npm's old object (`{"type": ...}`) and array (`"licenses"`, joined with
    OR) forms are read; every array entry must name its license;
  - every result carries `is_spdx`, `is_osi_approved` and `is_fsf_libre`:
    Tier 2 copies them from its candidates, and Tier 0 from its cached name
    table (a lookup per result made a broad name such as `GPL`, 42 results,
    20 times slower); an expression takes them from
    `MarkerDetector.license_flags`, the rule synthetic expression candidates
    already used;
  - a manifest value must be an expression as a whole (`resolve_license_value`
    with `whole=True`): a tag's value can trail into prose, a field's cannot,
    and the MIT prefix of `MIT/Apache-2.0` dropped a license. Cargo's
    `[package]` reads the slash as OR, its old spelling. A License List
    page URL (`https://spdx.org/licenses/MIT.html`) names its license; its
    `.html` made a small manifest lose the answer `main` gave;
  - a manifest is never matched by name as a whole: a value that does not
    resolve goes to Tier 0 on its own, and only an exact ID or name counts
    (`"Apache 2.0"` is Apache-2.0; `"BSD"` would be a fuzzy 0BSD). A small
    manifest with no value, or whose value names no license, has no answer:
    `license-file` alone answered the crate name `zlib-rs` as `Zlib` at
    1.01. A reader returns None for text that is not its format, or has no
    key in it, so `[MIT]` and `["MIT"]` are no manifest and Tier 0 answers;
  - the loose `License:` reader skips a manifest, whose field the manifest
    reader has read whole;
  - the text is parsed as a manifest once per match
    (`_MatchContext.manifest`), not by each tier.

  The loose `License:` reader stays at 0.95 elsewhere: it matches prose. OSI
  and FSF flags of an OR or AND stay false by design
  (`identifiers.flag_source`). Found on the way and not fixed: items 21 to
  23.

- A blob made matching slow (item 16, Priority 15; 2026-09-30). A query of
  few words and many characters (one long token, embedded base64, a run of
  60-character tokens) went through the full RapidFuzz alignment scan on
  every candidate: 27 words plus one 2,000-character token took 5 s, and
  5,000 characters about 60 s. The scan's cost follows the query's length in
  characters, but its guards counted words: the probe is built only for
  120-499 words, and 500 words or more already fell back to
  `token_sort_ratio`. Base64 is split at `+` and `/` when normalised, so it
  arrives as many medium tokens: dropping long tokens would not have been
  enough. A first fix scored a query of more than 16 characters a word with
  `token_sort_ratio`, and review found that it lost Japanese licence text:
  Japanese is written without spaces, so a 1,570-character slice of
  CC-BY-SA-2.1-JP (104 words) fell from a certain match to 0.5. Characters
  per word says nothing about a blob. The guard now uses the probe:
  - a query of 1,500 characters or more always has a probe, cut from its
    middle by characters when it has fewer than 120 words;
  - a probe is at most 500 characters, where its own cost jumps (15 ms a
    candidate at 500, 43 ms at 600, 136 ms at 1,000); the 60 words of a
    base64 probe had been 1,900 characters;
  - the scan takes at most 6,000 characters (`similarity.alignment_affordable`,
    the one judge of it); a longer query gets `token_sort_ratio`.

  A blob fails its probe, so each candidate costs a few milliseconds; a
  Japanese slice passes it and is scanned as before. No fixture query
  reaches the character limits (at most 1,427 characters unprobed, 5,478
  probed). Trimming the 16 fixture probes longer than 500 characters, all
  Japanese or Chinese, keeps every one's top answer; only ranks two and
  three, at scores near 0.11, change. Still bounded but not free: an
  unprobed query just under 1,500 characters (a 1,000-character token)
  takes about 1 s, as on `main`, and a licence-like middle among blob
  tokens under 6,000 characters is item 11.

- A tag read with a hand-written grammar, and an ID path that read only
  `WITH` (items 15 and 17, Priorities 15 and 16; 2026-09-21).
  `MarkerDetector._RE_SPDX` wrote the SPDX grammar into a regex: it wanted a
  bare ID first, so `(MIT OR Apache-2.0)` was dropped; it wanted an ID after
  every operator, so `MIT OR (Apache-2.0 AND BSD-3-Clause)` was cut to `MIT`
  and reported as a certain match for the wrong license; and its character
  class had no `:`, so `DocumentRef-x:LicenseRef-y` was cut to
  `DocumentRef-x`. Meanwhile `matcher._try_explicit_id_match` knew a database
  row or a `<license> WITH <exception>` and nothing else, so `LicenseRef-Foo`
  and `Apache-2.0+` were no match though the same values in a tag were.
  The tag value is now the rest of its line and
  `identifiers.leading_expression` decides where the expression ends: only
  AND, OR and WITH join two parts, so a token none of them bridges ends it
  (`CAL-1.0 Licensed under ...` is `CAL-1.0`), and a dangling or unbalanced
  value is no expression at all. Comment closers need no case of their own.
  The tag branch and the explicit-ID path both resolve through the function
  JSON, TOML and INI already used (`resolve_license_value`), and
  `_match_with_expression` was deleted as redundant. An "or later" grant is
  read before the value is read as an expression, so it qualifies the ID
  beside it instead of looking like the OR operator. `:` was added to
  `identifiers._RE_TOKEN`, which silently dropped it, and an identifier now
  ends alphanumeric, so a trailing full stop is punctuation.
  Item 17 was then settled the other way round (2026-09-24): `--id` is a
  declaration of ONE license, not a second way in for expressions. It takes
  an ID, a `LicenseRef-*`, an ID with `+` and either `WITH` an exception; an
  `AND`/`OR` expression, a license name, an SPDX URL and prose exit 2
  (`option: invalid: --id: <value>; pass one license ID`), where the first
  attempt had `--id` read a tag's whole grammar and silently cut prose off
  the end (`--id "BSD-3-Clause but modified"` answered `BSD-3-Clause`).
  `identifiers.is_simple_expression` is the one judge of that rule, read by
  the CLI (`reject_compound_id`) and the matcher alike. What a *file* holds
  is unchanged: a tag and a `license` field still carry any expression.
  Three deliberate tightenings: a tag and its value must be on one line; a
  bare CLI argument is read as an ID only when it names one license and every
  part is recognised (`licenseid match "MIT or something"` no longer prints
  an invented ID at similarity 1.0000); and a 400-term chain given as an ID
  is a usage error rather than a question for the parser, which is why item
  19 now bites only on a tag. Over the 1,405 fixture files the before/after
  run differed nowhere. Left open: item 18, item 19 and the new item 20.

- An unknown SPDX tag reported as a certain match (item 6, Priority 15;
  2026-09-21). `SPDX-License-Identifier: NoSuchLicense-9.9` (or a typo such
  as `Apache-2.O`, or `Copyright`, `NONE`) made `match` return that ID with
  score 1.0 and `is_spdx: true`, while `is-spdx` said false. The tag branch
  built a placeholder candidate for any value; the JSON, TOML and INI
  `license` fields already used a stricter rule of their own
  (`MarkerDetector._synthetic_candidate`). The tag took that same function,
  so every source of an expression decides alike: a value with no
  recognised ID builds no candidate and matching
  falls through to the text tiers; a valid expression (or `LicenseRef-*`)
  with at least one recognised ID is a candidate, with `is_spdx` false if
  any part is unknown; the OSI and
  FSF flags of a `WITH` expression are its license's, as for an explicit
  `license_id`; so are those of a lone `+` ID. A `+` operator is read
  (`Apache-2.0+`), which `py_spdx_license` cannot parse, and kept in an
  explicit `Apache-2.0+ WITH X`. The same function serves the JSON, TOML and
  INI `license` fields, so they also read `+` now and give a `WITH` value its
  license's flags. The CLI's `is-*` commands used to look the top ID up in the
  database on their own, so they said false for every expression and
  `LicenseRef-*` that `match` accepted; they now call
  `AggregatedLicenseMatcher.resolve_record`, the same code as the `is_*()`
  predicates, for `--id`, a positional ID and text alike. One parser wrapper,
  `identifiers.parse_expression`, served the synthetic candidate, the `WITH`
  match and `_canonicalize_expression`, and one `WITH` lookup,
  `identifiers.with_expression_details`, the first two (items 15 and 17 later
  deleted the separate `WITH` match).
  `tests/test_spdx_tag.py` holds the table of tags and checks that the API
  and the CLI agree on each. Not done: a `NONE` or `NOASSERTION` tag reads
  as unknown (valid in SPDX documents, not licenses); the tag regex became
  item 15. "Known" for a license ID follows `py_spdx_license`'s bundled list, not
  the database, as it did for the `license` fields; a license newer than that
  list in an expression makes it `is_spdx` false.
- API `file_path` read as strict UTF-8 (item 4, Priority 16; 2026-09-21).
  `match(file_path=...)` raised `UnicodeDecodeError` on Latin-1 or UTF-16
  and matched NUL bytes and a byte order mark as text, while the CLI reads
  the same file with a Latin-1 fallback, a warning and a binary check. The
  decoder moved from `cli.py` to `licenseid.textinput`, and
  `textinput.read_text_file` is now the only place a user file becomes text,
  for the CLI and the API alike (`tests/test_textinput.py` and the parity
  test in `tests/test_option_matrix.py` keep it so). Left as they were, on
  purpose: SPDX data files (`database.py`, `spdx_source.py`) stay strict
  UTF-8, since a Latin-1 fallback there would hide a corrupt download.
  Known gaps, not part of this item: `match(text=...)` does not check for a
  NUL byte or normalise line ends as `--text` does, and an empty file
  returns no match instead of an error.
- Comment prefixes stripped twice in retrieval (item 14, Priority 10;
  checked 2026-09-21, not a defect). `retrieval.get_candidates` calls
  `strip_comment_prefixes` before `normalize_text` on purpose: the two
  regexes differ. A prefix that `normalize_text` leaves behind (`;`, `;;`,
  `///`, `**`) hides a list marker from its bullet rule, so `; 1. term`
  keeps the `1` in the query. A first random check (3,000 inputs without
  list markers) missed this; `tests/test_get_candidates.py` now pins it.
- One ranking order, and a consistent `-only` / `-or-later` tie-breaker (item
  8, Priority 12; widened on 2026-09-20 to the whole tie-breaker). Three sorts
  in `matcher.py` had drifted apart: the main ranking took `DEP_PENALTY` off
  a deprecated ID, the tie-breaker's re-sort did not (so it could put a
  deprecated ID back above its replacement), and `match_short_text` carried
  keys its results never have. All three now use `ranking.ranking_key`, or (short
  text) `(-score, license_id)`. Three more inconsistencies in the tie-breaker:
  its 0.01 window was decided by the last bit of a float (`0.91 - 0.90` is not
  a tie, `0.35 - 0.34` is), now compared after rounding to 9 places and named
  `TIE_WINDOW` (in `ranking.py`); and three readers of "or later" disagreed.
  The tie-breaker,
  the bare-ID prose path (`identifiers`) and the marker detector (`markers`)
  each had a regex of their own, so `version 2 of the License, or any later
  version` came out `-only` from the marker detector and `-or-later` from
  Tier 0. They
  now share `classify.OR_LATER_PHRASE` (with a `not`/`no` guard), and
  `tests/test_match_ordering.py` pins that both paths read every phrase alike.
  Measured with a before/after run over the fixtures plus 160 synthetic
  headers (4,741 results): 344 changed. 184 are fixture results; 182 of them
  are GFDL slices or distorted copies that moved from `-only` to `-or-later`
  (the GNU Free Documentation License's own text says "or any later
  version", and the `-only` and `-or-later` variants have identical bodies),
  and 2 differ only at rank 5. The other 160 are synthetic headers; 32 of
  them changed their top answer, all `-only` to `-or-later`, for `or newer`.
  Of the 3,249 license-text results (both popularity settings), 1,949 had the
  right top answer before and 1,948 after (30 GFDL `-only` rows lost it, 29
  `-or-later` rows gained it).
  The GPL family already behaved this way.
  Left open: the tie-breaker is applied once per `match()` and is not
  idempotent (a second pass on a pair whose preferred side started below its
  peer nudges it again); the +/-0.005 nudge is kept on purpose, so results stay
  sorted by score, at the price of moving reported scores by up to 0.005 and
  letting a pair member pass an unrelated license within that; the name-based
  reader in `markers.MarkerDetector._name_variants` (`or any version later`)
  is a fourth regex that is not shared; `is_pure_license_text` does not flag
  slices of a license, so a quoted notice in one still counts as a grant.

- `match()` silently ignored unknown options (item 1, Priority 20):
  `AggregatedLicenseMatcher.match()` now raises
  `InvalidInputError('option: invalid: <names>; use one of ...')` for a key
  outside `MatchRequest` (a typo, or a removed option such as `enable_java`),
  before it looks at any input, so an explicit `license_id`, empty text or an
  unreadable file cannot let one through. The names are sorted, so the message
  is stable. The `is_*` predicates already refused an unknown keyword, with the
  interpreter's `TypeError` rather than this message; that difference is left.
  Left open: a *known* option is still ignored when `match()` returns before
  ranking (an explicit `license_id`, a bare ID or name, an
  `SPDX-License-Identifier` tag), so `match(license_id="MIT", exclude=["MIT"])`
  returns `MIT`. See item 5. Tests: `tests/test_match_options.py`.

- `py-spdx-license` upper bound (item 3, Priority 16): the requirement is
  now `py-spdx-license>=0.0.1,<0.1`. Version 0.0.1 is a single release with
  no type information, so a 0.0.x API can change without notice; only
  `markers.py` imports it. Raise the bound by hand after checking the new
  release against `tests/test_markers*.py`.

- Unready database answers silently (2026-09-19 audit): after a failed first
  `update`, `match` said "no license found" and `is-osi` printed `false`
  (exit 1); a non-SQLite `--db` or a directory crashed with a traceback; and
  a read command on a 0-byte file wrote tables into it. Now `match`, the
  `is-*` commands and `AggregatedLicenseMatcher()` check readiness first, read
  only, and report `database: not found`, `empty`, `invalid` (another
  program's objects beside an incomplete set of ours, or a `licenses` table
  without our columns; no `update` hint, as it would write into the file) or
  `unreadable` with exit 2 (`DatabaseNotReadyError`). Ready means the
  `licenses`, `db_metadata` and `license_index` (FTS5) tables exist,
  `license_list_version` is not blank, every `license_id` is text, and
  `licenses` and `license_index` each have a row. The check reads with plain
  `mode=ro`: `immutable=1` was tried and dropped, because every database
  licenseid writes is in WAL mode and immutable turns locking off, so a read
  during an `update` could see a torn file.
  The check is structural, not `PRAGMA quick_check` (about 200 ms on a real
  database, twice per command): damaged pages that keep the schema and the
  first rows plausible can still give a wrong answer. A fuzz run found only
  page swaps of the `licenses` root page (exit 1 or a traceback before the
  `typeof` probe, `NOT INDEXED` and exact column names were added).
  A table of ours whose schema is not ours is `invalid` too: the table names
  are common enough (`licenses`, `db_metadata`) that a seat inventory or an
  asset register hits them, and calling such a file `empty` used to send the
  user to `update`, which wrote licenseid's schema into it.
  Same change: `get_default_db_path()` no longer creates the directory (only
  `update` does) and `--clear-cache` works on the path without opening the
  database, so read commands no longer crash on an unwritable `HOME` and a
  corrupt database can be cleared. Because they write or delete, `update` and
  `--clear-cache` call `reject_foreign_database` first (it runs inside
  `LicenseDatabase.clear_cache`, so the Python API refuses what the CLI
  refuses). It refuses an `invalid` database, anything that is not a regular
  file with the SQLite header, a path naming no file, a file it may not read,
  and an `unknown` one; it accepts every other condition, which is what those
  commands are for. Gate and guard resolve one file the same way through every
  spelling of it, by path (`licenses.db`, `licenses.db/`, `licenses.db/.`) and
  by URI (`file:`, `file://`, `file://localhost`, `?vfs=`), and refuse
  anything that is not a regular file or a directory: a named pipe would have
  held the read-only open for ever. Only `mode=memory` and the exact base
  `file::memory:` are memory; `file::memory:notes` names a file on disk.
  Reading is the opposite way round: an `unknown` database
  is not refused, because a wrong refusal costs the user an answer they could
  have had.
  Left open: the metadata is committed before the fingerprints are computed,
  so a kill in between leaves a "ready" database without fingerprints. That
  is not merely a degraded answer — measured on a real database, the top
  match changes (`MIT` becomes `Xnet` for MIT text), so the command reports a
  different license with no warning. Fix by writing the metadata in the
  fingerprint transaction, or by adding a fingerprint row to the readiness
  check. A `sqlite3` failure after the check exits 2 on the CLI
  (`database: unreadable`); the API keeps raising the raw error (item 10).

- `cli.py` test coverage (2026-09-19 audit, Priority 18): was 66-75%. Now
  100% of lines and branches, from `tests/test_cli_errors.py`,
  `tests/test_cli_input.py`, `tests/test_cli_output.py` and the combination
  matrix `tests/test_option_matrix.py`.
- Tier 3 Java path (2026-09-19 audit, Priority 15): untested and silent on
  failure, so removed instead of fixed. The optional `tools-java` tier
  (`--java`, the `licenseid[java]` extra, `SPDX_TOOLS_JAR`) was off by
  default and not tested in CI; removed on 2026-09-19 (see `CHANGELOG.md`).
- Library diagnostics on standard output (2026-09-19 audit, Priority 16
  after re-scoring): progress, the `Data sources:` report and warnings from
  `licenseid update` and `--clear-cache` now go to standard error through
  `licenseid.console` (`status`, `warn`, `error`); standard output carries
  only the result line. Error and warning texts were rewritten to one
  `LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION]` grammar (see `AGENTS.md`),
  guarded by `tests/conftest.py::check_diagnostic_grammar`. Drive-by: the
  license-preparation progress line wrongly said `Preparing exception
  data...`.
- Type-1 `id_casing` and `id_deprecated` accuracy gaps — implemented; see
  the status note at the top of
  [`optimization-recommendation.md`](optimization-recommendation.md).
- `matcher.py`/`database.py` complexity and file size — tracked
  separately now in
  [`complexity-and-file-size-roadmap.md`](complexity-and-file-size-roadmap.md)
  rather than here, since it has its own linter-enforced ratchet.
- Stale `docs/implementation/` navigation (no current-state entry point)
  — fixed by `working-docs/implementation/README.md`.
- `requests` dependency floor, stale benchmark plan docs — resolved.
- CI guard rails (2026-09-19 audit, phase 0): the type check ran with
  `--no-strict-optional` and `continue-on-error`, so it never failed a build; CI
  ran neither `flake8` nor `pylint tests/`. Now `mypy` (strict, `src/` and
  `tests/`, from `[tool.mypy] files`) blocks, `lint.yml` runs `pylint` and
  `flake8` on `src/` and `tests/`. Tests stay on Python 3.10 and 3.14 only, to
  save CI resources. Same pass: removed a stdout debug line from the `--java`
  path, the unused `debug_gpl.db`, a `working-docs/` link and a wrong PR link in
  `CHANGELOG.md`; added `codemeta.json`, now the source that `codemeta2cff.yml`
  generates `CITATION.cff` from.
