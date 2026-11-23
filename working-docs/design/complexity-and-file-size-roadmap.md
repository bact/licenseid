---
Created: 2026-08-19
Last-Modified: 2026-11-23
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Complexity and file-size roadmap

See also: [`tech-debt-roadmap.md`](tech-debt-roadmap.md) for the rest of
the backlog. `AGENTS.md`'s Linting and formatting section and the
`pyproject.toml`/`.flake8` comments both point here.

## Why this exists

`AGENTS.md` states target complexity and size thresholds. The linter ceilings
in `pyproject.toml` (`[tool.pylint.design]`, `[tool.pylint.format]`) and
`.flake8` are **interim ratchets** set to the *exact* current repo maximum
where it exceeds the target, so any regression, even one point over the worst
offender, fails CI. `lint.yml` runs `pylint src/ tests/` and `flake8 src/
tests/` (since 2026-09-19). This doc is the backlog that has to shrink before
each ceiling can be tightened toward its target.

"Target" below is pylint's own built-in default for that option, checked
clean (`cd /tmp && pylint --generate-toml-config`) rather than assumed —
running it inside this repo silently reflects our own overrides instead
of pylint's real defaults, which is how an earlier pass of this doc ended
up quoting pitloom's Branches≤20/Statements≤80 as if they were standard;
pylint's actual defaults are 12 and 50.

Measured 2026-11-18 on the 0.9.0 candidate, across `src/` and `tests/`, with
the commands of
[`../implementation/complexity-refactors.md`](../implementation/complexity-refactors.md)
("Re-measured 2026-10-29"), each at ceiling 1 so that every function is
listed. How the ceilings moved before, and the refactors done, are in that
file.

| Metric | Target (pylint default) | Ceiling (config) | Measured worst |
| --- | --- | --- | --- |
| Args | ≤5 | 5 (at target) | 5 (17 functions in `src/`, e.g. `similarity.py`, `variantstated.py`; many tests) |
| Locals | ≤15 | 22 | 22 (`markers._detect_gpl_headers`); next 21 (`detector._rank_candidates`), 19 (`clidetect`) |
| Nesting | ≤5 | 5 (at target) | 5 (`detector._match_mixed_content`) |
| Branches | ≤12 | 13 | 13 (`identifiers._normalize_expression`, alone); next 12 (`tests/test_accuracy.py::run_accuracy_test`), 11 in `src/` |
| Returns | ≤6 | 6 (at target) | 6 (16 functions in `src/`) |
| Statements | ≤50 | 35 (config) | 35 (`markers._detect_gpl_headers`, `tests/test_update_matrix.py::test_update_matrix`) |
| McCabe | ≤10 | 12 | 12 (`identifiers.read_leading`, alone); next 11 (four holders) |
| Cognitive | ≤15 | 29 | 29 (`identifiers.read_leading` and `tests/test_accuracy.py::run_accuracy_test`); next 25 (`detector._match_mixed_content`) |
| Module lines | soft 400-500 / hard 800 | 734 (config) | 734 (`markers.py`; re-measured 2026-11-23); next `identifiers.py` 703, `dbcheck.py` 689 |

The module-lines ceiling in `pyproject.toml` is an exact ratchet again (734,
after the split of `tests/test_option_matrix.py`, 2026-11-23); the Statements
ceiling is 35, also exact. Nothing else can drop without a refactor:
Branches to 12 needs `identifiers._normalize_expression` (13); McCabe to 11
needs `identifiers.read_leading`; Cognitive to 28 needs two functions
(`read_leading`, `run_accuracy_test`; then 25); Locals to 21 needs
`markers._detect_gpl_headers`. `identifiers.read_leading` holds McCabe and
(with a test helper) Cognitive: refactoring it moves one ceiling and halves
the other.

Files over 600 lines (`git ls-files`, `wc -l`; the four names of `AGENTS.md`
are one file; generated outputs left out):

| Lines | File |
| --- | --- |
| 747 | `AGENTS.md` (also `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`) |
| 741 | `docs/resolve.md` |
| 734 | `src/licenseid/markers.py` |
| 703 | `src/licenseid/identifiers.py` |
| 689 | `src/licenseid/dbcheck.py` |
| 684 | `working-docs/implementation/declared-value-resolver-0-7.md` |
| 679 | `tests/test_variant.py` |
| 678 | `working-docs/paper-notes/ai-sessions-recent.md` |
| 676 | `working-docs/paper-notes/results-and-findings.md` |
| 656 | `src/licenseid/database.py` |
| 640 | `tests/test_cli_matrix_judge.py` |
| 638 | `src/licenseid/resolveleaf.py` |
| 637 | `working-docs/implementation/tech-debt-resolved-0-9.md` |
| 631 | `tests/test_clear_cache.py` |
| 624 | `tests/test_cli_matrix.py` |
| 618 | `tests/test_namehits.py` |

`CHANGELOG.md` (1,071 lines) is over the hard limit: it is one file by
design. No other file is over 800. Within 100 lines of the hard limit:
`AGENTS.md`, `docs/resolve.md`, `markers.py`, `identifiers.py`. The next
change to `markers.py` or `identifiers.py` should split first (the `AGENTS.md`
rule).

## Backlog, priority order

Priority = (Impact + Risk) × (6 − Effort), same scoring as the general
tech-debt roadmap. Refactors already done are in
[`../implementation/complexity-refactors.md`](../implementation/complexity-refactors.md).

### 1. `database.py` — split by responsibility (Priority 9)

656 lines (re-measured 2026-11-18), over the 500-line soft limit. Record
building moved to `records.py` and the SPDX release reader to `spdxdata.py`
in PR #85. Left in the file: update orchestration and the query methods. Not
a complexity offender; a file-size problem only.

- **Fix**: move the `get_*`/`search_*` query methods to their own module,
  re-exported from `database.py`, if the file grows past the hard limit.
- Impact 1, Risk 1, Effort 2.

## Out of scope for now

- `clidetect.detect_command` (McCabe 9, cognitive 22, 10 branches on
  2026-11-18) is at target except for cognitive complexity.
- `tests/test_accuracy.py::run_accuracy_test` (cognitive 29) shares the
  repo's Cognitive ceiling with `identifiers.read_leading`: a
  benchmark-table-printing test helper, not production code. Not a
  priority-ranked backlog item, but a blocker once `read_leading` is
  refactored.
