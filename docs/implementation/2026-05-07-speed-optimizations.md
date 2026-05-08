---
title: "Speed optimisations — plan"
date: 2026-05-07
status: planned
---

# Speed optimisation plan — 7 May 2026

This document outlines three coordinated optimisations targeting the
matching pipeline's wall-time bottlenecks. Each optimisation is
independent and can be implemented and benchmarked in isolation.

The current pipeline (as of `20260507T120849Z`) has a wall-time of
approximately 13,333 s across 59,738 queries (~0.22 s per query). The
targeted goal is sub-100 ms per query for full-text (type-4) inputs.

---

## Background — current bottlenecks

The pipeline processes each query through four layers:

1. **Tier 0 / 0.5** — short-text shortcut and marker detection. Fast
   (Python regex, no DB). Bottleneck: unconditional `normalize_text()`
   call and `detector.detect()` regex sweeps for every input.

2. **Tier 1 — FTS5 retrieval** (`search_candidates`). Calls
   `normalize_text(text)` at query time, then issues a SQLite FTS5 `MATCH`
   query. Two queries (head + tail) for long inputs. The DB round-trip is
   fast; the Python normalization of the *query* is repeated per call.

3. **Tier 2 — RapidFuzz ranking** (`_rank_candidates`). For each of the
   50–75 candidates, calls `fuzz.token_sort_ratio` or
   `fuzz.partial_ratio` with long Python strings in a Python `for` loop.
   This is the primary wall-time bottleneck for long inputs (≥ 500 words).

4. **Tier 3 — Java validation** (optional, not addressed here).

The three optimisations below target bottlenecks in this order of expected
impact: Tier 2 first (discriminative fingerprints + RapidFuzz
acceleration), then Tier 1 (query normalization + generated columns).

---

## Optimisation 1 — Discriminative N-gram fingerprints

### Rationale

License variants (GPL-2.0-only vs GPL-2.0-or-later, MIT vs MIT-STK vs
MIT-enna, CC-BY-4.0 vs CC-BY-SA-4.0) differ in a small number of specific
phrases. After Tier 1 produces a candidate pool, Tier 2 currently applies
full-text fuzzy matching against all 50–75 candidates. For variant
families, several candidates have near-identical similarity scores, forcing
RapidFuzz to compare long strings before the correct one emerges.

A **discriminative n-gram fingerprint** stores the phrases uniquely
associated with each license. At reranking, the system checks whether the
query contains any of these phrases, promoting the correct candidate
immediately without a full-text fuzzy pass.

### What is a discriminative n-gram?

A 5-word sequence that occurs in exactly one (or very few) licenses in the
corpus is highly discriminative. Formally, for a corpus of licenses
$\{L_1, \ldots, L_k\}$, a 5-gram $g$ is a fingerprint of $L_i$ when:

$$\mathrm{idf}(g) = \log\frac{k}{|\{L_j : g \in L_j\}|}$$

is above a threshold (e.g., $\mathrm{idf} \geq \log(k/2)$, meaning $g$
appears in fewer than half the corpus).

The top-$N$ highest-IDF 5-grams per license are stored as its fingerprint
set. A query "hits" license $L_i$'s fingerprint if it contains at least
one of those 5-grams.

### Changes required

#### Database schema — new table `license_fingerprints`

```sql
CREATE TABLE IF NOT EXISTS license_fingerprints (
    license_id  TEXT NOT NULL,
    ngram       TEXT NOT NULL,
    idf_score   REAL NOT NULL,
    PRIMARY KEY (license_id, ngram),
    FOREIGN KEY (license_id) REFERENCES licenses(license_id)
);
CREATE INDEX IF NOT EXISTS idx_fp_ngram ON license_fingerprints(ngram);
```

Populate after all licenses are inserted, in `_update_db_records()` or a
dedicated `_compute_fingerprints()` method in `database.py`.

#### Pre-computation algorithm (`database.py`)

