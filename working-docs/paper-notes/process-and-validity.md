---
Created: 2026-10-05
Last-Modified: 2026-10-05
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Engineering process and threats to validity

Process lessons recorded in the repository, threats to validity, open questions
and future work.
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

## 4. Engineering-process lessons

### 4.1 Development setting

- One developer with AI coding agents; "Private alpha, one developer. No
  backward compat needed yet" (`AGENTS` Project context). Agent instructions
  live in `AGENTS.md`, symlinked as `CLAUDE.md`; its "Traps and test patterns"
  section is a curated list of "things that cost time in earlier sessions"
  (`AGENTS` L211-400).
- Documentation discipline: `working-docs/design/` = future work;
  `working-docs/implementation/` = record of what was built, decisions, and
  rejected paths; dated front matter (`IMPL/README.md` L12-14, L93-101).
- Round-2 method: find (cProfile on a mixed workload) → plan (`EXPLAIN QUERY
  PLAN`) → self-review → implement → test → review/re-profile (`R2` L30-51).

### 4.2 Characterization tests and refactoring

- Rule: "Refactor with characterization tests first: they found a real bug in
  every refactor so far. Pin the bug (`# BUG:`), refactor purely, then fix it
  as a separate step and flip the pin to a regression test" (`AGENTS` L221-224).
- Evidence by refactor:
  - `_detect_gpl_headers` (McCabe 14→8, cognitive 49→20): zero unit tests
    before; two pre-existing bugs found (or-later window bleed; appendix
    suppression never firing), pinned then fixed (`CPLX` L114-171).
  - `_detect_structured_format` (McCabe 13→6, cognitive 23→9): ~12 bugs
    found and fixed in fetching/caching, incl. two CWE-22 path traversals and a
    75-day cached error page (`CPLX` L267-331).
  - `matcher.match()` (McCabe 19→6, cognitive 46→6) and `_get_candidates()`
    (McCabe 13→1, cognitive 32→1): 19 characterization tests written first; "no
    pre-existing bugs surfaced this time", but fixture consolidation exposed the
    shared-cache keep-alive bug (`CPLX` L176-250). **[observation]** So the
    "every refactor" claim holds only if this test-infrastructure bug counts.
  - `_normalize_single_id` McCabe 23→11, cognitive 48→15 via one shared
    `_lookup_case_insensitive` helper (`CPLX` L97-112).
- Differential testing: tie-breaker simplification checked with a 60,000-list
  differential test and a before/after over 4,741 results (`CPLX` L374-379);
  every fixture's top three answers compared before/after (1,405 files,
  unchanged) (`EXPR` L90-91).

### 4.3 Mutation checks

- "Mutation-check new tests by breaking a line and rerunning"; clear
  `__pycache__` between mutants — a same-size mutant restored within the same
  second leaves a stale `.pyc` that looks like a failing baseline; when
  mutating a copy, use `PYTHONPATH=<copy>/src` or every mutant "survives"
  because `.venv` is an editable install (`AGENTS` L240-245; `FETCH` L108-111).
- Mutation checks found tests "that passed for the wrong reason" in
  `_foreign_schema` and `tests/db_variants.py` (`GATE` L97-99).
- New tests run against a `git archive` of HEAD's `src/` to prove each fails
  without the fix (`EXPR` L87-89).
- Multi-agent hazard: "Do not run a mutation agent while another agent edits
  `src/`": a snapshot captured a live mutant of `database.py` and produced a
  phantom finding (`GATE` L103-106; `AGENTS` L370-372).

### 4.4 Complexity ceilings as ratchets

- Targets = pylint built-in defaults (Args ≤5, Locals ≤15, Nesting ≤5,
  Branches ≤12, Returns ≤6, Statements ≤50, McCabe ≤10, Cognitive ≤15);
  interim ceilings set to the **exact** current repo maximum (Branches 13,
  Locals 23, McCabe 12, Cognitive 29, module lines 864), so any regression
  fails CI (`CPLX` L16-47; `AGENTS` L160-180).
