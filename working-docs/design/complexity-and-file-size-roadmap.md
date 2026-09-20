---
Created: 2026-08-19
Last-Modified: 2026-09-19
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

`AGENTS.md` states target complexity/size thresholds. The linter ceilings
currently enforced in `pyproject.toml` (`[tool.pylint.design]`,
`[tool.pylint.format]`) and `.flake8` are **interim ratchets** set to the
*exact* current repo max (not a buffer above it) where that max exceeds
target, so CI passes today but any regression — even one point over the
current worst offender — trips it immediately. Until 2026-09-19 that was
only true for the pylint ceilings, and only on `src/`: CI ran neither
`flake8` (McCabe, Cognitive) nor `pylint tests/`. `lint.yml` now runs
`pylint src/ tests/` and `flake8 src/ tests/`. This doc is the backlog
that has to shrink before each ceiling can be tightened toward its
target.

"Target" below is pylint's own built-in default for that option, checked
clean (`cd /tmp && pylint --generate-toml-config`) rather than assumed —
running it inside this repo silently reflects our own overrides instead
of pylint's real defaults, which is how an earlier pass of this doc ended
up quoting pitloom's Branches≤20/Statements≤80 as if they were standard;
pylint's actual defaults are 12 and 50.

| Metric | Target (pylint default) | Interim ceiling | Current worst |
|---|---|---|---|
| Args | ≤5 | 5 (at target) | 5 (`similarity.py`, `matcher._rank_candidates`) |
| Locals | ≤15 | 23 | 23 (`database.py`) |
| Nesting | ≤5 | 5 (no ratchet needed) | 5 |
| Branches | ≤12 | 13 | 13 (2 functions, see note) |
| Returns | ≤6 | 6 (at target) | 6 (`tests/test_option_matrix.py`) |
| Statements | ≤50 | 50 (at target) | 35 (`markers._detect_gpl_headers`) |
| McCabe | ≤10 | 12 | 12 (2 functions, see note) |
| Cognitive | ≤15 | 29 | 29 (`test_accuracy.py`, see note) |
| Module lines | soft 400-500 / hard 800 | 931 | 931 (`database.py`) |

Measured 2026-08-19 via `pylint --disable=all --enable=too-many-<x>
--max-<x>=1`, `flake8 --max-complexity 1` and
`flake8 --max-cognitive-complexity 1` (needs `flake8-cognitive-complexity`,
run across all of `src/`, not a single file — a single-file scan
undercounted the true max on the first pass), and `wc -l src/licenseid/*.py`.
McCabe row re-measured 2026-09-18 after the `identifiers.py` fix landed;
Cognitive row re-measured 2026-09-18 after the `markers.py` fix below
landed. Whole table re-measured again 2026-09-18 after the `matcher.py`
fix below landed, this time also across `tests/` (not just `src/`) since
`.flake8`'s own `exclude` list doesn't exempt `tests/`, and `AGENTS.md`'s
documented `flake8 src/ tests/` command lints both — a stale
`src/`-only measurement would leave a ceiling that command immediately
fails on a file this pass never touched. That's how a test helper
(`run_accuracy_test`) ended up setting the Cognitive ceiling instead of
a `src/` function; several other rows (Args, Returns, Statements, Module
lines) were also already stale before this pass and are corrected here
as a drive-by, not something this refactor changed.
Branches, Statements and McCabe rows re-measured 2026-09-19 across `src/`
and `tests/`, after the CLI error handling moved into `exit_if_db_missing`
and `exit_no_input` and the two `--bold`/plain "no match" branches merged:
`cli.match` fell to McCabe 10, cognitive 20, 12 branches, so the Branches
ceiling dropped 15→13. Branches holders:
`matcher._apply_version_suffix_tiebreaker` and
`identifiers._normalize_expression`. McCabe holders:
`matcher._apply_version_suffix_tiebreaker` and
`database._prepare_license_and_exception_records`. Module lines 944→942
(`matcher.py`, shorter JPype message). Then 942→935 when the Java tier
was removed (2026-09-19); `database.py` now holds it. Then 935→933 when
`get_default_db_path()` stopped creating the directory. Then 933→931 when
`_get_cache_path` was inlined.

