---
Created: 2026-10-05
Last-Modified: 2026-10-05
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Results and technical findings

Accuracy and speed numbers, and the technical findings behind them. Extracted
from the repository's docs, benchmarks and code comments.
See [README.md](README.md) for the index, method and caveats.

Source abbreviations (all paths relative to the repo root):

- `IMPL/` = `working-docs/implementation/`; `DES/` = `working-docs/design/`
- `TDR` = `IMPL/tech-debt-resolved.md`; `ROAD` = `DES/tech-debt-roadmap.md`;
  `CPLX` = `DES/complexity-and-file-size-roadmap.md`
- `R2` = `IMPL/speed-optimizations-round-2.md`; `R1` =
  `IMPL/speed-optimizations.md`
- `OPT` = `DES/optimization-recommendation.md`; `THR` =
  `IMPL/threshold-optimizations.md`
- `ACC` = `IMPL/accuracy-optimizations.md`; `GATE` =
  `IMPL/database-readiness-gate.md`
- `EXPR` = `IMPL/spdx-expression-reading.md`; `FETCH` =
  `IMPL/data-fetching-and-caching.md`
- `BENCH` = `benchmarks/summary.md`; `BREADME` = `benchmarks/README.md`
- `FIX` = `tests/fixtures/README.md`; `AGENTS` = `AGENTS.md` (`CLAUDE.md` is a
  symlink to it)
- `L<n>` = line number in that file.

A few facts are taken from source code comments (marked `src/...`) where the
docs refer to them but do not quote the constant. Remarks marked
**[observation]** are the compiling agent's, not claims made in the repo.

## 2. Quantitative results

### 2.1 Benchmark datasets

<!-- markdownlint-capture -->
<!-- markdownlint-disable MD013 -->

| Type | Content | Size | Source |
| --- | --- | --- | --- |
| 1 IDs | verbatim, deprecated, space, casing, punct, truncated ("distorted") | n=306 queries | `FIX` §1; `BENCH` L197 |
| 2 names | verbatim, space, casing, punct, lexical distortion | n=295 (59 licences × 5) | `FIX` §2; `BENCH` L206, L61-100 |
| 3 short text | head/tail/head+tail slices at 300, 500, 700, 1000, 1500, 2000, 3000 **characters** | 695 files; n=2,085 in `BENCH` (3 head sizes × 695) | `FIX` §3; `BENCH` L215 |
| 4 long text | verbatim + distortion at 1, 2, 5, 10, 20% (typos, foreign text, dropped paragraphs, whitespace) | 555 files; n=3,330 (555 × 6) | `FIX` §4; `BENCH` L224 |
| 5 mixed content | generated source headers, READMEs, manifests, HTML; <15% contain the exact ID | 183 files | `FIX` §5; `BENCH` L233 |
| 5.1 curated | hand-crafted mixed content | 26 files (ls count) | `BREADME` L55 |

<!-- markdownlint-restore -->

- Full-coverage run `20260507T120849Z`: 695 licences, 59,738 queries
  (`OPT` L26-27). Previous runs used a 60-licence development subset
  (`OPT` L105).
- Distortion level 20 is "character-level, breaks word tokens" (`BREADME` L53).
- Mixed-content templates are "LLM-derived", based on an analysis giving source
  headers ~60%, READMEs ~20%, manifests ~10%, docs ~5%, other ~5%; lexical
  styles colloquial 40%, canonical names 30%, SPDX IDs 20%, URLs 10%
  (`tests/fixtures/mixed-content-analysis.md` L9-15, L61-73).
- "1,405 fixture files" used for before/after top-3 comparisons (`EXPR` L90-91;
  `TDR` L359).
- Benchmark harness: `bench_compare.py` builds a pristine `git worktree` of
  `main`, runs `bench_single.py` per tree in subprocesses (no import-cache
  cross-contamination); `InstrumentedMatcher` records the resolving tier;
  wall time via `perf_counter`, peak memory via `tracemalloc`; full run ~2 h
  (`BREADME` L21-44). Earlier a full run was ~50 min (`R2` L253-254).