```python
for each license L in the corpus:
    tokens = normalize_text(L.raw_text).split()
    ngrams_L = {" ".join(tokens[i:i+5]) for i in range(len(tokens)-4)}

global_freq: dict[str, int] = Counter(ngrams for L for ngrams in ngrams_L)
k = total number of licenses

for each license L:
    fingerprints = sorted(
        [(g, log(k / global_freq[g])) for g in ngrams_L],
        key=lambda x: -x[1]
    )[:FINGERPRINT_TOP_N]  # keep top 20 per license
    insert into license_fingerprints
```

`FINGERPRINT_TOP_N = 20` is a tunable constant. Larger values increase
recall (fewer misses) at cost of more rows per license.

#### Query-time fingerprint check (`matcher.py`)

In `_rank_candidates`, after computing initial RapidFuzz similarities,
add a fingerprint boost step:

```python
# Look up which candidates have a fingerprint match in the query.
fp_hits = self.db.find_fingerprint_hits(norm_input)
# fp_hits: dict[license_id, max_idf_score]

for r in ranked:
    if r["license_id"] in fp_hits:
        r["score"] += FP_BOOST * fp_hits[r["license_id"]]
```

The `find_fingerprint_hits` method in `database.py` does a set
intersection between query 5-grams and the fingerprint index:

```python
query_ngrams = build_ngrams(norm_input, n=5)
# Use a single parameterized IN query for the ngrams.
```

#### Short-circuit before RapidFuzz (optional, Phase 2)

If a candidate has a fingerprint hit with `idf_score > HIGH_THRESHOLD`
(e.g., $\log(k)$, meaning the n-gram appears in exactly one license), skip
RapidFuzz for that candidate and assign `similarity = fp_similarity`
(a pre-computed high score). This is a Phase 2 refinement; implement only
after measuring the boost impact in Phase 1.

### SPDX expression compatibility

Fingerprints are computed per base license ID (e.g., `GPL-2.0-only`) and
per exception ID (e.g., `Classpath-exception-2.0`). When the matcher
identifies a compound expression (`GPL-2.0-only WITH
Classpath-exception-2.0`), the fingerprint table covers both components
independently. The `exceptions` table needs a parallel
`exception_fingerprints` table with the same schema.

### Expected impact

- **Top-1 recall for variant families**: fingerprint hits should break
  near-ties between `GPL-2.0-only` and `GPL-2.0-or-later`, `MIT` and
  `MIT-STK`, `CC-BY-4.0` and `CC-BY-SA-4.0`.
- **Wall time**: fingerprint lookup is a single indexed SQLite `IN` query
  over the pre-built `idx_fp_ngram` index. Expected: < 1 ms per query.
- **Storage overhead**: 20 fingerprints × 695 licenses × ~30 bytes =
  ~400 KB additional SQLite storage. Negligible.

### Risks

- 5-grams generated from very short licenses (< 5 words) will produce no
  fingerprints. Handle gracefully with a minimum-length guard.
- Licenses updated across SPDX versions may invalidate stored fingerprints.
  Fingerprints must be recomputed whenever `_update_db_records()` runs.

---

## Optimisation 2 — Pre-computed normalization and RapidFuzz acceleration

### 2a — Pre-computed normalized text (already partially done)

The `license_index.search_text` column already stores
`normalize_text(raw_text)`. The FTS5 index is built on this column.
However, `search_candidates` calls `normalize_text(text)` on the *query*
at call time, and `_rank_candidates` re-normalizes the query in the
`norm_input` parameter.

**No change is needed for query normalization** — it is already called
once per `match()` invocation at the top of the method and passed down.
The concern is whether `normalize_text` on the candidate side is redundant.
It is not: `search_text` in `CandidateMatch` is fetched directly from the
pre-normalized `license_index` column, so no re-normalization occurs.

Action: add an assertion / `# noqa` comment confirming that
`cand["search_text"]` is always the pre-normalized form, to prevent future
regressions.

### 2b — Length filter before RapidFuzz