## Backlog, priority order

Priority = (Impact + Risk) × (6 − Effort), same scoring as the general
tech-debt roadmap.

### Done: `identifiers.py::_normalize_single_id` (McCabe 23→11, cognitive 48→15)

Was both the single highest McCabe score in the repo *and* the
second-highest cognitive score, in one function: four sequential
lookup-with-fallback stages (DB mapping, hardcoded deprecated maps,
bare-ID conservative fallback, `+`-suffix stripping), each with its own
case-insensitive retry branch.

- **Fix applied**: extracted a shared `_lookup_case_insensitive(mapping,
  key)` helper, reused by all four blocks here plus the identical
  pattern in `_normalize_exception_id`. Pure refactor, no behaviour
  change; new tests lock in the case-insensitive branches
  (`tests/test_identifiers.py`). McCabe ceiling dropped 23→19 (repo's
  new max moved to `matcher.match`); Cognitive ceiling unchanged at 49
  since `markers._detect_gpl_headers` was already the top offender on
  that metric and this change didn't touch it.

### Done: `markers.py::_detect_gpl_headers` (McCabe 14→8, cognitive 49→20)

Was the single highest cognitive score in the repo, all in one 115-line
loop body: per-match version/or-later extraction, appendix and
terms-explanation suppression heuristics, family classification, and
font-exception candidate construction (DB-backed or synthetic), all
inline.

- **Fix applied**: extracted three cohesive helpers —
  `_resolve_gpl_or_later` (the suppression heuristics),
  `_classify_gpl_family`, and `_build_font_exception_candidate` — each
  replacing a self-contained chunk of the loop body with a single call.
  Pure refactor, no behaviour change. The stale
  `# pylint: disable=too-many-branches` pragma above the function is
  gone; it had been masking that the function sat at exactly 15
  branches (the ceiling itself), not the "roughly zero" an earlier
  investigation pass wrongly inferred from the pragma's absence of
  output — the actual post-refactor count is 7. Cognitive ceiling
  dropped 49→46 (new repo max is `matcher.match`, unaffected by this
  change); McCabe ceiling unaffected since this function was never the
  McCabe max.
- **New tests** (`tests/test_markers.py`) close a real gap —
  `_detect_gpl_headers` had zero direct unit tests before this — and
  two adversarial cases written while adding them exposed pre-existing
  bugs, initially pinned (not fixed) to keep the extraction a pure
  refactor, then fixed as a deliberate, separate follow-up in the same
  pass once confirmed:
  - the or-later lookahead window (`text[m.start():m.start()+1000]`)
    had no upper bound at the *next* match, so a nearby second grant's
    or-later phrasing could leak into an earlier plain grant's window.
    **Fixed**: the window is now also capped at the next GPL-family
    match's start (`test_gpl_headers_nearby_grants_dont_bleed`).
  - the appendix-suppression check only looked *forward* from the grant
    match for the `<one line to give the program's name...>`
    placeholder, but the real canonical GPL-2.0 appendix places that
    placeholder *before* the grant sentence — so the suppression never
    fired against actual upstream GPL boilerplate.
    **First fix attempt** (bidirectional, placeholder-only, 1000-char
    lookback) traded that false-negative for a new false-positive,
    caught by review: a document that merely *quotes* the placeholder
    elsewhere (e.g. contributor guidance) could suppress a real,
    separate, genuinely or-later grant nearby.
    **Fixed properly**: the check now requires the canonical
    placeholder → `Copyright (C) <year> <name of author>` → grant
    ordering (both anchors, in order), within a tighter 300-char
    backward window (the real GPL-2.0 appendix gap measures ~220 chars)
    (`test_gpl_headers_appendix_real_layout_suppressed`,
    `test_gpl_headers_appendix_placeholder_too_far_back_not_suppressed`,
    `test_gpl_headers_appendix_placeholder_without_copyright_not_suppressed`,
    `test_gpl_headers_appendix_copyright_before_placeholder_not_suppressed`).
    The analogous risk in the *terms-explanation* suppression (a
    bare proximity check, no structural anchor) was found to be the
    same bug class but was left unfixed — the anchor there is an exact,
    unusual legal sentence rather than a generic phrase, and the real
    GPL-2.0/3.0 text's own Section 9/14 wording doesn't actually
    trigger this path (see the docstring on
    `test_gpl_headers_terms_explanation_unrelated_grant_nearby`, which
    pins the residual risk rather than leaving it undiscovered).

