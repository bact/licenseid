---
Created: 2026-10-05
Last-Modified: 2026-10-05
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# System design and decisions

Architecture and the decisions behind it, with rejected alternatives. Extracted
from the repository's design and implementation docs.
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

Project facts: Python ≥3.10; 25 modules in `src/licenseid/` (6,845 lines in
total, `wc -l`); 287 commits, first 2026-04-27; v0.4.0 released 2026-10-05
(`CHANGELOG.md` L8); DOI 10.5281/zenodo.19881009 (`README.md` L7). Licence
corpus: SPDX License List 3.28.0, 695 licences (`DES/new-matcher.md` L21-28;
`THR` L14). Used as the licence detection engine for the Pitloom SBOM
generator (`README.md` L14).

## 1. System design and architecture decisions

### 1.1 Pipeline (current state, 2026-10-02)

- Tiers: **Tier 0.5** marker detection (SPDX tags, then a manifest's
  `license` field) → **Tier 0** short-text ID/name shortcut → **Tier 1**
  SQLite FTS5 recall → **Tier 2** RapidFuzz ranking (`IMPL/README.md` L18-26).
- Module split: `matcher.py` = pipeline; `retrieval.py` = Tier 1;
  `shorttext.py` = Tier 0; `ranking.py` = sort order and `-only`/`-or-later`
  tie-breaker (`IMPL/README.md` L21-23). Split on 2026-09-21 as a pure move:
  `matcher.py` 888 → 544 lines; `ranking.py` 117, `retrieval.py` 179,
  `shorttext.py` 87 (`CPLX` L353-363).
- FTS5 table uses `tokenize = 'trigram'` (`src/licenseid/database.py` L161-166).
- No daemon or server; portable SQLite file (`README.md` L11-12).
- A **Tier 3** (Java `tools-java` validation via JPype, `--java`) existed and
  was **removed on 2026-09-19**: "untested and silent on failure, so removed
  instead of fixed"; off by default, not tested in CI (`TDR` L525-528;
  `IMPL/README.md` L20-21). CHANGELOG: "Results are unchanged" (`CHANGELOG.md`
  Removed section).

### 1.2 Original design rationale (`DES/new-matcher.md`, 2026-04-28)

- Problem motivating the design: near-variant licences, e.g. `Pixar` "is
  essentially Apache-2.0 with modifications to section 6"; Apache-2.0 text was
  misidentified as Pixar in tests (L14-17).
- Corpus statistics (normalised words, v3.28.0): 695 licences; mean ~1,021
  words; shortest any-OSI (12 words); longest APL-1.0 (7,286); LGPL-3.0-*
  6,890; GPL-3.0-* 5,652; next shortest TermReadKey 15, diffmark 17,
  check-cvs 19, man2html 20 (L23-44).
- Proposed: BM25 retrieval to a top-20 in <10 ms (L60-66); sliding window
  (window ≈ query length, stride/overlap 200 words) (L68-74); two metrics,
  similarity S (RapidFuzz on best window) and coverage
  C = query words / licence words (L82-96); "critical legal tokens" safeguard
  (`not`, `except`, `unless`, `exclusive`, `irrevocable`) for "shall" vs
  "shall not" (L210-219); "Base + Delta" variant reporting with `difflib`
  (L167-206).
- What survived into code: coverage, best-window alignment (`--diff`), and the
  critical-token safeguard: if 0.90 < similarity < 1.0 and the presence of any
  of {`not`, `except`, `unless`, `irrevocable`} differs between query and
  candidate, similarity ×0.95 per token (`src/licenseid/similarity.py`
  L148-155).
- **[observation]** `new-matcher.md` reads like conversational AI design
  advice (it ends "Would you like a code snippet…", L236); useful as evidence
  of AI-assisted design origins.

### 1.3 Tier 1 (FTS5 recall) design decisions

- Query truncated to first 100 words; candidate limit raised 20 → 50 "to
  ensure canonical licenses are not lost among similar variants (e.g., BSD
  variants)" (`IMPL/performance-optimization.md` L16-17).