The most impactful micro-optimization. Before calling `fuzz.ratio` on
any candidate, discard candidates whose normalized word count differs from
the query word count by more than a configurable factor.

```python
_LENGTH_RATIO_THRESHOLD = 3.0  # skip if c_len > q_len * 3 or c_len < q_len / 3

for cand in candidates:
    c_len = cand.get("word_count") or len(cand["search_text"].split())
    if q_len > 0 and c_len > 0:
        ratio = max(q_len, c_len) / min(q_len, c_len)
        if ratio > _LENGTH_RATIO_THRESHOLD and coverage_check_enabled:
            # Assign minimum similarity without calling RapidFuzz
            ranked.append(InternalMatch(..., similarity=0.0, ...))
            continue
    # ... full fuzzy match
```

This is already partially implemented via the `coverage` signal in scoring,
but the RapidFuzz call still happens. Moving the guard before the call
eliminates the expensive string comparison entirely for impossible
candidates.

Tuning: `_LENGTH_RATIO_THRESHOLD = 3.0` is conservative. A 500-word query
will skip candidates with < 167 or > 1500 words. This is safe for
type-4/type-5 inputs but must be disabled or relaxed for type-3 (short
fragments against the full corpus).

### 2c — RapidFuzz `score_cutoff`

`process.extract` accepts a `score_cutoff` parameter; `fuzz.ratio` (and
related scorers) abort early when the intermediate score cannot reach the
cutoff. This is implemented in C++ and has no Python overhead.

```python
# Current (no cutoff — scores everyone):
similarity = fuzz.token_sort_ratio(norm_input, search_text) / 100.0

# Proposed (early abort below 40%):
raw = fuzz.token_sort_ratio(
    norm_input, search_text, score_cutoff=40
)
similarity = raw / 100.0 if raw else 0.0
```

The cutoff of 40 % is conservative. Based on the benchmark data, any
candidate scoring below 40 % on `token_sort_ratio` cannot reach the
ranking threshold and will be discarded in scoring. Adjust after
measuring the impact on recall.

### 2d — RapidFuzz processor (C++ lowercasing)

Where `fuzz.*` functions are called without a `processor`, add
`processor=None` explicitly (inputs are already normalized) to avoid
RapidFuzz's default processor accidentally re-applying transformations.
This is a correctness fix as much as a speed fix: the current code passes
pre-normalized strings but does not explicitly opt out of the default
processor, which does its own lowercasing. In practice the strings are
already lowercase, so it is a no-op — but the explicit `processor=None`
removes a Python function call overhead per comparison.

### 2e — Batch processing with `process.extract`

Replace the Python `for cand in candidates` loop with a single
`process.extract` call when all candidates share the same scorer and
processor:

```python
from rapidfuzz import process, utils

candidate_map = {
    cand["license_id"]: cand["search_text"]
    for cand in candidates
    if cand.get("search_text")
}

results = process.extract(
    norm_input,
    candidate_map,
    scorer=fuzz.token_sort_ratio,
    processor=None,        # already normalized
    score_cutoff=40,       # skip obvious misses in C++
    limit=None,            # return all above cutoff
)
# results: list of (value, score, key)
```

This hands the inner loop entirely to RapidFuzz's C++ backend. For 75
candidates of ~500 words each, this is expected to be 5–10× faster than
the Python loop.

Caveat: the current code has branching logic (switching between
`token_sort_ratio` and `partial_ratio` depending on length). The batch
approach requires factoring out this branching before the `process.extract`
call or using a custom scorer wrapper.

### SPDX expression compatibility

Normalization is applied per-token (each license ID in the expression is
matched independently), so these optimizations apply directly.

### Expected impact

- Length filter: expected to skip 30–60 % of candidates for type-4 inputs
  (long full-text queries against a 695-license corpus have very few
  plausible length matches).
- `score_cutoff`: expected 2–5× speedup on RapidFuzz calls.
- Batch `process.extract`: expected 5–10× speedup on Tier 2.
- Combined: projected Tier 2 time reduction from ~0.18 s/query to
  < 0.05 s/query for type-4 inputs.