`_detect_structured_format`, originally grouped with this item, wasn't
touched by this pass — see its own "Done" section below.

### Done: `matcher.py::match()` and `_get_candidates()`

`match()`: McCabe 19→6, cognitive 46→6. `_get_candidates()`: McCabe
13→1, cognitive 32→1.

Was the repo's top McCabe and cognitive offender in one 177-line
function (`match()`), plus a second, 135-line function
(`_get_candidates()`) with the same shape: a Tier-dispatch pipeline that
grew a branch per tier as tiers were added, with several independent
early-return short-circuits threaded through shared local state
(`target_text`, `request`, `is_pure`, `norm_input`, `words`,
`marker_candidates`, `marker_boosts`).

- **Fix applied**: extracted seven private helpers —
  `_try_explicit_id_match`, `_resolve_target_text`,
  `_build_match_context`, `_try_tier0_5_markers`,
  `_try_tier0_short_text`, and `_run_tier1_and_tier2` for `match()`
  (plus a new immutable `_MatchContext` dataclass carrying the
  request-scoped state that 3+ of those helpers need, since a plain
  6-argument signature would trip the repo's `max-args=5` ceiling and
  none of those values are cheaply derivable from each other, unlike
  the single-value case fixed in the `_detect_gpl_headers` pass); and
  `_search_candidates_by_length`, `_filter_candidates`,
  `_inject_hinted_candidates` for `_get_candidates()`. Pure refactor, no
  behaviour change — each independently-short-circuiting phase returns
  `T | None` (`None` = fall through, mirroring the
  `_build_font_exception_candidate` convention from the previous pass).
  All three `# pylint: disable=too-many-*` pragmas that previously sat
  on `match()` are gone — confirmed via a before/after pylint run
  (`--enable=too-many-locals,too-many-branches,too-many-return-statements
  --max-<x>=1` against a pragma-stripped copy) that they were genuinely
  needed before (27 locals/9 returns/19 branches, all over ceiling) and
  fire nowhere in the file after extraction.
- **New tests**: `tests/test_get_candidates.py` (16 tests, new file) —
  `_get_candidates()` had zero direct unit tests before this; closes
  real gaps around the head/tail retrieval word-count thresholds (exact
  100/101/200/201-word boundaries), the tail-only candidate cap
  (promoted from a function-local to the module-level `_TAIL_ONLY_CAP`
  constant so tests can reference it), head/tail dedup, the
  `only_spdx`/`only_common`/`exclude` filters, and hint injection.
  `tests/test_matcher.py` gained 3 tests for
  `_apply_version_suffix_tiebreaker`, which also had no direct coverage.
  All 19 were written and passed against the pre-refactor code first
  (the established characterization-test-first pattern), then
  reconfirmed unchanged after extraction; no pre-existing bugs surfaced
  this time.
- **Code-review follow-up**: a review of the extraction itself found no
  correctness bugs (faithful, mechanical refactor), but surfaced several
  cleanup items, all applied: `_MatchContext` is now `@dataclass(frozen=True)`
  (its docstring claimed immutability the plain dataclass didn't
  enforce); its `words: list[str]` field — redundant with `norm_input`,
  read only for its length — became `word_count: int`, computed once;
  the docstring now states explicitly why `marker_candidates`/
  `marker_boosts` live outside the context (they're a tier's *output*,
  not a fixed input, so mutating an otherwise-immutable context to hold
  them would be worse); the near-identical in-memory shared-cache SQLite
  DB fixture, previously copy-pasted across `test_matcher.py`,
  `test_markers.py`, and the new `test_get_candidates.py`, is now one
  `make_memory_db_path()` helper in `tests/conftest.py`; and the
  tiebreaker tests plus the `_get_candidates` word-count boundary tests
  were collapsed into `@pytest.mark.parametrize`d tests per this
  project's own testing convention. Consolidating that fixture also
  surfaced a real, separate, previously-latent bug: `LicenseDatabase(db_path)`
  called without keeping a reference opens its own keep-alive connection
  to the shared-cache in-memory DB, but since nothing then holds a
  reference to that `LicenseDatabase` instance, CPython deallocates it
  (and closes its connection) immediately — and if that was the *only*
  open connection at that instant, the shared-cache DB (schema and all)
  is dropped before the caller's own `sqlite3.connect()` line ever runs,
  reproduced standalone outside pytest. Fixed by opening the helper's
  own keep-alive connection *before* constructing `LicenseDatabase`, so
  at least one connection is alive continuously across the handoff.
  (The three original inline fixtures happened not to trip this — likely
  incidental frame-reference timing under pytest — so it was never
  observed until the fixtures were consolidated and re-tested standalone.)