- FTS5 OR-term limit raised 10 → 20 words: HPND-family preambles share the
  first 10 words ("permission to use copy modify and distribute this
  software"), so with 10 terms "hundreds of indexed licences match" and the
  right one leaves the top 50 (`ACC` §9, L148-158).
- Word cap briefly 200, reverted to 100: "Recall@1 is flat beyond 100 words"
  (`ACC` §2, L66-70); 200 gave "zero net pool recall improvement vs 100 for
  any subcat" and slower queries (`OPT` L176).
- **Dual head + tail query** for inputs >200 normalised words: head =
  `words[:100]` (FTS uses the first 20), tail = exactly `words[-20:]`
  (warranty disclaimer, governing law) — surfaces licences with generic
  preambles but unique closings (OSL-1.0, OSL-1.1, OPL-1.0) (`ACC` §8,
  L122-137). Passing `words[-120:]` was wrong: FTS5 saw only words -120 to
  -101, "mid-text and less distinctive" (`src/licenseid/retrieval.py` L35-41).
- Tail-only additions capped at `TAIL_ONLY_CAP` = 25, so the union is ≤75
  candidates and Tier 2 does ≤75 passes. On 469 licences with >200 words,
  uncapped tail added mean 33 candidates (median 38, max 50), union mean 83
  (max 100) (`src/licenseid/retrieval.py` L45-57; `README.md` L31-34).
- Comment prefixes (`//`, `#`, `;`, `*`, `/*`, trailing `*/`) stripped before
  FTS5 to help Type 5 inputs (`ACC` §6, L94-105). A second, intentionally
  different stripper from the one in `normalize_text`; checked 2026-09-21 and
  kept: a prefix `normalize_text` leaves (`;`, `;;`, `///`, `**`) hides a list
  marker from its bullet rule; a random check of 3,000 inputs without list
  markers missed this (`TDR` L407-413).

### 1.4 Tier 0 (short text) design decisions

- Threshold: an input is "short" below **30 normalised words** (~200 chars);
  marker detection suppressed below 30 words (`THR` L53-77; `ACC` §7).
- Case-folded exact ID match before the fuzzy loop; returns score 1.02
  (`EXACT_MATCH_SCORE`) as a "definitive-result signal" (`ACC` §3, L72-77;
  `src/licenseid/shorttext.py` L17).
- Prose disambiguation fast path runs on the **raw** (un-normalised) text
  because `normalize_text` strips the punctuation and case the regexes need
  (`ACC` §4, L79-84).
- Tier 0 RapidFuzz scorers take `score_cutoff=threshold`: a 200,000-character
  word went 2.7 s → 0.3 s with no result change (proved by
  `test_shorttext.py::test_the_cutoff_changes_no_result`). Rejected:
  skipping the scan for a word longer than any name, since it is a
  characters-per-word limit that the CJK lesson rules out (`TDR` L150-161).

### 1.5 Tier 2 (RapidFuzz ranking) design decisions

- Adaptive rule: large queries use global `token_sort_ratio`; fragments
  (<500 words) use `partial_ratio_alignment` (`IMPL/performance-optimization.md`
  L18-20). Current rule: exact string equality → 1.0; if query length ≥ 0.8 ×
  candidate length or alignment not affordable → `token_sort_ratio`; else
  `fragment_similarity` (`src/licenseid/similarity.py` L141-146).
- **Probe gate** (PR #19): a 60-word probe from the query middle is scored
  first with `partial_ratio`; only candidates with probe score ≥ 0.52
  (`PROBE_GATE`) get the full alignment scan. Rationale: a full
  `partial_ratio` scan of a weak candidate is RapidFuzz's worst case (~50-80 ms
  per candidate); the probe costs ~80x less; "in fixture sampling (incl.
  distorted inputs) no candidate below _PROBE_GATE ever reached the 0.6
  alignment threshold" (`src/licenseid/similarity.py` L20-28; `R2` L15-16).
  ~48.6% of gated candidates pass (`DES/probe-anchored-windowing-plan.md` L51).
- Composite score (`src/licenseid/similarity.py` L163-209; `README.md`
  "composite score"): similarity − coverage penalty + coverage bonus
  (+ popularity) (+ marker boost).
  - Coverage penalty is 0 for fragments (coverage < 0.5), `(1−coverage)×0.02`
    for 0.5 ≤ coverage < 0.8; rationale: penalising fragments biases against
    the right licence when several share a preamble.
  - Coverage bonus +0.005 when 0.95 ≤ coverage ≤ 1.05.
  - Popularity: `log10(max(1, pop_score)) × 0.0001` when enabled (default off).
  - Marker boost only when confidence ≥ 0.85 (`ACC` §5): a fuzzy name hit such
    as "Apachi License" at ~0.7 confidence gave `+0.021`, enough to flip close
    candidates; guard raised from implicit 0 (`OPT` L146-150). For long pure
    text (≥50 words) with 0.85 ≤ conf < 0.94: `+conf×0.03`; otherwise
    authoritative: `max(score + conf×0.05, conf×0.95)`.
