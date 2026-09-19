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

Items 1, 2, 4 and 6 come from a tech-debt audit on 2026-09-19; item 3
from the review of the diagnostics change.

## 1. `cli.py` test coverage is 75% — Priority 18

The lowest-covered module, and the user-facing contract: output formats,
exit codes and `is-*` predicates. Was 66% at the audit;
`tests/test_cli_errors.py` (2026-09-19) now pins the error paths.

- **Fix**: one CLI test per output format and exit code in `README.md`.
- Impact 3, Risk 3, Effort 3.

## 2. `py-spdx-license` has no upper bound — Priority 16

Version 0.0.1, a single release, with no type information (a mypy
`ignore_missing_imports` override). The author is credible, but a 0.0.x
API can change without notice. Only `markers.py` imports it.

- **Fix**: add `<0.1` to the requirement.
- Impact 1, Risk 3, Effort 2.

## 3. API `file_path` input is read as strict UTF-8 — Priority 16

`AggregatedLicenseMatcher.match(file_path=...)` (and the `is_*` predicates)
open the file as strict UTF-8, so a Latin-1 or binary file raises
`UnicodeDecodeError`. The CLI reads the same file through
`cli.decode_input` (Latin-1 fallback with a warning, binary rejected as
`InvalidInputError`). Pinned by
`tests/test_option_matrix.py::test_api_file_path_not_utf8` (`# BUG:`).
Fix: move `decode_input` out of `cli.py` into a shared module and use it in
`matcher._resolve_target_text`; flip the pin.

- Impact 2, Risk 2, Effort 2.

## 4. Tier 3 Java path is untested and silent on failure — Priority 15

`_ensure_jvm` and `_consult_java` have no test coverage beyond the missing
JPype message. A broad `except Exception: pass` makes a JVM failure look
like "no Java match".

Folded in: `matcher.py` sorts candidates in three places with a local
`sort_key`. The main ranking subtracts `_DEP_PENALTY` from a deprecated
ID's score; the re-sorts after `_consult_java` and
`_apply_version_suffix_tiebreaker` do not, and the Java re-sort reads
`self.enable_popularity`, ignoring a per-request `enable_popularity`. The
audit scored this 20 as a ranking bug, but it is unreachable today:
deprecated IDs are not in the FTS index (0 of 32 in the real DB), marker
candidates never set `is_deprecated`, and the only way in is the Python
API's `hint=`, whose candidates have empty search text and cannot come
within `_DEP_PENALTY` of an `-only`/`-or-later` pair. Real GPL, LGPL, AGPL
and GFDL texts (full, head-300, tail-300) never rank a deprecated ID in the
top 4. Re-scored on its own: Impact 2, Risk 1, Effort 2 = 12.

- **Fix**: tests with an autospec'd fake `jpype`; warn on failure through
  `console.warn()`; one module-level sort key for all three sorts, with
  characterisation tests first.
- Impact 2, Risk 3, Effort 3.

## 5. GPL/LGPL/AGPL family disambiguation (tail recall floor) — Priority 12

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

## 6. `scripts/` and `benchmarks/` are not linted in CI — Priority 12

`bench_single.py` (770 lines) and `generate_fixtures.py` (755) are near
the 800-line hard limit. Pylint rates the two directories 9.48/10;
`flake8` reports 11 findings. CI checks only `src/` and `tests/`.

- **Fix**: fix the findings, then add both directories to `lint.yml`.
- Impact 1, Risk 2, Effort 2.

## 7. Probe-anchored windowing — Priority 9

The one large remaining lever on `fragment_similarity`'s dominant cost:
reuse the existing 60-word probe's match location instead of re-running
a full realignment scan. Deliberately deferred because it changes
`best_window`, which is user-facing via the CLI's `--diff` flag, not
just an internal ranking score — needs its own validation cycle (a
`bench_compare.py` run plus a manual `--diff` output quality check).

- Impact 2, Risk 2, Effort 3.
- Full plan: [`probe-anchored-windowing-plan.md`](probe-anchored-windowing-plan.md).

## 8. Apache-2.0 vs Pixar near-duplicate confusion — Priority 6

Licenses that are near-identical modifications of another license (e.g.
`Pixar` is `Apache-2.0` with a modified section 6) can be misidentified
as the parent license. See
[`new-matcher.md`](new-matcher.md) for the background analysis and word-count
statistics; no fix has been designed yet, only the problem is documented.

- Impact 2, Risk 2, Effort 4 (needs a design pass before an effort
  estimate is meaningful — treat this as provisional).

## Already resolved (kept for record)

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