- **File-size note**: this is an in-file extraction (new private methods
  on the same class) — it does not shrink `matcher.py`. The file grew
  846→944 lines (new `def`/docstring overhead), so the module-lines
  ceiling moved 921→944 to track it honestly. The 800-line hard target
  is **not** resolved by this pass; `matcher.py` is now the file most in
  need of the same subpackage-split treatment as `database.py` below,
  once its complexity offenders (already fixed here) aren't the
  competing concern.
- **Ceiling side-effects**: re-measuring across all of `src/` *and*
  `tests/` (not just `src/`, since `.flake8` lints both and `AGENTS.md`'s
  documented `flake8 src/ tests/` command would otherwise immediately
  fail on an untouched file) found several other table rows were already
  stale before this pass — see the table note above. The new
  Cognitive ceiling (29) is set by a test helper
  (`tests/test_accuracy.py::run_accuracy_test`), not a `src/` function;
  `markers.py::_detect_structured_format` was tied for the McCabe ceiling
  (13) at that point; it is fixed in the next "Done" section.

### Done: `markers.py::_detect_structured_format` (McCabe 13→6, cognitive 23→9)

Extracted `_detect_json_license`, `_detect_toml_license` and
`_detect_ini_license`; the orchestrator keeps the extension gating. The
inline TOML regex is now the class attribute `_RE_TOML_LICENSE_TABLE`,
`import configparser` moved to the module top, and the docstring no longer
claims YAML support (there is none).

- **Tests**: the function had none (`spdx_source.py` coverage was 20%).
  `tests/test_spdx_source.py` grew from 3 to 41 tests. New:
  `tests/test_spdx_source_cache.py` (39) for the `licenses.json` cache and
  `clear_cache`; `tests/test_database_update.py` (22) runs
  `update_from_remote` and the CLI `update` command end to end on a
  synthetic release and checks tarball extraction against each unsafe
  member kind, with and without the `data` filter;
  `tests/test_fingerprint.py` (4). `tests/test_database.py` gained 2.
  `requests.get` is replaced by an autospec'd fake
  (`conftest.fake_requests_get`), so nothing touches the network. The
  tests were written against the unrefactored code first; those for the
  bugs below were then flipped to regression tests.