- Coverage-aware scoring was introduced to break ties between a licence and
  its superset (BSD-3-Clause vs Sleepycat) (`IMPL/performance-optimization.md`
  L21).
- **Discriminative n-gram fingerprints** (planned `R1` §1, implemented): word
  5-grams with IDF = log(k / df), top 20 per licence stored at build time
  (`FINGERPRINT_N`=5, `FINGERPRINT_TOP_N`=20, `src/licenseid/fingerprint.py`
  L22-23); used as an additive tie-breaker capped at `_FP_BOOST` = 0.05,
  "calibrated to be in the same range as the marker boost"
  (`src/licenseid/matcher.py` L42-47; `IMPL/README.md` L33-34). Planned
  storage estimate: 20 × 695 × ~30 bytes ≈ 400 KB (`R1` L170-171).
- Importance of fingerprints: a kill between metadata commit and fingerprint
  computation leaves a "ready" DB without fingerprints, and on a real database
  the top match changes (`MIT` becomes `Xnet` for MIT text) (`TDR` L512-518).

### 1.6 Ranking and `-only` / `-or-later` tie-breaker (`ACC` §10, `TDR` item 8)

- GPL-2.0-only and GPL-2.0-or-later have identical bodies; scores tie, and
  alphabetical tie-break always picked `-only`. Granting language is the only
  evidence (`ACC` L162-166).
- Mechanism: scores within `TIE_WINDOW` = 0.01 are a tie; the preferred one
  gains `TIE_NUDGE` = 0.005 and the other loses it. A swap that left scores
  alone was rejected because the list would no longer be in score order
  (`ACC` L168-175; `src/licenseid/ranking.py` L22-28; `DEP_PENALTY` = 0.03).
- One sort key `ranking.ranking_key`: score with deprecated penalty, then
  non-deprecated, then popularity, then ID (`ACC` L178-180). Three sorts had
  drifted apart; the tie-breaker's re-sort omitted the penalty and could put a
  deprecated ID above its replacement (`TDR` L414-419).
- Tie-breaker visits only the `-only` member; a mutation audit showed the old
  `processed` set could not change a result; a 60,000-list differential test
  found no difference for unique IDs (`CPLX` L374-379).

### 1.7 Deprecated-ID semantics (`ACC` §1)

- `+` form (`GPL-2.0+`) is unambiguous → `-or-later` via DB `superseded_by`.
  Bare `GPL-2.0` is ambiguous (identical texts); resolution order: (1) DB
  lookup, (2) prose context in a ±150-character window for or-later phrases
  or a narrow post-ID window for "only", (3) conservative fallback to `-only`
  (L20-45).
- Non-mapped `+` IDs keep `+` after canonicalising the base:
  `Apache-2+` → `Apache-2.0+`, via shortest unambiguous prefix (L47-64).
- Coverage tests: `tests/test_deprecated_ids.py` checks every deprecated ID
  of the bundled License List with `-only`/`-or-later` successors, and every
  deprecated `-with-` ID (7; one, `GPL-2.0-with-classpath-exception`, had been
  missing) (`TDR` L209-230). GFDL-1.1 to 1.3 had no redirect at all (`TDR`
  L209-213).

### 1.8 SPDX expression handling (PR #61; `EXPR`)

- "One reader, one resolver, one judge": `identifiers.leading_expression`
  (reader), `MarkerDetector.resolve_license_value` (resolver for tag, JSON,
  TOML, INI, `license_id`), `identifiers.is_simple_expression` (judge of what
  `--id` may hold) (`EXPR` L17-32).
- Replaced a regex holding its own SPDX grammar that read
  `MIT OR (Apache-2.0 AND BSD-3-Clause)` as a certain `MIT`, dropped
  `(MIT OR Apache-2.0)`, and cut `DocumentRef-x:LicenseRef-y` at the `:`
  (`TDR` L322-331).
