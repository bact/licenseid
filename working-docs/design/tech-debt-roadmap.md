---
Created: 2026-08-19
Last-Modified: 2026-09-21
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
2026-09-19; items 4, 5, 6 and 12 (and the resolved item 1) from code reviews
of the diagnostics change and the Java removal; items 2 and 10 from manual
CLI testing under other locales and environments.

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
  (`ast.py` lines 22 and 34). Pylint `unspecified-encoding` (W1514) and
  Python's `-X warn_default_encoding` flag exactly this.
- **Upstream fix** (report and send a pull request to
  `github.com/JPEWdev/py-spdx-license`): use
  `p.open("r", encoding="utf-8")`, or `json.loads(p.read_bytes())`, which
  lets the `json` module detect UTF-8 itself. Add a test that runs the
  import under `-X warn_default_encoding -W error`.
- **Workaround until a release** (choose one): document `PYTHONUTF8=1`;
  or vendor the two JSON files. Importing `py_spdx_license` lazily would
  only move the crash to marker detection, so it is not a cure.
- Impact 2, Risk 3, Effort 2.

## 4. API `file_path` input is read as strict UTF-8 — Priority 16

`AggregatedLicenseMatcher.match(file_path=...)` (and the `is_*` predicates)
open the file as strict UTF-8, so a Latin-1 or binary file raises
`UnicodeDecodeError`. The CLI reads the same file through
`cli.decode_input` (Latin-1 fallback with a warning, binary rejected as
`InvalidInputError`). Pinned by
`tests/test_option_matrix.py::test_api_file_path_not_utf8` (`# BUG:`).
Fix: move `decode_input` out of `cli.py` into a shared module and use it in
`matcher._resolve_target_text`; flip the pin.

- Impact 2, Risk 2, Effort 2.

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

## 6. An unknown SPDX tag is reported as a certain match — Priority 15

In a file of 30 words or more, `SPDX-License-Identifier: NoSuchLicense-9.9`
(or a typo such as `Apache-2.O`) makes `match` return that ID verbatim with
score 1.0 and `is_spdx: true`. `MarkerDetector._detect_explicit_identifiers`
builds a candidate for any tag value that survives `normalize_identifier()`,
without checking that it parses or exists, and the matcher then stops at
Tier 0.5. `is-spdx` on the same file answers `false`, so the two commands
disagree. Found and pinned (`# BUG:`) by
`tests/test_matcher_coverage.py::test_unknown_spdx_tag_id_is_reported_verbatim`.

- **Fix**: decide what an unknown tag should return (fall through to text
  matching, or report it with `is_spdx: false` and a lower score), then flip
  the pin.
- Impact 3, Risk 2, Effort 3.

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

## 11. Probe-anchored windowing — Priority 9

The one large remaining lever on `fragment_similarity`'s dominant cost:
reuse the existing 60-word probe's match location instead of re-running
a full realignment scan. Deliberately deferred because it changes
`best_window`, which is user-facing via the CLI's `--diff` flag, not
just an internal ranking score — needs its own validation cycle (a
`bench_compare.py` run plus a manual `--diff` output quality check).

- Impact 2, Risk 2, Effort 3.
- Full plan: [`probe-anchored-windowing-plan.md`](probe-anchored-windowing-plan.md).

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

## 14. Comment prefixes are probably stripped twice in retrieval — Priority 10

`retrieval.get_candidates` calls `strip_comment_prefixes` and then
`normalize_text`, whose own comment-prefix rule may already cover it. A
mutation audit (2026-09-21) found that removing the call changes no test,
and 3,000 random `//`, `#`, `;`, `*`, `/*`, `--` inputs normalised
identically with and without it. The two regexes are documented as
separate on purpose (`normalize.py`), so this is unproven: find an input
where they differ (a lone `*/` line, or an odd prefix) or remove the call.

- Impact 1, Risk 1, Effort 1.

## Already resolved (kept for record)

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
