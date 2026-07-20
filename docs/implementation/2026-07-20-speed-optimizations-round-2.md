---
title: "Speed optimisations — round 2 (results)"
date: 2026-07-20
status: implemented
---

# Speed optimisations round 2 — 20 July 2026

Follow-up to [`2026-05-07-speed-optimizations.md`](2026-05-07-speed-optimizations.md)
(planned) and the work merged in PR #19 (RapidFuzz probe-gate) and PR #21
(normalize-guidelines refactor + Tier-0 precomputed columns). This round is
a profile-driven sweep of the rest of the codebase for additional wins,
run as a find → plan → self-review → implement → test → review loop.

Unlike the round-1 doc, this one reports **results**, not a plan — every
item below was implemented and verified, including one that was reverted.
The rejected item is the most important part of this document: it was
*proposed in round 1* (`2026-05-07-speed-optimizations.md`, Optimisation
2c) and flagged there as risky ("validate on type-3 before deploying").
That warning turned out to be exactly right, and the failure mode is worth
recording so it isn't retried the same way.

---

## Method

Each change went through:

1. **Find** — profile a realistic mixed workload (`cProfile` over short
   IDs, verbatim/distorted full texts, fragments, mixed-content) to find
   the actual hot path, not a guessed one.
2. **Plan** — for DB-facing changes, check `EXPLAIN QUERY PLAN` before
   assuming an index or cache helps.
3. **Self-review** — reason about whether the change can affect *any*
   observable result, not just the happy path.
4. **Implement**.
5. **Test** — `ruff` + `mypy --strict` + full `pytest` (which includes
   `test_accuracy.py`'s concrete Top-1/Top-5 percentage assertions on the
   18-license MUST_HAVE subset at 0%/1% char distortion).
6. **Review** — re-profile to confirm the measured win, then move on.