- "Don't raise a ceiling to make a change pass; refactor instead"
  (`AGENTS` L178-180). `database.py` crossed `max-module-lines` three times
  during PR #55; each time a cohesive piece moved out (931 → 926)
  (`GATE` L112-116). History of module-line ceiling: 944 → 942 → 935 → 933
  → 931 → 924 → 926 → 921 → 915 → 913 → 864 (`CPLX` L78-90).
- Measurement pitfalls: running `pylint --generate-toml-config` inside the
  repo reflects local overrides — an earlier pass quoted pitloom's
  Branches≤20/Statements≤80 as pylint defaults (actual 12 and 50)
  (`CPLX` L30-35); a single-file flake8 scan undercounted; measuring `src/`
  only missed that a **test helper** (`test_accuracy.py::run_accuracy_test`,
  cognitive 29) sets the Cognitive ceiling (`CPLX` L49-65, L403-407); a stale
  `# pylint: disable` pragma hid that a function sat exactly at the ceiling
  (`CPLX` L126-131).
- CI hardening: mypy had run with `--no-strict-optional` and
  `continue-on-error`, so "it never failed a build"; CI ran neither flake8 nor
  `pylint tests/` (`TDR` L548-556). Judge pylint by exit code, not the
  10.00/10 rating (one convention message still exits 16) (`AGENTS` L319-321).
- Prioritisation formula for debt: Priority = (Impact + Risk) × (6 − Effort),
  each 1-5 (`ROAD` L15-16; `CPLX` L94-95).
- File-size limit: soft 400-500, hard 800 lines for all files; `matcher.py`
  must stay under 800 (`AGENTS` Project context).

### 4.5 Benchmarks vs unit tests

- The 18-licence accuracy subset "is a fast smoke test, not a substitute for a
  full benchmark"; "Provably identical for the winning candidate is not
  provably identical overall" — a change can corrupt Recall@N for N>1 by
  reordering losers (`R2` L296-313).
- Risk classes: SQLite-level changes (indexes, pragmas, caching static data)
  change only speed, so pytest + reasoning suffices; anything touching
  `similarity.py` scoring needs a full corpus run (`R2` L314-320).
  **[observation]** The "static data" premise later proved false (`R2`
  L156-159; `TDR` L66-73).
- Timing discipline: time against `main`, not the branch; distinct values;
  balanced payloads; 10x headroom for CI's Python 3.10 (`AGENTS` L392-400).
- Benchmark DB built by `bench_single.py` directly from the tarball,
  bypassing `_update_db_records` (`BREADME` L33-36).

### 4.6 CLI test matrix (`tools/cli_matrix/`)

- Runs the real CLI as a process in real shells (bash, zsh, sh, dash, ksh),
  locales, stdio states, signals, `HOME` variants, input sizes, against a
  known-flags baseline; ~1,200 cells (`tools/cli_matrix/README.md` L1-57).
- "Every FLAG this tool has produced so far was a defect the test suite could
  not reach" (`tools/cli_matrix/README.md` L14-15). Found the eucJP crash in
  `py-spdx-license` and the environment failures (`IMPL/README.md` L38-45).
  11 cells left the baseline after the streams/signals fix (`TDR` L129-131).
- Not in CI (needs a real database) (`IMPL/README.md` L43).
- A `FIXED_FLAG` is not proof: cell `E4-028` (`ulimit -f 0`) stopped flagging
  because the command now failed *earlier*, at DB open (`GATE` L107-111).
- Safety incident: an early version deleted the developer's real
  `licenses.db` when cells ran with `HOME` unset (`AGENTS` L246-252).

### 4.7 Review loops

- PR #55 review rounds 4-7 each found something; findings were concentrated in
  the write/delete guard added in round 4 — "Count findings per surface, not
  per round" (`GATE` L117-122).
- Reviews repeatedly found defects in fixes: `--id` widening reversed;
  `TableCache` first version would have kept stale IDs; two threading races
  (`TDR` L69-82); click error rewording missed three cases (`TDR` L43-51).
- "Re-read the PR description before merging: after the `--id` reversal it
  still described the opposite" (`EXPR` L92-93).