### Risks

- `score_cutoff` too high may silently drop correct candidates that score
  below the cutoff due to partial-text inputs. Validate on type-3 (short
  fragments) before deploying.
- Batch `process.extract` requires careful scorer selection — the
  branching between `token_sort_ratio` and `partial_ratio` encodes
  important heuristics. Refactor incrementally.

---

## Optimisation 3 — SQLite generated columns

### Rationale

SQLite generated columns (available since SQLite 3.31, 2020-01-22) define
a column whose value is automatically derived from other columns at insert
or update time. `STORED` generated columns are computed at write time and
stored on disk — reads are free.

Two derived values are currently computed in Python that could instead live
in the database schema:

1. **`char_count`**: the character length of `search_text`. Used for
   length filtering in Optimisation 2b. Currently computed as
   `len(search_text)` or via `word_count`.

2. **`word_count`**: already stored as an explicit column — no change
   needed. (Included here for completeness; the generated column approach
   would compute it from `search_text` automatically, eliminating the
   manual Python calculation in `_build_db_from_tarball`.)

### Proposed schema additions

```sql
ALTER TABLE licenses
    ADD COLUMN char_count INTEGER
        GENERATED ALWAYS AS (
            LENGTH(search_text_col)
        ) STORED;
```

Limitation: the full `normalize_text()` function uses Python-level regex
and BeautifulSoup, which SQLite's built-in functions cannot replicate. The
generated column approach is therefore limited to *simple* derived values
(lengths, checksums via `HEX(SUBSTR(...))`) that are computable from SQL
built-ins alone.

For the full normalization pipeline, the `search_text` column in
`license_index` remains the canonical pre-normalized storage, populated
by Python at DB build time. Generated columns cannot replace this.

### What is feasible

| Derived value | SQL expression | Feasibility |
|---|---|---|
| `char_count` | `LENGTH(search_text)` | ✅ simple, useful for length filter |
| `word_count` | Not directly in SQL | ❌ requires Python (split on spaces) |
| `normalized_head_100` | `SUBSTR(search_text, 1, 100)` | ✅ character-level, approximate |
| Full `normalize_text()` | Regex + HTML parse | ❌ requires Python |

### Recommended generated column

Add `char_count` to the `licenses` table (or `license_index`):

```sql
-- In _init_db(), add after existing columns:
char_count INTEGER GENERATED ALWAYS AS (
    LENGTH(search_text)
) STORED
```

Then update `search_candidates` to join and return `char_count` alongside
`word_count`, and use it in the length filter (Optimisation 2b) without
an additional Python `len()` call.

Note: `license_index` is a virtual FTS5 table and does not support
generated columns. The `char_count` column must live in the `licenses`
base table, with `license_index` joining to it (as the `search_candidates`
query already does).

### SQLite mmap pragma

Add `PRAGMA mmap_size = 268435456;` (256 MB) to `_connect()` or in
`_init_db()`. For a database smaller than 256 MB, this makes all FTS5
reads happen at memory speed after the first access.

```python
def _connect(self) -> sqlite3.Connection:
    conn = sqlite3.connect(str(self.db_path), uri=self.use_uri)
    conn.execute("PRAGMA mmap_size = 268435456")
    return conn
```

### SPDX expression compatibility

Schema changes (adding columns) are transparent to the expression parser
and matching logic. All existing queries remain valid.

### Expected impact

- `char_count` generated column: eliminates ~75 Python `len()` calls per
  query (one per candidate). Minor absolute saving (< 0.1 ms) but improves
  code clarity.
- `mmap_size` pragma: potentially significant for cold-start queries where
  the SQLite page cache is empty. On repeated queries (warm cache) the
  effect is negligible.

### Risks

- Generated columns require SQLite ≥ 3.31. Python 3.10's bundled SQLite is
  3.37+ on most platforms. Add a version guard in `_init_db()` with a
  fallback to a plain computed column at insert time.