- **Bugs found and fixed**:
  - A row missing `num_pushers` raised an uncaught `TypeError` and crashed
    `LicenseDatabase.update_from_remote`; it now counts as 0 and is reported.
  - A cache-write failure (missing or read-only cache directory) aborted the
    update after a successful download; it now warns and keeps the data.
  - The raw response was cached before parsing, so an error page was served
    as a valid cache for 75 days; only data that parses to a non-empty map
    is cached, and a local cache that parses to nothing is re-downloaded
    once and overwritten.
  - A non-UTF-8 cache file raised `UnicodeDecodeError` instead of falling
    back to a download.
  - The cache was written in place, so an interrupted write left a truncated
    file that parsed to partial data and looked fresh. All three caches
    (popularity CSV, `licenses.json`, SPDX tarball) are now written through
    `_atomic_path`: a unique temporary file, renamed on success and removed
    either way. The tarball had the worst version of this: an interrupted
    download left a partial file that every later run reused.
  - `get_version_info` had the same defects as the popularity fetch: an
    uncaught `OSError` on cache write, a crash on a corrupt cache
    (`UnicodeDecodeError`, or a non-object JSON value), and caching of a
    response with no `licenseListVersion`. It now follows the same order
    (valid cache, one download, stale cache unless `--no-cache`, then an
    explicit version or `RuntimeError`) and reports `cache`, `remote`,
    `stale cache` or `unavailable`.
  - A corrupt or truncated cached tarball failed every later run (a
    truncated gzip raised a bare `EOFError`); `_process_and_store` now
    deletes it and asks for a re-run, so it is re-downloaded once.
  - `clear_cache` did not remove temporary files orphaned by a killed run.
  - A license list version (from `--version` or from a third-party
    `licenses.json`) went unchecked into a cache file name and a download
    URL (path traversal, CWE-22); versions are now limited to
    `[A-Za-z0-9][A-Za-z0-9._-]*`, and an invalid one from the network or the
    cache counts as an unusable response.
  - `tar.extractall` ran on a third-party tarball with no path checks
    (CWE-22); `spdx_source.extract_tarball` uses the `data` extraction
    filter, or an equivalent manual check on Pythons that lack it.
  - `is_cache_valid` treated a future-dated file as valid forever (the age
    was negative); it is now invalid beyond a 5-minute clock-skew allowance.
  - `compute_idf_fingerprints` divided by zero for a one-license corpus
    (found by the new end-to-end update test); it now returns no records.
  - `LicenseDatabase.update_from_remote` reported the popularity source from
    the cache-validity check, not from where the data came from.
    `fetch_popularity_data` now returns `(map, source)` with source
    `cache`, `remote`, `stale cache` or `unavailable`, and the report uses
    it.
- **Predictable, non-silent fallbacks**: every deviation from the normal
  path prints a warning, and the `Data sources` report says where each input
  really came from (`cache`, `remote`, `stale cache`, `unavailable`).
  Rows with a missing or non-numeric `num_pushers` are counted and reported
  instead of silently becoming 0; a CSV parse error yields no data at all
  (never a partial map that then gets cached); an unusable cache or an
  unusable download says so before the next fallback. `--no-cache` now
  means what it says: it also disables the stale-cache fallback for both
  the popularity data and `licenses.json`.
- **Gentle fetching** (all three `requests.get` calls in the module go
  through `_http_get`): an identifying `User-Agent`
  (`licenseid/<version> (+repo URL)`, version read from
  `licenseid.__version__` at call time), explicit timeouts, a single attempt
  with no retry or backoff loop, and a stale cache file as the fallback
  when a download fails, so a flaky network neither zeroes popularity nor
  triggers repeated requests. Not added: conditional requests (ETag,
  `If-Modified-Since`) and a rate limiter; the 45/75-day cache expiry
  already limits this to about one request per source per update.
- **Ceilings**: McCabe 13→12. Cognitive stays 29
  (`tests/test_accuracy.py::run_accuracy_test`), module lines 944.

### 1. `database.py` — split by responsibility (Priority 9)

934 lines (re-measured 2026-09-19), over the 800-line hard limit.
Schema/connection management, license-record preparation,
and query methods are still all in one file. Not a complexity offender
(no individual function stands out) — purely a file-size and
module-lines-ratchet problem.

- **Fix**: split along existing method-name groupings (e.g.
  `_prepare_*`/`_write_*` build-time methods vs. `get_*`/`search_*`
  runtime query methods) into two modules re-exported from
  `database.py`, or a `database/` subpackage per the file-size rule's
  "3+ related files → group in a same-named subfolder" convention.
  `matcher.py` (852 lines after the Java tier was removed) is now a
  candidate for the same treatment once its own complexity work has settled.
- Impact 2, Risk 1, Effort 3.

## Out of scope for now

- `cli.py::match` (McCabe 10, cognitive 20, 12 branches since
  2026-09-19) is at target except for cognitive complexity.
- `tests/test_accuracy.py::run_accuracy_test` (cognitive 29) now sets
  the repo's Cognitive ceiling — a benchmark-table-printing test helper,
  not production code. Not a priority-ranked backlog item (it isn't
  `src/`), but worth a look if the Cognitive ceiling needs to tighten
  further, since it's the actual blocker at that point.
