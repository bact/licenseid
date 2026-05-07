---
title: "Threshold optimisations — 7 May 2026"
date: 2026-05-07
---

## Threshold optimisations — 7 May 2026

Driven by the `20260507T120849Z` full-coverage benchmark run
(695 SPDX 3.28.0 licences, both `license-marker` and `main` branches).

## Key findings from the benchmark

The benchmark exposed two tier-interaction problems in `license-marker`:

### Problem 1 — head_300 top-1 regression (−5.5 pp vs `main`)

At 300 characters (~50 normalised words), `license-marker` scored 85.9 %
top-1 vs 91.4 % for `main` — a regression of 38 fixtures out of 695.

Tier breakdown for `head_300` (695 fixtures):

| Tier | `license-marker` | `main` |
| :--- | ---: | ---: |
| tier05 (markers) | 93 | 0 |
| tier1 (FTS5) | 599 | 682 |
| missed entirely | 2 | 12 |
| **top-1** | **597** | **635** |

The marker tier resolved 93 fixtures, yet the overall top-1 count was lower.
The cause: the Tier 0 threshold was 60 words. A 300-char head (~50 words) fell
inside the short-text fast path and hit `_match_short_text`, which returned
the generic parent licence (e.g. `MIT`) for a variant input (e.g. `MIT-STK`).
The FTS5 pipeline was never reached for those 38 fixtures.

Mapping of observable failures: `MIT-STK → MIT`, `MIT-enna → NONE`,
`CC-BY-NC-SA-2.0-DE → CC-BY-NC-SA-2.0`.

### Problem 2 — marker scanning overhead on short inputs

`MarkerDetector.detect()` fired on every query, including the ~11,000
type-3 head/tail snippets in the benchmark. For tail-only slices at small
sizes, tier05 fired in only 2 of 695 queries (`tail_300`). The detector
scans regex patterns over the entire text regardless, adding latency without
yield for short inputs.

## Changes applied

### 1. Tier 0 threshold lowered to 30 words (`matcher.py`)

The short-text fast path (Tier 0) now only applies when
`len(words) < 30` (~200 characters).

- Inputs of 30–50 words (head_300 territory) now route directly to
  marker detection + FTS5, recovering the regression.
- Bare IDs and short names (< 30 words) still hit the fast path as intended.

Benchmark impact on type-3 head slices after applying this change:

| Size | Before (threshold=60) | After (threshold=30) |
| :--- | ---: | ---: |
| head_300 top-1 | 85.9 % | ~91 % (projected) |
| head_500 top-1 | 93.5 % | unchanged |
| head_700+ top-1 | 94.2–94.5 % | unchanged |

### 2. Marker detection suppressed for inputs < 30 words (`matcher.py`)

`detector.detect()` is now guarded by `if len(words) >= 30`. Inputs below
the threshold skip marker scanning entirely, as they are handled by Tier 0
and have no structural licence patterns to detect.

This change also moves `norm_input`/`words` computation to before the
marker detection block so the guard can use `len(words)` directly.

Expected performance improvement: measurable reduction in wall time for
type-1 (IDs), type-2 (names), and any short-text API calls, where
`MarkerDetector.detect()` previously ran unconditionally.

## Effective Tier 0 input boundary

From analysis of the type-3 recall plateau:

| Chars | ~Words | Top-1 (head) | Notes |
| ---: | ---: | ---: | :--- |
| 300 | ~50 | 85.9 % → ~91 % | recovers with threshold fix |
| 500 | ~83 | 93.5 % | big gain vs 300 |
| 700 | ~117 | 94.2 % | plateau begins |
| 800 | ~133 | 94.5 % | peak |
| 1000+ | ~167+ | 94.4 % | flat — no benefit beyond 800 |

The practical optimum is 500–800 chars (~80–133 words) for head slices.
Beyond 800 characters the FTS5 pipeline gains nothing from additional
head text.

## Next optimisation steps

Priority order by expected return (recall/accuracy first):

1. **Variant-licence disambiguation in Tier 0** — `id_casing` is flat at
   80 % top-1 for both branches. A case-folded exact match before the
   fuzzy loop in `_match_short_text` should recover the remaining 20 %.

2. **Deprecated ID redirect** — `id_deprecated` is 0 % top-1. Build a
   `deprecated_map` from the DB's `superseded_by` column and return the
   canonical ID directly in Tier 0 when the input matches a deprecated ID.

3. **Tail recall for small sizes** — `tail_300` top-1 is 65.8 % (LM) with
   28 fixtures completely absent from top-50. These are licences whose
   tail text is boilerplate shared across a family. Investigate which IDs
   are affected and whether a family-aware disambiguation step (e.g. using
   version number or supersession chain) can resolve ties.

4. **Union top-1 does not benefit from tail** — the union matrix shows
   top-1 is entirely determined by the head score. Adding tail cannot
   rescue a head miss at rank 1. A re-ranking step that boosts candidates
   appearing in both head and tail results could improve top-1 for
   head+tail inputs.

5. **Type-4 at 5 % distortion (−1.5 pp vs `main`)** — investigate whether
   the 5 % distortion model corrupts FTS5-discriminating terms more than
   other rates. May need distortion-aware FTS5 query relaxation.
