---
Created: 2026-08-19
Last-Modified: 2026-09-19
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

Items 3, 8 and 9 come from a tech-debt audit on 2026-09-19; items 1, 4, 5,
6 and 12 from code reviews of the diagnostics change and the Java removal;
items 2 and 10 from manual CLI testing under other locales and environments.

## 1. `match()` silently ignores unknown options — Priority 20

`AggregatedLicenseMatcher.match(text, *, license_id, file_path, **options)`
casts `options` to `MatchRequest` and never checks the keys. A mistyped
option (`enable_popularty=True`) or a removed one (`enable_java=True`, gone
with the Java tier) is accepted and has no effect, with no error or warning:
a silent deviation. Pinned by
`tests/test_removed_java.py::test_stale_enable_java_option_is_ignored_silently`
(`# BUG:`).

- **Fix**: reject keys not in `MatchRequest.__annotations__` with
  `InvalidInputError('option: unknown: <name>')`; flip the pin.
- Impact 2, Risk 3, Effort 2.

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

## 3. `py-spdx-license` has no upper bound — Priority 16

Version 0.0.1, a single release, with no type information (a mypy
`ignore_missing_imports` override). The author is credible, but a 0.0.x
API can change without notice. Only `markers.py` imports it.

- **Fix**: add `<0.1` to the requirement.
- Impact 1, Risk 3, Effort 2.

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

## 8. Local `sort_key` functions disagree on deprecated IDs — Priority 12

`matcher.py` sorts candidates with a local `sort_key` in two places. The main
ranking subtracts `_DEP_PENALTY` from a deprecated ID's score;
`_apply_version_suffix_tiebreaker`'s re-sort does not. The audit scored this
20 as a ranking bug, but it is unreachable today: deprecated IDs are not in
the FTS index (0 of 32 in the real DB), marker candidates never set
`is_deprecated`, and the only way in is the Python API's `hint=`, whose
candidates have empty search text and cannot come within `_DEP_PENALTY` of an
`-only`/`-or-later` pair. Real GPL, LGPL, AGPL and GFDL texts (full,
head-300, tail-300) never rank a deprecated ID in the top 4. (A third sort,
after the removed Java tier, is gone.) `_match_short_text`'s final sort also
keys on `is_deprecated` and `pop_score`, which its results never carry, so
only the score and ID order apply there.

- **Fix**: one module-level sort key for both sorts, with characterisation
  tests first.
- Impact 2, Risk 1, Effort 2.

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

- **`--clear-cache` and `update` when the default directory cannot be
  made** (unwritable `HOME`): the `mkdir` error is a traceback for
  `--clear-cache`. (A foreign file or a read-only directory given with `--db`
  now exits 2 with `database: unreadable`.)
- **Closed standard input** (`<&-`): `AttributeError: 'NoneType' object has
  no attribute 'isatty'` from `read_input`.
- **Closed standard output** (`>&-`): exit 0 and the result is lost. A
  script sees success with no data.
- **Output error** (`ulimit -f 0` with output to a file): `OSError`
  traceback and exit 120, instead of one `ERROR:` line.
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

## Already resolved (kept for record)

- Unready database answers silently (2026-09-19 audit): after a failed first
  `update`, `match` said "no license found" and `is-osi` printed `false`
  (exit 1); a non-SQLite `--db` or a directory crashed with a traceback; and
  a read command on a 0-byte file wrote tables into it. Now `match`, the
  `is-*` commands and `AggregatedLicenseMatcher()` check readiness first, read
  only, and report `database: not found`, `empty` or `unreadable` with exit 2
  (`DatabaseNotReadyError`). Ready means the `licenses` and `db_metadata`
  tables exist, `license_list_version` is not blank and `licenses` has a row.
  Same change: `get_default_db_path()` no longer creates the directory (only
  `update` and `--clear-cache` do), so read commands no longer crash on an
  unwritable `HOME`.
  Left open: the metadata is committed before the fingerprints are computed,
  so a kill in between leaves a "ready" database without fingerprints (fix by
  writing the metadata in the fingerprint transaction). A `sqlite3` failure
  after the check exits 2 on the CLI (`database: unreadable`); the API keeps
  raising the raw error (item 10).

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