- Stratified 70-fixture subset for fast iteration (family × length quintile,
  hard-case pinning for GPL, LGPL, AGPL, CC-BY, CC-BY-SA, MIT), deterministic,
  no seed; expected ~10x faster; "does not replace the full-coverage
  benchmark" (`R1` L452-495).
- Unit-level accuracy test: `test_accuracy.py` MUST_HAVE subset = 18
  well-known licences at 0%/1% character distortion, Top-1/Top-5 (`R2` L42-44).

### 2.2 Accuracy: full-coverage run `20260507T120849Z` (`OPT` L36-50)

Recall@1, `license-marker` branch vs `main`:

| Type | license-marker | main | Δ |
| --- | --- | --- | --- |
| 1 IDs | 78.1% | 78.1% | 0 |
| 2 names | 90.2% | 86.4% | +3.8 pp |
| 2 `name_casing` | 96.6% | 79.7% | +16.9 pp |
| 3 `head_300` | 85.9% | 91.4% | −5.5 pp (fixed later) |
| 3 `head_500` | 93.5% | 92.4% | +1.1 pp |
| 3 `head_800` (peak) | 94.5% | 93.2% | +1.3 pp |
| 3 `tail_300` | 65.8% | 63.7% | +2.1 pp |
| 3 `tail_2000` | 87.1% | 83.7% | +3.4 pp |
| 4 verbatim | 94.2% | 92.4% | +1.8 pp |
| 4 5% distortion | 69.7% | 71.2% | −1.5 pp |
| 4 20% distortion | 48.5% | 44.5% | +4.0 pp |
| 5 mixed content | 74.9% | 19.7% | **+55.2 pp** |
| 5.1 curated | 95.8% | 25.0% | **+70.8 pp** |

Wall time 13,333 s (license-marker) vs 8,199 s (main), +63%, attributed to
12x more Type 3 queries (695 × 16 slices vs 60 × 16) (`OPT` L52-54).
≈0.22 s per query; goal was sub-100 ms for full texts (`R1` L23-25).

### 2.3 Accuracy: most recent recorded run `20260720T082350Z` (`BENCH`)

Baseline column (before the rejected `score_cutoff` change), Recall@1 / @5 /
@50:

- Type 1: `id_verbatim` 100/100/100; `id_space` 100; `id_punct`
  86.67/90.00/91.67;
  `id_casing` 80.00 flat; `id_deprecated` 0.00 / 33.33 / 33.33;
  `id_distorted` 30.00/56.67/63.33 (L9-56).
- Type 2: `name_verbatim` 100; `name_space` 100; `name_casing` 96.61 flat;
  `name_punct` 94.92/94.92/100; `name_distored` 55.93/86.44/91.53 (L61-100).
- Type 3: `head_300` 92.09/98.42/99.71; `head_500` 93.53/98.99/99.86;
  `head_800` 94.53/99.28/99.86 (L105-128).
- Type 4: verbatim 94.23/98.92/99.46; 1% 94.05/98.92/99.46; 2%
  94.23/98.74/99.28;
  5% 71.71/83.96/98.20; 10% 60.72/76.94/95.14; 20% 50.09/64.68/78.92 (L133-180).
- Type 5 mixed: 60.66/79.78/86.89 (L185-192).
- Tier attribution (n; resolved-by share): Type 1 n=306: Tier 0 75.49%,
  Tier 1 10.13%, Tier 2 0.33%, missed 14.05%. Type 2 n=295: Tier 0 86.78%,
  missed 2.37%. Type 3 n=2,085: Tier 0.5 14.15%, Tier 1 85.61%, missed 0.19%.
  Type 4 n=3,330: Tier 0.5 4.71%, Tier 1 91.26%, missed 4.02%. Type 5 n=183:
  Tier 0 13.66%, Tier 0.5 49.73%, Tier 1 21.86%, Tier 2 2.73%, missed 12.02%
  (L196-239).