- Schema migrations: the current `_init_db()` uses `CREATE TABLE IF NOT
  EXISTS`, which does not alter existing tables. A migration step
  (`ALTER TABLE ... ADD COLUMN`) is needed for databases created before
  this change. Since the project is pre-release (no backward compatibility
  guarantee), `clear_cache()` + rebuild is acceptable.

---

## Implementation order and dependencies

| Phase | Optimisation | File(s) | Prerequisite |
|---|---|---|---|
| 1 | 2b — length filter | `matcher.py` | None |
| 1 | 2c — `score_cutoff` | `matcher.py` | None |
| 1 | 2d — `processor=None` | `matcher.py` | None |
| 2 | 3 — `mmap_size` pragma | `database.py` | None |
| 2 | 3 — `char_count` generated col | `database.py` | Phase 1 (use in filter) |
| 3 | 2e — batch `process.extract` | `matcher.py` | Phase 1 (validate cutoff) |
| 4 | 1 — fingerprint table + compute | `database.py` | Phase 2 (schema stable) |
| 4 | 1 — fingerprint boost in ranker | `matcher.py` | Phase 4 (table exists) |

Start with Phase 1 (zero-risk, no schema changes) to establish a new
performance baseline before moving to the fingerprint work.

---

## Benchmark subset for fast iteration

To reduce iteration time, the full-coverage benchmark (695 short + 555
long fixtures) is replaced with a 70-fixture subset for each of
`license-text-short` and `license-text-long`. The subset is selected using
stratified sampling:

1. **Family stratum**: the leading alpha component of the license ID
   (e.g., `GPL`, `MIT`, `CC`, `BSD`).
2. **Length stratum**: word count quintile (< 75, 75–175, 175–375,
   375–1963, > 1963 words for long fixtures; proportionally scaled for
   short).
3. **Selection**: within each (family, length) cell, pick one fixture
   deterministically (by sorted `license_id`). Over-represented families
   (CC: 55, BSD: 36) are down-sampled proportionally; under-represented
   families get at least one slot if a fixture exists.
4. **Hard-case pinning**: always include at least one fixture from each of
   GPL, LGPL, AGPL, CC-BY, CC-BY-SA, MIT (for variant disambiguation).

The selection function `_select_benchmark_subset(files, n)` in
`bench_single.py` implements this strategy deterministically (no random
seed needed).

Pass `--subset 70` to either script to activate a 70-fixture subset:

```bash
# Single-branch run with 70-fixture subset:
python benchmarks/bench_single.py src license-marker perf_eval \
    "$(date -u +%Y%m%dT%H%M%SZ)" --subset 70

# Comparison run with 70-fixture subset:
python benchmarks/bench_compare.py --subset 70

# Full-coverage run (omit --subset):
python benchmarks/bench_compare.py
```

**Expected speed-up**: 70/695 ≈ 10× faster for type-3, 70/555 ≈ 8× for
type-4. A full iteration cycle (modify → benchmark → compare) should
complete in under 3 minutes on a modern laptop, vs 30+ minutes for the
full run.

**Caveat**: the subset does not replace the full-coverage benchmark for
release validation. Run the full benchmark before merging.

---

## Reference: SPDX License Expression compatibility

All optimisations operate on individual license IDs resolved from an
expression. The matching pipeline processes one expression component at a
time (see `cli.py` for expression parsing). The fingerprint table covers
both license IDs and exception IDs (`Classpath-exception-2.0`,
`Font-exception-2.0`, etc.). The `WITH` operator in expressions
(`GPL-2.0-only WITH Classpath-exception-2.0`) requires independent lookups
for both components; the fingerprint boost applies to each independently.

SPDX expression operators (`AND`, `OR`, `WITH`) and the `+` suffix are
handled upstream of the matching layer and do not affect the schema or
scoring logic described here.

See the SPDX 3.1 specification for expression grammar:
<https://spdx.github.io/spdx-spec/v3.1-dev/annexes/spdx-license-expressions/>