Step 5 alone was **not sufficient** for one change (see
[Rejected](#rejected-tried-and-reverted)) — pytest's accuracy subset
passed identically before and after a regression that a full-corpus
`bench_compare.py` run caught. See
[Lessons](#lessons-for-future-optimisation-work).

---

## Accepted (kept)

### 1. Index on `licenses.name`

**File:** `database.py`

`get_license_by_name()` — used by every case-insensitive name lookup,
including the ~10 name variants `markers.py`'s `_try_license_lookup()`
tries per marker candidate — had no index to use:

```sql
EXPLAIN QUERY PLAN SELECT * FROM licenses WHERE name = ? COLLATE NOCASE;
-- before: SCAN licenses
-- after:  SEARCH licenses USING INDEX idx_licenses_name (name=?)
```

```sql
CREATE INDEX IF NOT EXISTS idx_licenses_name
ON licenses(name COLLATE NOCASE);
```

Added to `_init_db()`, which already handles migrating existing on-disk
databases (same pattern as the `norm_license_id`/`norm_name` migration
from round 1).

**Measured:** `get_license_by_name` cumulative time in profiling dropped
~3x (0.676s → 0.220s over 1317 calls in a 195-query mixed workload).
**Risk:** none — an index cannot change query results, only the plan used
to compute them.

### 2. Redundant duplicate DB lookups removed

**File:** `markers.py`

`_detect_first_line()` and `_extract_license_from_lines()`'s inner `_try`
helper each did:

```python
details = self.db.get_license_details(text) or self.db.get_license_by_name(text)
if details:
    return details
details = self._try_license_lookup(text)  # <-- redundant re-query
```

`_try_license_lookup()`'s variant list (`_name_variants()`) always starts
with the unmodified input string, so its first loop iteration already
performs `get_license_details(text) or get_license_by_name(text)` —
identical to the "direct lookup" step above it. Removed the redundant
step at both call sites; `_try_license_lookup(text)` alone is a strict
superset of what was there before.

**Risk:** none — provably identical control flow, just without repeating
the first iteration's queries.

### 3. Lazy imports for `requests` and `bs4`

**Files:** `database.py`, `normalize.py`

`python -X importtime` showed `licenseid.cli`'s import chain costing
~125ms, dominated by `requests` (~60ms, via `spdx_source.py`) and `bs4`
(~32ms, via `normalize.py`'s unconditional `from bs4 import
BeautifulSoup`). Both are needed only for uncommon paths:

- `requests` — only `licenseid update` and `--clear-cache` (network
  fetch), never `licenseid match`.
- `bs4` — only when `normalize_text()`'s own HTML-detection heuristic
  (`_HTML_TAG.search(text)`) actually fires.

Moved both imports inside the functions that need them
(`clear_cache()`/`update_from_remote()` for `spdx_source`, inside the
existing `if _HTML_TAG.search(text):` guard for `BeautifulSoup`).

**Measured:** CLI import/cold-start time **~125ms → ~31ms (≈4x)**.
**Risk:** none for correctness (same imports, same call sites, just
deferred) — verified `licenseid update`, `--clear-cache`, and HTML input
normalisation all still work end-to-end.

### 4. `get_all_names_and_ids()` instance-level caching

**File:** `database.py`

Every Tier-0 short-text `match()` call re-fetched the full ~700-row
`licenses` table (`_match_short_text` → `get_all_names_and_ids()`), even
though the table is static for the lifetime of a `LicenseDatabase`
instance (it only changes out-of-process, via a separate `licenseid
update` invocation). Added the same instance-cache pattern already used
by `get_deprecated_mappings()`:

```python
def get_all_names_and_ids(self) -> list[LicenseNameId]:
    if self._names_and_ids_cache is not None:
        return self._names_and_ids_cache
    ...
    self._names_and_ids_cache = result
    return result
```

Confirmed the only caller (`matcher.py`'s `_match_short_text`) only reads
the returned list, never mutates it, so returning the cached object by
reference is safe.

**Risk:** none within a single process/instance lifetime; caching does
not survive process restarts, so a separate `licenseid update` run is
unaffected.

### 5. `PRAGMA mmap_size` on every connection

**File:** `database.py`

Every query method opens its own short-lived connection via `_connect()`
(measured: 16 call sites, ~16 connections per `match()` call on average).
Memory-mapped I/O lets SQLite read the file directly instead of via
`read()` syscalls:

```python
def _connect(self) -> sqlite3.Connection:
    conn = sqlite3.connect(str(self.db_path), uri=self.use_uri)
    conn.execute("PRAGMA mmap_size=268435456")  # 256MB, file is ~46MB
    return conn
```

Measured ~35% faster per connection+query (0.51ms → 0.33ms), reproduced
after controlling for OS page-cache warm-up (alternated mmap/plain runs to
rule out the first run just warming the cache for the second). 256MB is
a virtual mapping, not a physical reservation — cheap even though larger
than the ~46MB on-disk file. Confirmed a documented no-op (not an error)
on `:memory:`/shared-cache URIs used by tests and benchmarks.

**Risk:** none — a read strategy, not a data change. Verified the write
path (`_write_db_records`, which also calls `_connect()`) still works via
a full `licenseid update --force`.

---

## Rejected (tried and reverted)

### `score_cutoff` on `partial_ratio_alignment`

**File:** `similarity.py`, `fragment_similarity()`

`fragment_similarity()` is 85%+ of total `match()` time on realistic
workloads (RapidFuzz's `partial_ratio_alignment` on the fragment-matching
path). The function already discards any candidate scoring below 0.6:

```python
alignment = fuzz.partial_ratio_alignment(norm_input, search_text)
fast_score = (alignment.score / 100.0) if alignment else 0.0
if fast_score >= 0.6 and alignment:
    ...  # only path that can win
return fast_score, search_text
```

RapidFuzz's `score_cutoff` parameter lets it prune the scan early instead
of computing an exact score for candidates that will be discarded anyway
— measured ~6x faster (66ms → 11ms) for the query lengths where this
path is expensive (120–500 normalised words). Passing `score_cutoff=60`
was verified to produce **byte-identical results for every candidate that
clears the cutoff** (0/80 mismatches in a direct A/B check against real
corpus data, including exact alignment window boundaries).

**Why it still regressed:** for candidates that *don't* clear the cutoff,
RapidFuzz returns `None` instead of the true sub-60 score, and the
function was flattening that to a bare `0.0`. This looked safe — a
sub-0.6 candidate can never win the top rank either way — but it isn't:
for **heavily distorted input, the true match itself is often the
sub-60-scoring candidate**, and flattening every sub-60 candidate's score
to the same `0.0` destroys their relative order, which now falls through
to unrelated tie-break criteria (`is_deprecated`, `pop_score`,
alphabetical license ID) instead of the actual similarity ranking. That
only matters for `Recall@N` with `N > 1` (the true match is no longer
rank 1, but still needs to surface within the top N) — which is exactly
why `test_accuracy.py`'s Top-1/Top-5 assertions on well-known licenses at
low distortion didn't catch it.

A full `bench_compare.py` run did catch it, with a signature that matched
the mechanism exactly — regressions concentrated in the categories where
the true match is most likely to score below 60%:

| Category | Before | After `score_cutoff` | Δ |
|---|---:|---:|---:|
| 05% distortion, Recall@1 | 71.71% | 71.71% | +0.00% |
| 10% distortion, Recall@30 | 91.17% | 89.73% | −1.44pp |
| **20% distortion, Recall@30** | 75.86% | 67.93% | **−7.93pp** |
| mixed content, Recall@10 | 80.87% | 75.41% | −5.46pp |

The gradient (flat at low distortion, increasingly worse as distortion
increases) is the tell: it tracks how often the true match's own score
legitimately falls below the cutoff, not a uniform noise effect.

**Reverted.** The root cause and this exact failure mode are documented
directly in `fragment_similarity()`'s docstring to stop it from being
retried the same way. Confirmed the revert restores baseline via a
targeted 675-fixture check (555 heavy-distortion + 120 mixed-content
fixtures, run directly rather than through the full ~50-minute
`bench_compare.py`) — results within 0.18 percentage points of `main`
(≈1 fixture, consistent with SQLite tie-break ordering noise, not a
systematic gap).

---

## Investigated, no action taken

- **`get_license_by_id_prefix`'s `LIKE` query** — confirmed via `EXPLAIN
  QUERY PLAN` that it's a full table scan (the `ESCAPE` clause disables
  SQLite's prefix-LIKE index optimisation), but it's only called on the
  explicit `license_id=` resolution path in `identifiers.py`, not in any
  per-candidate loop. Negligible at this call frequency on a 695-row
  table.
- **`configparser`/TOML-regex cost** in `markers.py`'s
  `_detect_structured_format()` — measured directly: 0.024ms and 0.11ms
  respectively even on a 5600-word license text (both fail fast on the
  first non-conforming line). Not a real cost.
- **Regex precompilation** in `markers.py`'s smaller helpers
  (`_name_variants`, `_extract_mentioned_license`) — Python's `re` module
  already caches compiled patterns; these aren't in a per-candidate hot
  loop, so precompiling would be a cosmetic change with no measurable
  benefit.
- **`get_metadata()` caching** — not called per-query (once per CLI
  invocation for staleness checks), and caching it risks returning stale
  data immediately after `update_from_remote()` runs. Not worth the risk
  for zero measured benefit.
- **Probe-anchored windowing** (reuse the *existing* 60-word probe's
  match location instead of re-running the full-query alignment scan) —
  the one remaining large lever on `fragment_similarity`'s dominant cost.
  Not attempted: it would change `best_window`, which is user-facing via
  the CLI's `--diff` flag, not just an internal ranking score. Needs a
  deliberate decision and its own validation cycle (both a
  `bench_compare.py` run for ranking accuracy and a manual check of
  `--diff` output quality, which the recall benchmarks don't cover at
  all). Flagged for a future round rather than attempted under this
  loop's risk budget — see
  [`2026-07-20-probe-anchored-windowing-plan.md`](2026-07-20-probe-anchored-windowing-plan.md)
  for the detailed plan.

---

## Lessons for future optimisation work

1. **`test_accuracy.py`'s MUST_HAVE subset (18 well-known licenses, 0%/1%
   distortion, Top-1/Top-5 only) is a fast smoke test, not a substitute
   for a full benchmark.** It is intentionally narrow — common licenses,
   light distortion, shallow ranks — so it will not exercise paths that
   only matter under heavy distortion or deep in the ranking. Any change
   to *how a score is computed* (not just retrieval, caching, or I/O)
   needs either a full `bench_compare.py` run or, at minimum, a targeted
   check against the heaviest-distortion tier and mixed-content fixtures
   before being trusted — the same categories that caught the
   `score_cutoff` regression here.
2. **"Provably identical for the winning candidate" is not "provably
   identical overall."** A change can be exact for whichever candidate
   ends up ranked #1 and still corrupt `Recall@N` for `N > 1`, if it
   changes the *relative order of the losers* — which matters whenever
   the true match isn't a clean winner (heavy distortion, partial/mixed
   content) and multiple candidates end up tied on an approximated value.
3. A full corpus run remains the deciding check for anything touching
   `similarity.py`'s scoring path, matching the precedent set throughout
   this project's history (see PR #19, PR #21). SQLite-level changes
   (indexes, pragmas, caching of static data) are a different risk class
   — they can only change *how fast* a result is computed, never *what*
   the result is — and a full `pytest` pass plus reasoning about the
   change is sufficient for those.

---

## Verification summary

Final state after keeping items 1–5 and reverting the `score_cutoff`
change:

| Check | Result |
|---|---|
| `pylint src/licenseid` | 10.00/10 |
| `ruff check src tests` | clean |
| `mypy src tests` (strict) | 0 issues, 21 files |
| `pytest tests` | 50 passed, 2 skipped |
| Targeted 675-fixture check (20% distortion + mixed) vs `main` | within 0.18pp — noise level |
| CLI cold-start (`licenseid match`) | ~125ms → ~31ms |