- Global: recall 96.58%; "precision" 1.85%; wall time 1,385.0 s vs 1,298.4 s;
  throughput 4.5 vs 4.8 q/s; peak memory 5.3 vs 8.6 MB (L242-249).

Earlier per-tier analysis (60-licence subset, `20260505T095558Z`, `OPT`
L113-207): Tier 0.5 resolved 16.07% of Type 3 (439 inputs), 4.74% of Type 4
(158), 49.73% of Type 5 (91) with +46.45 pp R@1 on Type 5; pool-recall
ceilings: Type 4 verbatim/1%/2% 98%+, 20% distortion 68%, tail-only
(300-500 chars) 76-78%; ranking headroom (R@50 − R@1): `head_700_tail_700`
38.6 pp, `head_2500_tail_500` 41.5 pp, Type 4 verbatim 5.0 pp, 20% distortion
24.9 pp. Projected global recall with all fixes 89.98% → ~92-93% (L262).

### 2.4 Threshold tuning and regressions found

- **Tier 0 threshold 60 → 30 words** (`THR`): at 300 chars (~50 words),
  top-1 85.9% vs 91.4% on `main`, a loss of 38/695 fixtures; tier breakdown
  `head_300`: tier05 93 vs 0, tier1 599 vs 682, missed 2 vs 12, top-1 597 vs
  635 (L20-32). Cause: 50-word heads hit the name/ID matcher, which returned
  the generic parent (`MIT-STK → MIT`, `MIT-enna → NONE`,
  `CC-BY-NC-SA-2.0-DE → CC-BY-NC-SA-2.0`) (L34-41). Projected ~91% after fix
  (L66); `BENCH` later shows 92.09% (L105).
- Head-length plateau (`THR` L85-96): 300 chars ~85.9→~91%; 500 93.5%;
  700 94.2%; 800 94.5% (peak); 1000+ 94.4% (flat); optimum 500-800 chars
  (~80-133 words).
- Marker scanning yield on short inputs: tier05 fired in 2 of 695 `tail_300`
  queries; ~11,000 Type 3 snippets scanned regardless (`THR` L43-49).
- **Dual head+tail FTS5 query** (`ACC` L139-146, 695 licences, in-memory DB,
  `20260507T060233Z`): head top-50 recall 98.7% → 99.9% (+1.2 pp); tail top-1
  39-46% → 52-57% (+10-13 pp); union top-50 (h700+t700) 99.4% → 100.0%.
