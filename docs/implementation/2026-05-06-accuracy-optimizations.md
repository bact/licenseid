---
title: "Accuracy optimisations — May 2026"
date: 2026-05-06
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