- Decision to stop one-off fixes: "no more one-off fixes of these edge cases";
  revise the matching rules as a whole (`ROAD` item 31, L179-184;
  `DES/matching-rules-redesign.md`).

### 4.8 Single-source-of-truth refactors

Recurring theme: duplicated partial logic diverged and produced bugs; each
fix consolidated to one function — one input reader (`textinput`), one
"or later" reader, one ranking key, one expression reader/resolver/judge, one
path resolver, one result builder (`AGENTS` traps; `ACC` §10; `EXPR`;
`GATE` L48-54; `TDR` item 4, item 22). Six places still hold part of the
SPDX grammar (`DES/matching-rules-redesign.md` L28-49).

---

## 5. Threats to validity, limitations, open questions, future work

### 5.1 Threats to validity of the evaluation

- **Closed-world corpus**: fixtures are generated from SPDX License List
  texts (3.28.0), the same texts indexed by the system (`FIX` L5, L32).
  **[observation]** Measures recognition of known texts, not
  generalisation to real-world variants.
- **Synthetic mixed content**: templates "generated with LLM assistance"
  (`tests/fixtures/generation-plan.md` L86;
  `tests/fixtures/mixed-content-analysis.md` L70); the real-world
  proportions (60/20/10/5/5%, 40/30/20/10%) have no stated sample or method.
- **Stale numbers**: `OPT` status note: R@1 figures "predate this work and
  ha[ve] not been re-benchmarked" (L12-22); ROAD item 7 says the same.
  `BENCH` (2026-07-20) still shows `id_casing` 80% flat and `id_deprecated`
  0% R@1 although the case-fold match "landed earlier" (`OPT` L13-14).
  **[observation]** Unexplained; needs a fresh run before publishing.
- `BENCH` headers say "`main` vs `main`" while tier tables say
  `license-marker`; the second column is the rejected `score_cutoff` branch
  (numbers match `R2` L238-243). **[observation]** Labelling defect.
- "Precision 1.85%" in `BENCH` L245 is undefined in the docs.
  **[observation]** Probably computed over all returned candidates; define
  or drop.
- Projected, not measured: `head_300` "~91% (projected)" (`THR` L66);
  probe-anchored windowing gains "rough, unvalidated" (`DES/probe-anchored-
  windowing-plan.md` L196-204); `OPT` combination estimates.
- Run-to-run noise: ~0.18 pp (≈1 fixture) attributed to SQLite tie-order
  (`R2` L254-256); `id_distorted` R@5-R@40 moves ±1.67 pp between identical
  code paths (`BENCH` L27-31).
- Benchmark DB path differs from production update path (`BREADME` L33-36);
  thresholds (100/200/50/25/20) were tuned on raw word counts but now slice
  normalised counts — "re-validate via bench_compare" (`src/licenseid/
  retrieval.py` L59-62).
- Benchmarks do not check `best_window`/`--diff` quality at all
  (`DES/probe-anchored-windowing-plan.md` L132-134).
- Fixture limits calibrated to fixtures prove little (`AGENTS` L383-391).
- Python-version dependence of expression results (3.10 vs 3.14,
  `ROAD` item 19).
- Wall-time comparisons confounded by query-count changes (`OPT` L52-54).

### 5.2 Known limitations (open roadmap items, `ROAD`)

<!-- markdownlint-capture -->
<!-- markdownlint-disable MD013 -->