- **Tie-breaker trade-off** (`ACC` L189-198; `TDR` L431-441): before/after over
  fixtures + 160 synthetic headers (4,741 results): 344 changed; 184 fixture
  results, 182 of them GFDL slices/distortions moving `-only`→`-or-later`
  (GFDL's own text says "or any later version"); 32 synthetic headers changed
  top answer for "or newer". Of 3,249 licence-text results, correct top
  answers 1,949 → 1,948 (30 lost, 29 gained).
- **Early accuracy** (`IMPL/performance-optimization.md` L36-44): subset test
  (38 matches) 20 s (from minutes); full accuracy test (3,330 matches) ~5 min
  (from 2+ hours); Top-5 100% at 0%/1% distortion on core licences; Top-1 ~94%,
  limited by identical texts (GPL-2.0-only vs -or-later).

### 2.5 Speed results (before → after, with units)

<!-- markdownlint-capture -->
<!-- markdownlint-disable MD013 -->

| Change | Before | After | Source |
| --- | --- | --- | --- |
| Lazy imports of `requests` (~60 ms) and `bs4` (~32 ms) | CLI cold start ~125 ms | ~31 ms (≈4x) | `R2` L109-130 |
| Index `licenses(name COLLATE NOCASE)` | `get_license_by_name` 0.676 s / 1,317 calls (195-query workload); `SCAN` | 0.220 s (~3x); `SEARCH USING INDEX` | `R2` L57-81 |
| `PRAGMA mmap_size=268435456` | 0.51 ms per connection+query | 0.33 ms (~35%) | `R2` L165-186 |
| Shared connection per `match()` | 4,000 distinct `LicenseRef-*` tags 9.0 s | 1.85 s | `TDR` L134-143 |
| `TableCache` of IDs | 1.73 s (1.2 s in two unindexable queries) | 0.52 s; 1 query per tag instead of 5 | `TDR` L56-63 |
| Tier 0 `score_cutoff` | 200,000-char word 2.7 s | 0.3 s | `TDR` L150-158 |
| Probe gate + char limits (blob input) | 27 words + one 2,000-char token 5 s; 5,000 chars ~60 s | a few ms per candidate | `TDR` L290-312 |
| Rejected `score_cutoff=60` on `partial_ratio_alignment` | 66 ms | 11 ms (~6x), reverted | `R2` L212-217 |
| Probe alignment mode vs score-only | 65.62 ms | 65.75 ms (no overhead) | `DES/probe-anchored-windowing-plan.md` L68-69 |

<!-- markdownlint-restore -->

CHANGELOG summary: thousands of distinct tags "over 20× faster"; one very long
word "about 9× faster" (`CHANGELOG.md` L122-123).

RapidFuzz cost data points:

- Per candidate vs licence of 18,000 chars: query 700 chars 7 ms; 2,150 chars
  124 ms; 4,000 chars 758 ms (`src/licenseid/similarity.py` L30-33).
- Probe cost per candidate: 15 ms at 500 chars, 43 ms at 600, 136 ms at 1,000
  → `PROBE_MAX_CHARS` = 500 (`TDR` L306-308).
- `fragment_similarity` cost scales with query length, not candidate length:
  q=80 words, cand=7,244 → ~2 ms; q=300, cand=464..7,244 → ~47-67 ms
  (`DES/probe-anchored-windowing-plan.md` L37-43). It is 85%+ of `match()`
  time on realistic workloads (`R2` L200-201).
- Remaining slow cases: 3,000-char Apache-2.0 slice 9 s on the real DB (many
  similar licences pass the probe); 200 words of Apache-2.0 among 120 random
  25-char tokens (4,426 chars) 134 s, 141 candidates × ~1 s (`ROAD` item 11,
  L305-313); unprobed query just under 1,500 chars ~1 s (`TDR` L317-319).
- Other measured costs: `configparser`/TOML regex 0.024 ms and 0.11 ms on a
  5,600-word text (`R2` L268-271); `py_spdx_license` tokenizer 0.11 s at
  100,000 chars, 0.35 s at 200,000, 6.8 s at 1,000,000; `create_ast`
  `pop(0)` 0.18 s at 10,000 operands, 1.05 s at 40,000 (`ROAD` item 26,
  L96-101); loose `License:` reader 9 s on 10,000 lines; `configparser` 2 s
  on 100,000 non-`key=value` lines on 3.10 vs 0.3 s on 3.14 (`ROAD` item 23).
- Parser cost budget `_MAX_PARSE_COST` = 10^9 (sum of squared token lengths,
  ≈8 ms, one token of 31,622 chars); a 256-char token cap refused real
  `LicenseRef-*` values (`ROAD` item 26, L84-92).

### 2.6 The rejected `score_cutoff` experiment (`R2` L194-256; `BENCH`)

- Byte-identical for every candidate clearing the cutoff (0/80 mismatches in
  A/B). But below the cutoff RapidFuzz returns `None`, flattened to 0.0,
  destroying the relative order of losers; under heavy distortion the true
  match is often a sub-60 candidate.
- Full benchmark deltas: 5% R@1 71.71% → 71.71% (0); 10% R@30 91.17% →
  89.73% (−1.44 pp); **20% R@30 75.86% → 67.93% (−7.93 pp)**; mixed R@10
  80.87% → 75.41% (−5.46 pp) (`R2` L238-243). Also 20% R@1 50.09 → 45.23
  (−4.86 pp) (`BENCH` L165).
- The gradient across distortion levels was the diagnostic signature.
  Revert confirmed on a targeted 675-fixture check (555 heavy-distortion +
  120 mixed) within 0.18 pp of `main` (≈1 fixture, SQLite tie-order noise).
- The pytest accuracy subset passed identically before and after the
  regression.

### 2.7 Other numbers

- Coverage of `cli.py`: 66-75% → 100% lines and branches (`TDR` L521-524).
- Test counts after the structured-format refactor: `test_spdx_source.py`
  3 → 41 tests; `test_spdx_source_cache.py` 39; `test_database_update.py` 22;
  `test_fingerprint.py` 4 (`CPLX` L275-282). `test_get_candidates.py` 16 new
  tests (`CPLX` L209). At round 2: pytest 50 passed, 2 skipped; mypy strict 0
  issues on 21 files (`R2` L331-334). Repo now has 60 entries in `tests/`.
- SPDX 3.28.0 tarball: 13,018 files, 19 directories, no links (`FETCH` L90-93);
  `popularity.csv` covers 29 licences (`FETCH` L93). On-disk DB ~46 MB
  (`R2` L177).
- Readiness probe `_BUSY_WAIT` = 1.0 s vs SQLite default 5 s (`GATE` L72-75).
- CLI matrix: ~1,200 cells, five shells, two interpreters, ~3 minutes
  (`tools/cli_matrix/README.md` L56-57); baseline file 19 lines.

---

## 3. Interesting technical findings

### 3.1 Algorithmic cost and performance traps

- **RapidFuzz cost is in characters, not words.** Guards counted words (probe
  only for 120-499 words; ≥500 words fell back to `token_sort_ratio`), so a
  blob of few words and many characters (long token, base64) took the full
  alignment scan on every candidate (`TDR` L290-298; `AGENTS` L379-391).
  Base64 is split at `+` and `/` by normalisation, so dropping long tokens
  would not have sufficed (`TDR` L297-299).
- **CJK breaks per-word limits.** A first fix (score queries of >16 chars per
  word with `token_sort_ratio`) lost Japanese text: a 1,570-char slice of
  CC-BY-SA-2.1-JP (104 words) fell from a certain match to 0.5. "Characters
  per word says nothing about a blob." Final design: queries ≥1,500 chars
  always get a probe (cut by characters if <120 words); probe ≤500 chars; scan
  ≤6,000 chars else `token_sort_ratio`; `alignment_affordable` is the one judge
  (`TDR` L299-310). No fixture reaches the limits (max 1,427 chars unprobed,
  5,478 probed); trimming the 16 fixture probes longer than 500 chars (all
  Japanese or Chinese) keeps every top answer; only ranks 2-3 at scores near
  0.11 change (`TDR` L313-317). Warning: "A limit that clears every fixture
  proves little" — sweep real texts (CJK included) at several offsets
  (`AGENTS` L383-391).
- **Quadratic regex backtracking**: `\s+` followed by a class that also
  matches whitespace (`\s+[\s/*#]*`) is quadratic on a run of spaces: 5 s at
  32,000 spaces; write `\s[\s/*#]*`; time every prose regex on
  `"x" + " " * N` (`AGENTS` L311-315).
- **Each fix added the next quadratic path**: three review rounds in a row
  found a slowdown introduced by the previous fix (re-slicing per bracket
  `s = s[1:-1]`, one pass over the whole line per tag) (`EXPR` L62-66).
  Minified lines with thousands of tags made per-tag rest-of-line reading
  quadratic, so a tag value ends at line break or next tag (`EXPR` L51-53).
- **Benchmark artefacts**: a dedupe made 4,000 identical tags take 0.05 s
  while 4,000 distinct ones took 8.7 s vs 6.9 s on `main`; a CHANGELOG line
  once claimed a fix for a 36 s slowdown that existed only on the branch;
  unbalanced deep brackets fail early and prove nothing — a balanced
  40,000-deep nest found two quadratic loops (`EXPR` L67-72).
- **Python-version-dependent behaviour**: a deep-bracket test took ~1 s
  locally, 5.3 s on CI's Python 3.10 (5 s limit), passed on 3.14
  (`EXPR` L73-77). `py_spdx_license` builds its AST recursively with no depth
  guard: a 400-term `AND` of `LicenseRef-*` raises RecursionError on 3.10
  (no match) and parses on 3.14 (match) — same file, different answer on two
  supported versions (`ROAD` item 19, L420-426). `configparser` on 3.10 scans
  a whitespace run once per key character: 50,000 spaces after `license` took
  9 s (`TDR` L256-258).
- **CPython string append**: `t.value += c` on an attribute cannot append in
  place, so tokenizing is quadratic (`ROAD` L95-98).

### 3.2 SQLite findings

- **NOCASE folds ASCII only**; the ID map uses `dbcache.fold_case` because
  `str.lower` would turn the KELVIN SIGN (U+212A) into `k` (`TDR` L64-65).
- `license_id = ? COLLATE NOCASE` cannot seek a binary primary key; the FTS5
  `UNINDEXED` column cannot be searched by index (`TDR` L57-61).
  `LIKE … ESCAPE` disables SQLite's prefix-LIKE index optimisation (`R2`
  L262-267).
