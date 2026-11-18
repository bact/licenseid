# Benchmarking — how it works

Recall/precision/speed/memory comparison between the current working tree
and `main`, across all input types the matcher handles. Implementation
notes for the actual scripts. The baseline of `bench_compare.py` is fixed in
the script to `main` (`baseline_label`); to compare with a release tag, change
that label.

## Running it

```bash
python benchmarks/bench_compare.py
```

- `--subset N` — stratified N-fixture subset for Type 3/4 fixtures only
  (Type 1, 2, 5, 5.1 always run in full). Shortens iteration cycles.
- `--fast` — reduced matrix: Type 3 tests `head_800` only (skips `head_300`
  and `head_500`); Type 4 tests `verbatim`/`02` only (skips
  `01`/`05`/`10`/`20`).
- `--verify` — 1-2 items per input type, for validating script changes
  without running the full matrix.

Full run with no flags takes about 2 hours.

## Architecture

- **`bench_compare.py`** — orchestrator. Creates a pristine `git worktree`
  of `main` in a temp dir (not a branch switch — avoids disturbing the
  working tree), runs `bench_single.py` against that worktree's `src/`,
  then against the current tree's `src/`, and diffs the two result sets
  into `benchmarks/summary.md`. Cleans up the worktree in a `finally`
  block.
- **`bench_single.py`** — runs one branch's evaluation in a subprocess
  (`sys.path.insert(0, <src_path>)` picks up whichever tree it's pointed
  at). Builds its own in-memory SQLite DB directly from the SPDX data
  tarball, bypassing `LicenseDatabase._update_db_records` — schema fields
  that a fixture or matcher path depends on must degrade gracefully or be
  built lazily, since this path won't populate them the way the real CLI
  does. Wraps the matcher in `InstrumentedMatcher` to record which tier
  (0 / 0.5 / 1 / 2) resolved each query. Measures wall time with
  `time.perf_counter()` and peak memory with `tracemalloc`. Writes one
  JSON result file per branch to `benchmarks/outputs/`. Its parts are
  `bench_single_db.py` (the database), `bench_single_matcher.py`
  (`InstrumentedMatcher`), `bench_single_fixtures.py` (the fixtures of each
  type), `bench_single_board.py` (the counters) and `bench_single_run.py`
  (the run and the result file). It also takes `--tarball PATH` (default:
  the newest tarball in the licenseid cache); `bench_compare.py` does not.
- **`bench_report.py`** — renders the two result sets as the Markdown of
  `summary.md`.

Both scripts are invoked as standalone processes (not imported), so a
branch's `src/` fully determines its behavior with no import-caching
cross-contamination between the two runs.

## Input types and fixtures

| Type | Fixtures | What it tests |
| --- | --- | --- |
| 1 — License IDs | `tests/fixtures/license-id/license_ids.json` | Each `id_*` field (`id_verbatim`, `id_deprecated`, `id_space`, `id_casing`, `id_punct`, `id_distorted`) should resolve to `license_id` |
| 2 — License names | `tests/fixtures/license-name/license_names.json` | `name_verbatim`, `name_space`, `name_casing`, `name_punct`, `name_distored` fields (the fixture file spells it so) |
| 3 — Short text | `tests/fixtures/license-text-short/*.json` | The `license_text_short_head_300`, `_500` and `_800` keys of each file |
| 4 — Long text | `tests/fixtures/license-text-long/*.json` | Clean `license_text` plus distortion variants (`01`/`02`/`05`/`10`/`20`; `20` is heaviest — character-level, breaks word tokens) |
| 5 — Mixed content | `tests/fixtures/mixed-content/` | Generated source/doc files with embedded license info, per canonical-ID directory |
| 5.1 — Mixed content (curated) | `tests/fixtures/mixed-content-curated/` | Same evaluation as Type 5, but hand-crafted fixtures instead of generated ones |

Stats are nested `stats[input_type][sub_category]`, each tracking
`total`/`top1`/`top3`/`top5` (plus per-tier resolution counts from
`InstrumentedMatcher`). `bench_compare.py` renders this into per-type
Markdown tables in `summary.md`.

## Other paths worth knowing

- Real (non-benchmark) on-disk DB: `~/.local/share/licenseid/licenses.db`,
  built from `spdx-data-v3.29.0.tar.gz` in the same directory.
- Failure diffing: compare the `failures_sample` arrays (the first ten
  failures) between the two branches' JSON files in `benchmarks/outputs/`.

## Also in this directory

- `bench_fts5_recall.py` — standalone FTS5 pool-recall probe, not part of
  the main/current comparison flow above.
- `summary.md` — output of the most recent `bench_compare.py` run.