| Item | Priority | Issue |
| --- | --- | --- |
| 32 | 24 | Missing file argument matched as text (`LICENSE.txt` → `APL-1.0`, exit 0) |
| 2 | 20 | `py-spdx-license` locale-encoding crash; waits on upstream release |
| 5 | 15 | Conflicting options/inputs resolved silently; `--top -1`/`0` unchecked |
| 11 | 15 | Probe-anchored windowing; 9 s and 134 s slow cases |
| 7 | 12 | GPL/LGPL/AGPL tail recall floor: `tail_300`-`tail_500` lose 28-35 fixtures from top-50 |
| 9 | 12 | `scripts/`, `benchmarks/` unlinted; `bench_single.py` 770, `generate_fixtures.py` 755 lines; pylint 9.48/10, 11 flake8 findings |
| 10 | 12 | Environment failures: read-only WAL DB, `file://localhost`, lock contention, raw `sqlite3` errors in API, Ctrl-C during imports |
| 23 | 12 | Loose `License:` reader unbounded (9 s / 10,000 lines) |
| 31 | 12 | Matching-rules revision: grammar, certainty, ranking |
| 33, 34 | 12 | Non-ASCII tag values cut; expression flags wrong |
| 26, 28 | 10 | Parser guard; short phrases score 1.0 |
| 19, 20 | 9 | Depth by Python version; grant inside expression refused |
| 35 | 9 | `exclude` ignored by declared paths; repeated text misranked; textless deprecated rows still candidates |
| 13 | 6 | Apache-2.0 vs Pixar near-duplicate confusion — no fix designed |
| 30 | 6 | `GPL 2.0+` in prose |

<!-- markdownlint-restore -->

Also: `database.py` 864 lines, over the 800 hard limit (`CPLX` L383-397);
fingerprints committed after metadata (kill-window changes answers,
`TDR` L512-518); `licenseId` from tarball JSON used in paths unvalidated;
per-read not total timeouts (`FETCH` L113-118); `NONE`/`NOASSERTION` tags
read as unknown (`TDR` L389-391); tie-breaker not idempotent; nudge moves
reported scores by up to 0.005 (`TDR` L442-449); `match(text=...)` does not
check NUL or normalise line ends as `--text` does (`TDR` L404-406).

### 5.3 Open research/design questions (`DES/matching-rules-redesign.md`)

1. **SPDX grammar**: one reader returning a typed tree, other judges derived;
   conformance table "written from the grammar (SPDX Annex D), not from the
   bugs"; one depth cap; delegate to `py_spdx_license` once linear (L28-49).
2. **Certainty taxonomy**: evidence kinds (declaration, exact ID/name,
   look-alike name, phrase, whole text, close text) and the strongest answer
   each may give; is a short phrase hit evidence or an answer; what is an
   exact text under SPDX replaceable/omittable rules (L51-68).
3. **Ranking**: two keys, certainty then closeness, so no cap needed; family
   disambiguation as ranking rule or separate step; is `score` one number
   (L70-82; `ROAD` item 31 L186-199).
4. Flags for expressions (all/any/null) and references (L84-94).
5. Input and option precedence taxonomy (L96-111).
6. API error wrapping layer (L113-127).

### 5.4 Future work (accuracy and speed)

- Probe-anchored windowing: reuse probe alignment location (`dest_start`) to
  estimate the full-query window; risks — changes `--diff` output, offset
  estimate assumes uniform chars/word, fallback may erase savings; lower-risk
  variant: a larger 150-200-word probe with a real alignment search
  (`DES/probe-anchored-windowing-plan.md`). Also snap `--diff` windows to word
  boundaries (`ROAD` item 11).
- Fragment-aware Tier 2 scoring for head+tail inputs:
  `0.6 × head_sim + 0.4 × tail_sim`, expected +8-15 pp R@1 (`OPT` L198-207,
  not implemented per docs).
- Re-ranking that boosts candidates in both head and tail results (`OPT`
  L96-99; `THR` L117-121).
- Distortion-aware FTS5 query relaxation (`THR` L123-125); 20% distortion is
  "near the threshold for trigram FTS5 to fail entirely" (`OPT` L238).
- `name_distorted` partial-ratio scoring, expected 61% → ~75-80% (`OPT` L224).
- Re-enable guideline-9 copyright removal once discrimination no longer
  depends on boilerplate (`normalize.py` L234-238).
- Structural diffing, template neutralisation, segmented comparison for
  "one clause added" variants (`DES/new-matcher.md` L159-234).
- Short-circuit RapidFuzz on unique fingerprint hits (Phase 2 in `R1`
  L146-152, not implemented per docs); exception fingerprints (`R1` L156-161).