- Resolver tries the whole value as a name first: "MIT No Attribution" is
  MIT-0, not MIT (`EXPR` L27-30).
- **Rejected path**: widening `--id` to any expression, then reversing it:
  `MIT OR Apache-2.0` declares neither licence and `is-osi`/`is-fsf` have no
  answer for it (`EXPR` L36-41; `TDR` L344-353).
- "or later" is a grant, not the OR operator; qualifies the ID beside it (the
  licence of a WITH, not its exception); closes brackets
  (`(GPL-2.0 or later)` → `(GPL-2.0-or-later)`); a value continuing after a
  grant is refused to avoid understating obligations (`EXPR` L45-50; `ROAD`
  item 20).
- One reader of "or later": `classify.OR_LATER_PHRASE`; a bare "or later"
  needs a number before it ("sooner or later" is not a grant); `not`/`no`
  before it turns it off (`ACC` L181-188). Before unification, "version 2 of
  the License, or any later version" came out `-only` from the marker detector
  and `-or-later` from Tier 0 (`TDR` L423-430).
- Unknown tag values (`NoSuchLicense-9.9`, `Apache-2.O`, `Copyright`) used to
  be reported at score 1.0 and `is_spdx: true` while `is-spdx` said false; now
  a candidate requires a valid expression with at least one recognised ID
  (`TDR` L362-393).
