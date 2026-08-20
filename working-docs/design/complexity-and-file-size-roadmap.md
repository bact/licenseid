---
Created: 2026-08-19
Last-Modified: 2026-08-20
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
| McCabe | ≤10 | 23 | 23 (`identifiers._normalize_single_id`) |
| Cognitive | ≤15 | 49 | 49 (`markers._detect_gpl_headers`) |
| Module lines | soft 400-500 / hard 800 | 933 | 933 (`database.py`) |

Measured 2026-08-19 via `pylint --disable=all --enable=too-many-<x>
--max-<x>=1`, `flake8 --max-complexity 1` and
`flake8 --max-cognitive-complexity 1` (needs `flake8-cognitive-complexity`,
run across all of `src/`, not a single file — a single-file scan
undercounted the true max on the first pass), and `wc -l src/licenseid/*.py`.

## Backlog, priority order

Priority = (Impact + Risk) × (6 − Effort), same scoring as the general
tech-debt roadmap.

### 1. `identifiers.py::_normalize_single_id` — reduce McCabe 23 / cognitive 48 (Priority 20)

Both the single highest McCabe score in the repo *and* the second-highest
cognitive score, in one function: four sequential lookup-with-fallback
stages (DB mapping, hardcoded deprecated maps, bare-ID conservative
fallback, `+`-suffix stripping), each with its own case-insensitive
retry branch.

- **Fix**: extract a shared `_lookup_case_insensitive(mapping, key)`
  helper for the four near-identical "try exact then case-insensitive"
  blocks; collapses roughly half the branches without changing
  behaviour. Directly lowers both the McCabe and Cognitive ratchets.
- Impact 3, Risk 2, Effort 2.

### 2. `markers.py::_detect_gpl_headers` / `_detect_structured_format` (Priority 9)

`_detect_gpl_headers` is the single highest cognitive score in the repo
(49); `_detect_structured_format` is close behind (McCabe 13,
cognitive 23). Both scan license text line-by-line for multiple
heading/field patterns in one function.

- **Fix**: table-driven dispatch (list of `(pattern, handler)` pairs)
  instead of sequential `if`/`elif` pattern checks. Directly lowers the
  Cognitive ratchet, which item 1 alone won't fully resolve.
- Impact 2, Risk 1, Effort 3.

### 3. `matcher.py` — split `match()` and `_get_candidates()` (Priority 9)

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

### 4. `database.py` — split by responsibility (Priority 9)

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

## Out of scope for now

- `spdx_source.py::fetch_popularity_data` (McCabe 13) and
  `cli.py::match` (McCabe 12, cognitive 25) are close to target already
  relative to the top offenders above; revisit after items 1-4 land.
