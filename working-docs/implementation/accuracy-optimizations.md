---
Created: 2026-05-07
Last-Modified: 2026-09-21
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
title: "Accuracy optimisations — May 2026"
---

## Accuracy optimisations — May 2026

Optimisations driven by benchmark analysis of the `20260505T095558Z` run.
All changes target accuracy without sacrificing performance.

## Changes

### 1. Deprecated ID normalisation (`identifiers.py`, `database.py`)

#### Semantic correction: bare deprecated IDs

The SPDX `+` operator (e.g. `GPL-2.0+`) unambiguously means "or any later
version". Bare deprecated IDs (e.g. `GPL-2.0`) are technically ambiguous: the
license texts of `GPL-2.0-only` and `GPL-2.0-or-later` are identical, so only
the granting declaration in a source file can distinguish them.

The DB schema reflects this: `superseded_by` is `NULL` for bare deprecated IDs
and populated only for `+`-form IDs. The resolution strategy is:

1. **DB lookup** — `+`-form IDs (e.g. `GPL-2.0+`) resolve via `superseded_by`.
2. **Prose context** — `disambiguate_deprecated_id()` scans a ±150-character
   window around a bare deprecated ID for or-later phrases
   (`"or later"`, `"or any later"`, `"or (at your option) any later"`,
   `"or newer"`) or a narrow post-ID window for `"only"`.
3. **Conservative fallback** — `DEPRECATED_BARE_LICENSE_IDS` maps bare IDs
   to `-only` when no context is available. Applied last.

Examples:

| Input | Output |
| --- | --- |
| `"GPL-2.0+"` | `"GPL-2.0-or-later"` |
| `"GPL-2.0 or later version"` | `"GPL-2.0-or-later"` |
| `"GPL-2.0 only"` | `"GPL-2.0-only"` |
| `"GPL-2.0"` (no context) | `"GPL-2.0-only"` (conservative) |

#### `+`-suffix retention for non-mapped IDs

When a `+`-suffixed ID (e.g. `"CDDL-1.0+"`, `"Apache-2+"`) is not covered by
`DEPRECATED_SPDX_LICENSE_IDS`, the base is resolved — first by exact DB lookup,
then by `get_license_by_id_prefix()` (shortest unambiguous prefix match) — and
`+` is re-attached to the canonical form.

Examples:

| Input | Output |
| --- | --- |
| `"CDDL-1.0+"` | `"CDDL-1.0+"` |
| `"Apache-2+"` | `"Apache-2.0+"` |

#### New DB helper: `get_license_by_id_prefix()`

Returns the shortest active (non-deprecated) license whose ID starts with the
given prefix, only when that match is unambiguous (unique shortest length).

### 2. FTS5 word cap reverted to 100 (`matcher.py`)

The query truncation cap was temporarily raised to 200 words. Benchmark results
show Recall@1 is flat beyond 100 words: the head of the license text provides
sufficient FTS5 signal. The cap is returned to 100 words.

### 3. Case-fold exact ID match in Tier 0 (`matcher.py`)

`_match_short_text()` now checks for an exact case-insensitive ID match in a
single pass before entering the fuzzy loop. On a hit it returns immediately
with `score=1.02`, which the Tier 0 caller uses as a definitive-result signal.
This eliminates false fuzzy-near-miss rankings for inputs like `"mit"`.

### 4. Prose disambiguation fast path in Tier 0 (`matcher.py`)

Before the short-text fuzzy loop, `match()` calls `disambiguate_deprecated_id()`
on the raw (un-normalised) input text. On a hit it performs a single DB lookup
and returns directly. The raw text is used because `normalize_text()` strips
punctuation and case that the disambiguation regexes rely on.

### 5. Marker boost guard raised to ≥ 0.85 (`matcher.py`)

The marker confidence boost in `_calculate_final_score()` previously fired for
any `marker_conf > 0`. Low-confidence markers on partial or noisy inputs caused
score distortion on Type 4 benchmark fixtures (5 %/20 % text fragments). The
guard is now `marker_conf >= 0.85`, so only reliable markers influence the
final score.

### 6. Comment-prefix stripper (`matcher.py`)

A new `_strip_comment_prefixes()` static method removes leading comment
characters (`//`, `#`, `;`, `*`, `/*`) and trailing `*/` closers from every
line. It is called:

- At the top of `_get_candidates()`, before the FTS5 query.
- Per section in `_match_mixed_content()`, before both the short-text and FTS5
  paths.

This improves recall for Type 5 inputs — license notices wrapped in source-file
comment blocks — without affecting pure-text inputs.

### 7. Short-text threshold set to 30 words (`matcher.py`)

The Tier 0 short-text fast path triggers when the input is fewer than 30
normalised words (~200 characters). Inputs at or above 30 words flow through
FTS5 as full text queries.

