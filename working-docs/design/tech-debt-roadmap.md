---
Created: 2026-08-19
Last-Modified: 2026-08-19
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Tech debt roadmap

See also: [`complexity-and-file-size-roadmap.md`](complexity-and-file-size-roadmap.md)
for code-health/complexity debt specifically. This doc tracks the rest.

Priority = (Impact + Risk) × (6 − Effort), each scored 1-5; same scale as
the complexity roadmap, so the two lists can be read together.

## 1. GPL/LGPL/AGPL family disambiguation (tail recall floor) — Priority 12

`tail_300`-`tail_500` benchmark subcategories lose 28-35 fixtures out of
top-50: GPL/LGPL/AGPL family members share boilerplate warranty text, so
a short tail-only fragment can't distinguish them by text similarity
alone.

- **Fix**: family-aware disambiguation using version number and/or the
  supersession chain (`superseded_by`) already in the DB schema, as a
  tie-breaker when top candidates are all in the same license family.
- Impact 3, Risk 3, Effort 4.
- See [`optimization-recommendation.md`](optimization-recommendation.md)
  ("Remaining open issues", item 5) for the original benchmark analysis
  this is based on — note that document predates the deprecated-ID fixes
  described in its own status note and has not been re-benchmarked since.

## 2. Probe-anchored windowing — Priority 9

The one large remaining lever on `fragment_similarity`'s dominant cost:
reuse the existing 60-word probe's match location instead of re-running
a full realignment scan. Deliberately deferred because it changes
`best_window`, which is user-facing via the CLI's `--diff` flag, not
just an internal ranking score — needs its own validation cycle (a
`bench_compare.py` run plus a manual `--diff` output quality check).

- Impact 2, Risk 2, Effort 3.
- Full plan: [`probe-anchored-windowing-plan.md`](probe-anchored-windowing-plan.md).

## 3. `new-matcher.md` — Apache-2.0 vs Pixar-style near-duplicate confusion — Priority 6

Licenses that are near-identical modifications of another license (e.g.
`Pixar` is `Apache-2.0` with a modified section 6) can be misidentified
as the parent license. See
[`new-matcher.md`](new-matcher.md) for the background analysis and word-count
statistics; no fix has been designed yet, only the problem is documented.

- Impact 2, Risk 2, Effort 4 (needs a design pass before an effort
  estimate is meaningful — treat this as provisional).

## Already resolved (kept for record)

- Type-1 `id_casing` and `id_deprecated` accuracy gaps — implemented; see
  the status note at the top of
  [`optimization-recommendation.md`](optimization-recommendation.md).
- `matcher.py`/`database.py` complexity and file size — tracked
  separately now in
  [`complexity-and-file-size-roadmap.md`](complexity-and-file-size-roadmap.md)
  rather than here, since it has its own linter-enforced ratchet.
- Stale `docs/implementation/` navigation (no current-state entry point)
  — fixed by `working-docs/implementation/README.md`.
- `requests` dependency floor, stale benchmark plan docs — resolved.