- **Shared-cache in-memory DB vanishes** when its last connection closes, and
  CPython frees an unreferenced `LicenseDatabase` (and its keep-alive
  connection) immediately; a test helper must open its own keep-alive
  connection first. Latent until fixtures were consolidated — the inline
  versions avoided it by incidental frame-reference timing (`CPLX` L238-250;
  `AGENTS` L227-230).
- **Named pipe hangs**: `open(O_RDONLY)` on a FIFO blocks for ever — no output,
  no exit code, no traceback; "the only failure mode in the PR that no test
  could have caught by assertion — the test would have hung too"; check
  `S_ISREG`/`S_ISDIR` before opening (`GATE` L42-47).
- **Path/URI spellings**: `x`, `x/`, `x/.` are one file; `file:`, `file://`,
  `file://localhost/` likewise; an `endswith("/")` patch failed at `/.`;
  normalise once in `_os_file` (`GATE` L48-54). `file::memory:NAME` is a file
  on disk (only `mode=memory` and exact `file::memory:` are memory); treating
  the prefix as memory made `--clear-cache` do nothing and a read create a
  file (`GATE` L55-58). `?vfs=` needs two notions of path: what the OS opens vs
  what licenseid may delete (`GATE` L59-64). `file://localhost/abs.db` passes
  the gate but `Path()` collapses `//` (`ROAD` item 10).