The threshold was briefly raised to 60 words during development but reverted
after the `20260507T120849Z` full-coverage benchmark showed a −5.5 pp top-1
regression at the 300-character input size. At 50 words (~300 chars), the
name/ID matcher returns the generic parent licence rather than a specific
variant (e.g. MIT instead of MIT-STK). Keeping the threshold at 30 words
preserves the fast path for bare IDs and short names while letting
licence-text fragments of ≥ 30 words reach the FTS5 pipeline where they
resolve correctly.

### 8. Dual FTS5 query: head + tail (`matcher.py`)

For inputs longer than 200 normalised words, `_get_candidates()` now issues two
FTS5 queries and unions the candidate sets:

- **Head query**: `words[:100]` — the preamble is the most distinctive part
  of a licence and provides good FTS5 signal in the first 100 words.
- **Tail query**: `words[-20:]` — the true last 20 words (warranty disclaimer,
  governing-law clause, closing statement) are passed directly to
  `search_candidates`, which uses the first 20 normalised words of whatever
  it receives. This surfaces licences whose preamble is generic but whose
  closing clauses are unique (e.g. `OSL-1.0`, `OSL-1.1`, `OPL-1.0`).

The 200-word threshold ensures head (`0–99`) and tail (last `20`) are
non-overlapping for any realistic input. Only one extra DB call is made, and
only when the input is long enough to benefit.

Benchmark on 695 canonical SPDX licences (FTS5 recall, in-memory DB,
`20260507T060233Z`):

| Metric | Before | After | Δ |
| :--- | ---: | ---: | ---: |
| Head top-50 recall | 98.7% | 99.9% | +1.2 pp |
| Tail top-1 recall | 39–46% | 52–57% | +10–13 pp |
| Union top-50 recall (h700+t700) | 99.4% | 100.0% | +0.6 pp |

### 9. FTS5 OR-term limit raised to 20 (`database.py`)

`search_candidates()` builds an OR query from the first N normalised words of
the input text. The limit was raised from 10 to 20 words.

This matters most for short licences in the HPND family, whose preambles all
share the first 10 words (`"permission to use copy modify and distribute this
software"`). With 10 OR terms, hundreds of indexed licences match and the
correct short licence is pushed out of the top-50. With 20 OR terms, the
additional distinctive words (unique author disclaimer text, specific scope
clauses) narrow the match set sufficiently for the correct candidate to rank.

### 10. `-only` / `-or-later` tie-breaker and its phrase detector (2026-09-21)

`GPL-2.0-only` and `GPL-2.0-or-later` have identical license bodies, so their
scores tie and the alphabetical ID tie-break would always pick `-only`. The
granting language around the text is the only evidence, and
`ranking.apply_version_suffix_tiebreaker` (called from
`AggregatedLicenseMatcher.match`) uses it.

- **Why it moves scores.** The result is a list sorted by score and
  `results[0]` is the answer, so the only lever is the score. Two scores that
  differ by less than `TIE_WINDOW` (0.01) are a tie; the preferred one gains
  `TIE_NUDGE` (0.005) and the other loses it, which together span the window.
  A swap that left the scores alone was rejected: the list would no longer be
  in score order. The costs are accepted and pinned in
  `tests/test_match_ordering.py`: reported scores move by up to 0.005, and a
  pair member can pass an unrelated license scoring within that of it.
- **The window is compared after rounding to 9 places.** `abs(a - b) > 0.01`
  let the last bit of a float decide a gap of exactly 0.01.
- **One order.** `ranking.ranking_key` is the single sort key (score with the
  deprecated penalty, then non-deprecated, then popularity if enabled, then
  ID). The re-sort used to omit the penalty.
- **One reader of "or later".** `classify.OR_LATER_PHRASE` is used by the
  tie-breaker, by `identifiers.disambiguate_deprecated_id` and by
  `markers` (which adds its own `either version` rule). Before, each had a
  regex of its own and read `or any later version`, `or a later version` and
  `or newer` differently. A bare `or later` needs a number before it (`sooner
  or later` is not a grant) and `not`/`no` directly before the phrase turns it
  off. Add a phrasing there and in `PHRASES` in
  `tests/test_match_ordering.py`, not in a fourth regex.
- **Trade-off found by the before/after run.** The GNU Free Documentation
  License's own text says "or any later version", so a slice or distorted copy
  of it (not recognised as a pure license text) now resolves to
  `-or-later` where it used to resolve to `-only`. Their bodies are identical,
  so nothing can tell the variants apart: over 3,249 license-text results
  the correct top answers went from 1,949 to 1,948 (30 `-only` rows lost it, 29
  `-or-later` rows gained it). The GPL family already behaved this way.
