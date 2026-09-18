---
Created: 2026-08-19
Last-Modified: 2026-09-18
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
current worst offender — trips it immediately. This doc is the backlog
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
| Args | ≤5 | 6 | 6 |
| Locals | ≤15 | 23 | 23 |
| Nesting | ≤5 | 5 (no ratchet needed) | 5 |
| Branches | ≤12 | 15 | 15 |
| Returns | ≤6 | 6 (no ratchet needed) | 5 |
| Statements | ≤50 | 50 (no ratchet needed) | 49 |
| McCabe | ≤10 | 19 | 19 (`matcher.match`) |
| Cognitive | ≤15 | 46 | 46 (`matcher.match`) |
| Module lines | soft 400-500 / hard 800 | 933 | 933 (`database.py`) |

Measured 2026-08-19 via `pylint --disable=all --enable=too-many-<x>
--max-<x>=1`, `flake8 --max-complexity 1` and
`flake8 --max-cognitive-complexity 1` (needs `flake8-cognitive-complexity`,
run across all of `src/`, not a single file — a single-file scan
undercounted the true max on the first pass), and `wc -l src/licenseid/*.py`.
McCabe row re-measured 2026-09-18 after the `identifiers.py` fix landed;
Cognitive row re-measured 2026-09-18 after the `markers.py` fix below
landed.

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
touched by this pass — see item 3 below.

### 1. `matcher.py` — split `match()` and `_get_candidates()` (Priority 9)

841 lines (over the 800-line hard target); `match()` is 178 lines /
cognitive 46 / McCabe 19, `_get_candidates()` is 136 lines / cognitive 32
/ McCabe 13. Both are Tier-dispatch functions that grew a branch per
tier as tiers were added — third on McCabe/cognitive individually, but
the only item that also blocks the module-lines ratchet.

- **Fix**: extract each tier's logic (`_try_tier0`, `_try_tier0_5`,
  `_try_tier1_and_2`, `_finalize_tier0_deprecated`, etc.) into private
  methods `match()` only calls in sequence, mirroring the natural
  Tier 0 → 0.5 → 1 → 2 → 3 pipeline structure already described in
  comments.
- Impact 3, Risk 2, Effort 3.

### 2. `database.py` — split by responsibility (Priority 9)

933 lines (down from 977 — the n-gram/IDF fingerprint math moved to
`fingerprint.py`). Schema/connection management, license-record
preparation, and query methods are still all in one file. Not a
complexity offender (no individual function stands out) — purely a
file-size and module-lines-ratchet problem.

- **Fix**: split along existing method-name groupings (e.g.
  `_prepare_*`/`_write_*` build-time methods vs. `get_*`/`search_*`
  runtime query methods) into two modules re-exported from
  `database.py`, or a `database/` subpackage per the file-size rule's
  "3+ related files → group in a same-named subfolder" convention.
- Impact 2, Risk 1, Effort 3.

### 3. `markers.py::_detect_structured_format` (Priority 6)

McCabe 13, cognitive 23 — well under the current ceilings, so not
urgent, but the smallest/cheapest item left. Parses JSON/TOML/INI file
formats for a `license` field via three separate `if` blocks (JSON
returns early; TOML/INI fall through and can both run).

- **Fix**: extract each format's parsing into its own private method
  (`_detect_json_license`, `_detect_toml_license`,
  `_detect_ini_license`), preserving the JSON early-return quirk.
- Impact 1, Risk 1, Effort 2.

## Out of scope for now

- `spdx_source.py::fetch_popularity_data` (McCabe 13) and
  `cli.py::match` (McCabe 12, cognitive 25) are close to target already
  relative to the top offenders above; revisit after items 1-3 land.