- **WAL and read-only**: `mode=ro` cannot create `-shm` or replay a hot
  journal; `immutable=1` was tried and dropped because it disables locking, so
  a read during `update` could see a torn file (`GATE` L65-71; `TDR` L481-484).
- **Foreign schemas**: table names `licenses`/`db_metadata` collide with seat
  inventories or asset registers; classifying such a file as `empty` sent the
  user to `update`, which wrote licenseid's schema into it; also check that
  `license_index` is actually FTS5 (`GATE` L76-83). A fuzz run found only
  root-page swaps of `licenses` (`TDR` L486-489).
- `database is locked` means "ask again later", mapped to `unknown`
  (`GATE` L72-75).
- `mmap_size` 256 MB is a virtual mapping, a documented no-op on in-memory
  URIs (`R2` L182-186).
- Cache staleness: the "static" names table was not static — a rebuild by the
  same or another process kept the old list (`R2` L156-159).

### 3.3 SPDX semantics findings

- `-only` vs `-or-later` and GFDL: licence bodies are identical, so only the
  grant can decide; GFDL's own text contains "or any later version", so
  slices of it resolve `-or-later` — "nothing can tell the variants apart"
  (`ACC` L189-195).
- Short-phrase false certainty: `license identifier` or an empty
  `SPDX-License-Identifier:` answers `CAL-1.0` at 1.0 and `is-osi` says yes;
  `BSD` answers `0BSD`, `the` answers `MirOS`, a README "json" code fence
  answers the `JSON` licence (`ROAD` item 28).