- `py_spdx_license` cannot parse the `+` operator (upstream issue #1)
  (`EXPR` L56; `TDR` L376-377).

### 1.9 Manifest reading (`TDR` item 18, PR #65)

- PEP 639 string form (`license = "MIT OR Apache-2.0"`) was not read; with no
  marker under 30 words, a small `package.json`/`pyproject.toml`/`Cargo.toml`
  was matched by name and answered `Apache-1.0` at 1.01 (`TDR` L232-242).
- Fixes: field that resolves scores 1.0 at any length; TOML string form only in
  `[project]`, `[tool.poetry]`, `[package]`, `[workspace.package]`;
  extensionless text read as TOML only if its first non-blank non-comment line
  is a table header (a README with a `[project]` example answered MIT);
  Cargo's `/` read as OR; a manifest is never matched by name as a whole
  (`TDR` L243-283).
- Flags on every result: per-result DB lookups made a broad name such as `GPL`
  (42 results) 20 times slower; flags copied from cached tables instead
  (`TDR` L261-266).

### 1.10 Public result and scoring scales (PR #68; `TDR` item 22)

- Internal tier scales: tag 1.0, exact ID/name 1.0 or 1.02, look-alike name
  1.01, text up to ~1.08 (`TDR` L163-168; `ROAD` L186-190).
- Public result: nine keys, `method` (tag, field, id, name, text), `exact`
  flag, score capped to 0-1 and rounded to 4 places, null where nothing was
  measured; JSON Lines in RFC 8785 (JCS) form so equal results print equal
  bytes (`TDR` L169-201; `README.md` §4).
- Rejected: `--threshold 1.02` as "exact only" (a tag scores 1.0, a close text
  up to 1.08); marking every deprecated row inexact (made `--exact` find
  nothing for "GNU Affero General Public License v3.0"); keeping `best_window`
  in the result (`TDR` L189-201).
- Ranking reads raw records (`_match_raw`), never the capped public score
  (`AGENTS` L342-350).

### 1.11 SPDX matching-guideline normalisation order (`src/licenseid/normalize.py`)

14 ordered steps (`normalize.py` L242-349): 1 HTML→text (only if a closing tag
is found; opening tags look like template placeholders `<year>`); 2 comment
prefixes (guideline 5a); 3 copyright-notice removal (guideline 9, **off**);
4 repeated separators (5b); 5 bullets (6); 6 `https`→`http` (12); 7 ©→(c) (8);
8 all dashes incl. ASCII `-` → space (4); 9 quotes (4); 10 lowercase (3);
11 whitespace collapse "ahead of schedule"; 12 varietal spellings from SPDX
`equivalentwords.txt` (7), incl. `&`→`and` before punctuation removal;
13 remaining punctuation; 14 final whitespace collapse (2).

Order-sensitivity findings documented in code:

- Comment prefixes must go before copyright removal, else `# Copyright …`
  headers are never recognised (L248-254).
- Hyphens folded to space before varietal matching, and whitespace collapsed
  before step 12, to keep `normalize_text` **idempotent** (`copyright-owner`
  otherwise survives the first pass) (L28-39, L265-272).
- With step 3 enabled it is not idempotent: ~2% of fixture variants normalise
  differently on a second pass (docstring after L272).
- **Guideline 9 deliberately disabled**: full `bench_compare` showed −0.72%
  overall recall (worst on mixed content and Tier 0.5/1, several categories
  −5-7%); disabling it gave +0.51%. Root cause: the pipeline uses copyright
  boilerplate as *accidental* discriminative signal between near-duplicate
  bodies (e.g. ISC vs Python-2.0) (`normalize.py` L224-239).
- `NORMALIZATION_VERSION = "2"` stored in the DB; outdated normalisation is a
  warning condition (`src/licenseid/database.py` L78; `AGENTS` CONDITION list).

### 1.12 Data fetching and caching (PR #51; `FETCH`)

- Three sources: spdx.org `licenses.json` (45-day cache), GitHub
  `license-list-data` tarball (never expires), GitHub Innovation Graph
  `popularity.csv` (75 days) (L18-25).
- Fallback order: valid cache → one download → stale cache (only if caching
  allowed) → explicit `--version` or error; `--no-cache` never reads cached
  data (L33-35).
- Gentle: identifying User-Agent, timeouts, one attempt, no retry; ETag and
  rate limiter deliberately not added (L43-46).
- Only parseable data cached; atomic writes (temp + `os.replace`); version
  string validated `[A-Za-z0-9][A-Za-z0-9._-]*` (CWE-22); tarball extracted
  with `tarfile` `data` filter or equivalent manual check; self-healing
  corrupt caches (L47-63).

### 1.13 Database readiness gate (PR #55; `GATE`)

- Asymmetric policy: **read is fail-open** (refuse only what is certain; "a
  wrong refusal costs the user an answer"); **write/delete is fail-closed**
  ("a wrong acceptance destroys or overwrites somebody else's file") (L19-28).
- Bridge: internal tag `unknown` (locked DB, indistinguishable from a hot
  rollback journal); `Refusal = tuple[str, DatabaseNotReadyError]`. "Without
  the tag, every attempt to serve both callers from one boolean produced a bug
  in one of them" (L30-36).
- Ready means: `licenses`, `db_metadata`, `license_index` (FTS5) exist;
  `license_list_version` not blank; every `license_id` is text; both tables
  non-empty. Structural check chosen over `PRAGMA quick_check` (~200 ms on a
  real DB, twice per command) (`TDR` L478-489).
- Exit 2 for a not-ready DB in `match`/`is-*`, where exit 1 already means "no"
  (`AGENTS` CLI output).

### 1.14 Connection and cache architecture (PRs #69, #72)

- Each lookup opened its own connection (~16 per `match()`, `R2` L169-170);
  4,000 distinct `LicenseRef-*` tags took 9.0 s, nearly all in connect/close.
  Per-thread shared connection inside `LicenseDatabase.reading()` → 1.85 s
  (`TDR` L134-148).
- Rejected: per-value cache (useless for distinct values); one connection per
  `LicenseDatabase` (sqlite3 refuses cross-thread use; would read a deleted
  file through a stale handle) (`TDR` L144-148).
- `dbcache.TableCache`: reads each table's IDs once; unknown ID costs no
  query; 1.73 s → 0.52 s, one query per tag instead of five; invalidated when
  `last_update_datetime` changes (seen across processes) (`TDR` L56-88).
- Rejected: `CREATE INDEX` on `license_id COLLATE NOCASE` and a plain search
  text table — `_init_db` runs at every open, so a new index would write on a
  read and fail on a read-only file (`TDR` L83-86).

### 1.15 CLI output design (`AGENTS` "CLI output", `README.md` §4-5)

- Unix philosophy: `KEY=VALUE` line-delimited output; stdout carries only the
  result; one diagnostic grammar `LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION]`
  with a closed vocabulary of conditions, enforced in tests by
  `tests/conftest.py::check_diagnostic_grammar` (`AGENTS` L36-ff).
- Exit codes: 0 true/match; 1 no/false; 2 usage or setup (incl. DB not ready,
  unwritable output); 130 Ctrl-C; 141 closed pipe (`README.md` exit-code table).
- `;` in an echoed value would forge the ACTION part, so it is replaced by `,`
  (`EXPR` L82-83).
