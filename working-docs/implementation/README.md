---
Created: 2026-08-19
Last-Modified: 2026-08-19
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Implementation history — index

This directory is a chronological record of what was built, decided, and
why — not a user manual and not a roadmap. For planned/deferred work not
yet started, see [`../design/`](../design/).

## Current state (as of 2026-07-20)

- **Pipeline**: Tier 0 (short-text ID/name shortcut) → Tier 0.5 (marker
  detection) → Tier 1 (SQLite FTS5 recall) → Tier 2 (RapidFuzz ranking) →
  optional Tier 3 (Java `tools-java` validation).
- **Deprecated ID handling**: DB-backed `superseded_by` redirect for
  unambiguous cases (e.g. `GPL-2.0+` → `GPL-2.0-or-later`); conservative
  `-only` fallback for bare ambiguous IDs (e.g. `GPL-2.0`) with no
  granting-context phrase in the input. Applied consistently across the
  explicit `license_id=` path, prose-disambiguated free text, and bare
  free-text Tier 0 lookups.
- **Discriminative n-gram fingerprints**: precomputed at DB-build time,
  used as an additive tie-breaker in Tier 2 ranking.
- **Known deferred work**: probe-anchored windowing (reusing the existing
  probe's match location instead of a full realignment scan) — flagged
  but deliberately not attempted; see
  [`../design/probe-anchored-windowing-plan.md`](../design/probe-anchored-windowing-plan.md).
  For the full prioritised backlog, see
  [`../design/tech-debt-roadmap.md`](../design/tech-debt-roadmap.md) and
  [`../design/complexity-and-file-size-roadmap.md`](../design/complexity-and-file-size-roadmap.md).

## Chronology

| Date | Doc | Status | Summary |
|---|---|---|---|
| 2026-04-28 | [performance-optimization.md](performance-optimization.md) | implemented | Initial matching-pipeline tuning: FTS5 query truncation, Tier 1 candidate limit 20→50, adaptive RapidFuzz rule selection, coverage-aware composite scoring. |
| 2026-05-06 | [accuracy-optimizations.md](accuracy-optimizations.md) | implemented | Deprecated-ID normalisation semantics: DB-lookup-first, `-only` conservative fallback for ambiguous bare IDs. |
| 2026-05-07 | [threshold-optimizations.md](threshold-optimizations.md) | implemented | Diagnosed and fixed the `head_300` Tier 0/0.5 regression from the full-coverage benchmark: lowered Tier 0 threshold to 30 words, suppressed marker detection below that. |
| 2026-05-07 | [speed-optimizations.md](speed-optimizations.md) | implemented (as PR #19, PR #21) | Original plan for discriminative n-gram fingerprints and pre-computed-normalization/RapidFuzz acceleration; superseded in narrative detail by the round-2 doc's results. |
| 2026-07-20 | [speed-optimizations-round-2.md](speed-optimizations-round-2.md) | implemented | Profile-driven sweep: DB index on `licenses.name`, removed redundant lookups, lazy imports, instance-level metadata caching, `mmap_size` pragma. One change (`score_cutoff` on `partial_ratio_alignment`) was tried and reverted — see its "Rejected" section. CLI cold start ~125ms → ~31ms. |

Deferred/not-yet-built work (e.g. probe-anchored windowing) lives under
[`../design/`](../design/), not in this table — this directory only
records what shipped.

## Conventions used across these docs

- Frontmatter: `Created`/`Last-Modified` dates plus SPDX tags on every
  file; some carry an additional `title`/`status` pair from an earlier
  convention.
- `status: planned` means proposed but not yet implemented at time of
  writing; check the Chronology table above for the current status, since
  a later doc may report the outcome without the original doc being
  updated in place.