- A missing file name passed as argument is matched as text: `licenseid match
  LICENSE.txt` with no such file answers `APL-1.0` at 1, exit 0 (`ROAD` item
  32, Priority 24 — highest open).
- `GPL 2.0+` in prose loses its "+" in normalisation and answers
  `GPL-2.0-only`; reading "+" from prose is a guess (`C++`) (`ROAD` item 30).
- Non-ASCII in tag values cut short: `LicenseRef-café` → `LicenseRef-caf`,
  `MIT-ü` → `MIT` (`ROAD` item 33).
- Flags for expressions: `is_spdx` true for any `LicenseRef-*`;
  `MIT OR Apache-2.0` reports OSI/FSF false; spaces in `LICENSE_ID=` break
  `awk` (`ROAD` item 34).
- A licence text repeated three times (Apache-2.0 ×3) answers `BSD-4-Clause`
  at 0.9025 with similarity 0.0968, coverage 20.08 (`ROAD` item 35).
- "Exact" is stricter than SPDX matching: a filled-in copyright line or title
  makes a real licence file not exact, whereas the guidelines allow
  replaceable/omittable text to differ (`ROAD` item 31; `README.md` §4).
- GPL appendix heuristics: the canonical GPL-2.0 appendix places the
  `<one line to give the program's name...>` placeholder *before* the grant,
  so forward-only suppression never fired on real boilerplate; a
  bidirectional fix introduced a false positive (a quoted placeholder could
  suppress a real grant); final fix requires placeholder → copyright → grant
  order within 300 chars (real gap ~220 chars). Or-later lookahead window
  (1,000 chars) also leaked into a neighbouring grant (`CPLX` L141-171).

### 3.4 Encoding, streams and environment

- `py-spdx-license` 0.0.1 opens its JSON data with the locale encoding: under
  `LC_ALL=ja_JP.eucJP` every command dies at import with `UnicodeDecodeError`
  at byte 103585; under cp1252 seven licence names become mojibake silently;
  PEP 686 (Python 3.15) hides it. Upstream PR JPEWdev/py-spdx-license#5;
  workaround `PYTHONUTF8=1` (`ROAD` item 2; `README.md` L78-92). Found by the
  CLI matrix (`IMPL/README.md` L41-42).
- Streams/signals: click exits 1 ("no") on Ctrl-C and closed pipe, so `is-osi`
  could read an interrupt as "not OSI"; `click.echo` drops output silently on
  a closed stdout; `<&-` stdin crashed with `AttributeError`; full disk or
  `ulimit -f` gave exit 120; a failing stderr turned every status into 120 at
  the exit flush (`TDR` L100-132).
- `CliRunner` runs click in standalone mode, so rewording errors in
  `cli.main()` alone would leave tests seeing click's format (`TDR` L36-42).
- Fetching traps: truncated `.tar.gz` raises bare `EOFError`; a corrupted gzip
  CRC trailer is never noticed (tarfile stops at end-of-archive); the `data`
  filter makes absolute names relative instead of raising; `int(None)` is
  `TypeError`; a future-dated cache never expires (5-minute skew allowance
  added); IDF fingerprints divided by zero for a one-licence corpus
  (`log(1)=0`), found only by the end-to-end test (`FETCH` L65-81).
- `Path.unlink(missing_ok=True)` swallows only `FileNotFoundError`
  (`GATE` L87-90).
- Floating-point tie window: `0.91 - 0.90` was not a tie but `0.35 - 0.34`
  was; now compared after rounding to 9 places (`TDR` L420-423).
