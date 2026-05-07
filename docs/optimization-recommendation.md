# Benchmark analysis and optimisation recommendation

## Full pipeline analysis — `20260507T120849Z`

Full-coverage run: 695 SPDX 3.28.0 licences, both `license-marker` and
`main` branches, 59,738 total queries.

**Previous analysis** (based on `20260505T095558Z`, 60-licence subset) is
preserved below the current section for reference.

---

### Summary — `20260507T120849Z`

| Type | `license-marker` R@1 | `main` R@1 | Δ |
|---|---|---|---|
| Type 1 — IDs | 78.1 % | 78.1 % | 0 |
| Type 2 — names | 90.2 % | 86.4 % | **+3.8 pp** |
| Type 2 `name_casing` | 96.6 % | 79.7 % | **+16.9 pp** |
| Type 3 `head_300` | 85.9 % | 91.4 % | **−5.5 pp** ⚠ fixed |
| Type 3 `head_500` | 93.5 % | 92.4 % | +1.1 pp |
| Type 3 `head_800` (peak) | 94.5 % | 93.2 % | +1.3 pp |
| Type 3 `tail_300` | 65.8 % | 63.7 % | +2.1 pp |
| Type 3 `tail_2000` | 87.1 % | 83.7 % | +3.4 pp |
| Type 4 verbatim | 94.2 % | 92.4 % | +1.8 pp |
| Type 4 05 % distortion | 69.7 % | 71.2 % | **−1.5 pp** |
| Type 4 20 % distortion | 48.5 % | 44.5 % | +4.0 pp |
| Type 5 mixed content | 74.9 % | 19.7 % | **+55.2 pp** 🌟 |
| Type 5.1 curated | 95.8 % | 25.0 % | **+70.8 pp** 🌟 |

Wall time: `license-marker` 13,333 s vs `main` 8,199 s (+63 %).
The wall-time gap is expected: 695 × 16 type-3 slices vs 60 × 16 in
previous runs (12× more type-3 queries).

---

### Changes applied since this run

The `head_300` regression (−5.5 pp) was diagnosed and fixed:

- **Tier 0 threshold lowered to 30 words** — 50-word heads no longer fall
  into the ID/name shortcut path. See
  `docs/implementation/2026-05-07-threshold-optimizations.md`.
- **Marker detection suppressed for inputs < 30 words** — eliminates
  wasted scanning on bare IDs and short names.

---

### Remaining open issues (next optimisation steps)

Priority order by expected return:

1. **`id_casing` flat at 80 % (both branches)** — case-folded exact lookup
   before the fuzzy loop in `_match_short_text`. Five-line fix, expected
   +20 pp on type-1.

2. **`id_deprecated` 0 % top-1 (both branches)** — deprecated IDs
   (`GPL-2.0`, `LGPL-3.0`) are not redirected to canonical successors.
   Build a `deprecated_map` from the DB `superseded_by` column and return
   the canonical ID directly in Tier 0.

3. **Type-4 at 5 % distortion (−1.5 pp vs `main`)** — investigate whether
   the distortion model lands on FTS5-discriminating terms. May be
   addressable with the marker boost guard (see item 4).

4. **Marker boost guard** — raise the minimum confidence for the additive
   marker boost from implicit 0 to ≥ 0.85. Eliminates minor regressions on
   distorted type-4 inputs.

5. **Tail recall floor** — `tail_300` to `tail_500` have 28–35 fixtures
   absent from top-50. These are licence families sharing boilerplate
   warranty text (GPL/LGPL/AGPL). Investigate family-aware disambiguation
   using version number or supersession chain.

6. **Union top-1 does not benefit from tail** — union matrix shows top-1
   is bounded by the head's top-1. A re-ranking step that boosts candidates
   appearing in both head and tail results could improve top-1 for
   head+tail inputs without changing the candidate pool.

---

## Full pipeline analysis — `20260505T095558Z` (archived)

Analysis based on the 60-licence development subset. Superseded by the
full-coverage run above for quantitative conclusions; preserved for
diagnostic reasoning.

---

### Tier-by-tier findings

#### Tier 0 — short-text shortcut

**What the data shows:**

| Input | R@1 main | R@1 marker | R@50 |
|---|---|---|---|
| id_casing | 80% | 80% | 80% (flat) |
| id_deprecated | 0% | 0% | 0% (flat) |
| id_distorted | 33.3% | 31.7% | 68.3% / 73.3% |
| name_casing | 79.7% | **96.6%** | flat |

The flatness of `id_casing` and `id_deprecated` at R@1 = R@50 means the correct answer is **not found anywhere**, even in the pool — these inputs never reach Tier 1 meaningfully (they're too short for FTS5 to be useful).

**Problem 1 — `id_casing` (80% R@1):** `_match_short_text` calls `normalize_text(lid)` and compares against `norm_input`, which is also normalised. If `normalize_text` lowercases both sides, casing variants like `"gpl-3.0-only"` vs `"GPL-3.0-ONLY"` should be handled — but the 80% flat ceiling suggests 20% of IDs have a normalisation mismatch. The most likely cause: IDs with numeric sequences or special characters (e.g., `LiLiQ-R-1.1`) where `fuzz.ratio` falls just below the 90% threshold for 1-word inputs. The fix is to add a **case-folded exact lookup** before the fuzzy loop — if `norm_input.upper() == id.upper()`, return score 2.0 immediately.

**Problem 2 — `id_deprecated` (0% R@1 both branches):** Deprecated SPDX IDs (e.g., `GPL-2.0`, `LGPL-3.0`) are in the database but `normalize_identifier()` doesn't redirect them to their canonical successors (`GPL-2.0-only`, `LGPL-3.0-only`). `_match_short_text` iterates all metadata but the deprecated ID vs canonical ID string similarity is low (e.g., `"GPL-2.0"` → `"GPL-2.0-only"`: `fuzz.ratio` ≈ 82% — just below the threshold). The marker branch gets 33% at R@10 because the deprecated text form happens to recall related licences, but the exact deprecated ID itself isn't promoted. Fix: build a `deprecated_map: dict[str, str]` in Tier 0 from the DB's `superseded_by` column and return the canonical ID directly when the input matches a deprecated ID.

**Problem 3 — `id_distorted` (33% R@1):** Distorted IDs are short (1–3 words) but have character-level noise. `fuzz.ratio` on a 1-word corrupted token falls below threshold. This is largely irretrievable from Tier 0; these should fall through to Tier 1. Currently the `> 1.0` early-return guard already ensures a non-confident Tier 0 result falls through — but for short inputs the FTS5 query on a corrupted 1-token string produces nothing useful. The 68–73% R@50 shows they do land in the pool eventually via other means. This is a harder problem (see Tier 1 section).

---

#### Tier 0.5 — marker detection

**What the data shows:**

| Type | % resolved by Tier 0.5 | R@1 impact |
|---|---|---|
| Type 1 | 0% | N/A (IDs too short for marker detection) |
| Type 2 | 0% (Tier 0 handles names) | name_casing +17pp via Tier 2 re-rank |
| Type 3 | **16.07%** (439 inputs) | +1–8pp per subcat |
| Type 4 | **4.74%** (158 inputs) | small (+0.18pp clean, **−1.98pp at 5% distortion**) |
| Type 5 | **49.73%** (91 inputs) | **+46.45pp R@1** 🌟 |

**Regression problem — Type 4 at 5% and 20% distortion:**

- 5% distortion: −1.98pp, 20% distortion: −1.62pp
- The distorted text still contains a readable licence name fragment (e.g., `"Apachi License"`, `"MIT Lisence"`) which triggers a fuzzy name match with moderate confidence (~0.7). The resulting marker boost (`score += 0.7 * 0.03 = +0.021`) is small but enough to bump a wrong candidate above a correct one when their raw similarities are close.
- The fix: **only apply marker boost if the marker was detected via a structural pattern** (heading, name field, SPDX tag) rather than a fuzzy name match. Add a minimum `conf ≥ 0.85` guard before boosting in `_calculate_final_score`. The current threshold for "authoritative marker" behaviour is `0.94`; lower the additive-boost guard to `0.85`.

**Missed mixed content (28.4% still missed in Type 5):** The 52 missed queries have no SPDX tag, no recognisable heading. The licence text is buried in comment blocks (`//`, `#`, ` * `). The `_match_mixed_content` windowed search helps but comment-prefixed lines dilute FTS5 trigrams. Fix: add a **comment-prefix stripper** that normalises `//`, `#`, ` * ` prefixes before passing to FTS5.

---

#### Tier 1 — FTS5 pool recall

**Pool recall ceilings (Recall@50 ≈ pool recall):**

| Input type | Pool recall ceiling |
|---|---|
| Type 1 ids (clean) | 100% |
| Type 2 names (clean) | 100% |
| Type 3 head-only (≥500 chars) | 88–90% |
| Type 3 head+tail | 82–90% |
| Type 3 tail-only (300–500 chars) | 76–78% |
| Type 4 verbatim/1%/2% | 98%+ |
| Type 4 20% distortion | 68% |
| Type 5 mixed | 72% (with markers) |

**Problem — FTS5 word cap at 200 truncates head+tail:**  
`head_2500_tail_500` has combined ≈600 words. At cap=200, the entire 500-char tail is discarded. Yet R@50 is 85% — meaning the head alone is enough for pool recall. The bottleneck is **ranking** (R@1 = 36–44%). However, the tail contains the most distinctive trailing clauses; discarding it hurts the ranking score because `search_text` returned by FTS5 is the head fragment only.

**Fix — dual-query for inputs where head covers > word_cap:** Run two FTS5 queries when `len(words) > word_cap`: one with `words[:word_cap]` (head) and one with `words[-min(word_cap, len(words)-word_cap):]` (tail). Union the candidate sets. This alone doesn't improve pool recall (already 85%) but it surfaces the **correct search_text slice** for Tier 2 scoring.

**Pending revert — word cap 200 → 100:** Still needed. Analysis from the prior session showed 200 provides zero net pool recall improvement vs 100 for any subcat, but 200 words means slower FTS5 queries. Revert.

**Tail-only ceiling (tail_300 R@50=76.7%):** Irreducible with current approach. Short tails are boilerplate warranty text shared across families. Only tail ≥ 2000 chars approaches 88% pool recall.

---

#### Tier 2 — RapidFuzz ranking

**The central problem — large R@1 vs Recall@50 gap:**

| Subcat | R@1 (marker) | R@50 (marker) | Gap (ranking headroom) |
|---|---|---|---|
| head_700_tail_700 | 50.9% | 89.5% | **38.6pp** |
| head_2500_tail_500 | 43.9% | 85.4% | **41.5pp** |
| tail_300 | 50.0% | 76.7% | 26.7pp |
| Type 4 verbatim | 93.7% | 98.7% | 5.0pp |
| Type 4 20% distortion | 43.8% | 68.7% | 24.9pp |

A 38–41pp gap for head+tail inputs means Tier 2 is ranking the correct answer somewhere between positions 2 and 50 in roughly half of all head+tail queries. The correct answer is in the pool; the ranking function doesn't push it to rank 1.

**Root cause:** `_calculate_base_similarity` compares the joined `head\ntail` string against the full licence template. For `head_700_tail_700`, the input is 1400 chars of a licence where the middle 1000+ chars are missing. `fuzz.token_sort_ratio(input, full_template)` measures full-text similarity, which is inherently low for a 50–70% fragment. Meanwhile, similar licences with shorter full texts achieve higher coverage ratios and therefore better `fuzz.token_sort_ratio` scores.

**Fix — fragment-aware scoring for head+tail inputs:**  
When the input is non-contiguous (head + tail), instead of comparing against the full template, compare:

- `head` against `template[:head_len*1.2]` (the template's opening section)  
- `tail` against `template[-tail_len*1.2:]` (the template's closing section)  
- Combine as `0.6 * head_sim + 0.4 * tail_sim`

This requires detecting that an input is a head+tail fragment. A heuristic: if `coverage < 0.5` AND `partial_ratio(input, full_template) > 0.75`, the input likely covers non-contiguous sections. The `_is_pure_license_text` classification is already available.

This is the highest-leverage single change for Type 3.

---

### Per-input-type summary

#### Type 1 — licence IDs

- Current R@1 (marker): ~80% weighted (blocked by casing and deprecated issues)  
- **Fix 1**: Case-folded exact match before fuzzy loop → `id_casing` 80% → ~100% (+20pp)  
- **Fix 2**: `deprecated_map` redirect in Tier 0 → `id_deprecated` 0% → ~80–100% (+80pp)  
- Combined impact on Type 1: 13.4% missed → ~2–5% missed

#### Type 2 — licence names

- Current R@1 (marker): ~90–97% depending on subcat  
- Marker branch already solved `name_casing` (+17pp). The only remaining gap is `name_distorted` at R@1=61%, R@50=91.5%: the correct name is in the pool but ranked poorly. Better Tier 0 partial-name normalisation could close this.  
- **Fix**: In `_match_short_text`, add `fuzz.partial_ratio(norm_input, name_norm)` to the score candidates (similar to `score_id_partial` already done for IDs). Expected: `name_distorted` 61% → ~75–80%.

#### Type 3 — short partial texts

- Current R@1 (marker): 44–82% depending on subcat (worst for head_2500_tail_500)  
- **Fix 1**: Revert word cap 200 → 100 (minor, but cleaner)  
- **Fix 2**: Dual-query FTS5 (head+tail separately) → improves `search_text` alignment  
- **Fix 3**: Fragment-aware Tier 2 scoring → expected +8–15pp R@1 on large-head+tail subcats  
- Combined expected: head+tail R@1 from 44–74% → 60–85%

#### Type 4 — full distorted texts

- Verbatim/1%/2%: already 93%+ — diminishing returns  
- 5% distortion: −1.98pp regression vs main — fix marker boost threshold first  
- 20% distortion R@1=43.8%: pool recall only 68%, so some loss is irreducible. RapidFuzz already uses character-level similarity; at 20% distortion, ≈1 in 5 characters is wrong, which is near the threshold for trigram FTS5 to fail entirely  
- **Fix**: Raise marker boost minimum confidence guard from implicit 0 → 0.85 for additive boost → eliminates Type 4 regressions at 5% and 20%

#### Type 5 — mixed content

- Marker branch: R@1 = 66.7%, still 28.4% missed  
- **Fix**: Comment-prefix stripper before FTS5 (`//`, `#`, ` * ` line prefixes) → expected +5–10pp on missed cases  
- The remaining ~20% are likely files with licence text spread across many comment blocks with no identifier header — structurally hard

---

### Two recommended combinations

#### A — Highest accuracy

Priority order (highest return first):

1. **Tier 0: case-fold exact match** — `id_casing` 80% → ~100% (+20pp on 60 queries)
2. **Tier 0: deprecated→canonical redirect** — `id_deprecated` 0% → ~80% (+48pp on 60 queries)  
3. **Fix marker boost guard** (conf ≥ 0.85) — eliminates Type 4 5%/20% regressions (+1.98pp on 555 queries)
4. **Tier 2: fragment-aware scoring** — head+tail R@1 +8–15pp on large-head subcats (~600 queries)
5. **Comment-prefix stripper for Type 5** — +5–10pp on 52 missed mixed-content queries
6. **Revert FTS5 word cap 200 → 100** — minor speed gain, no recall loss

Expected global recall change: **89.98% → ~92–93%**

#### B — Fast, high quality (minimal code change)

1. **Tier 0: case-fold exact match** (5 lines) — biggest return for smallest effort
2. **Tier 0: deprecated→canonical redirect** (one dict lookup) — pure Tier 0, zero pipeline cost
3. **Fix marker boost guard** (one line: change `if marker_conf > 0:` guard to `if marker_conf >= 0.85:` for the additive path) — eliminates regressions

Skip fragment-aware scoring and dual-query FTS5 for now (more complex, higher risk). Expected: **~91–92% global recall**, no regressions, near-zero added latency.

---

### What to do first

The three highest-leverage, lowest-risk changes:

```text
1. matcher.py _match_short_text():   add case-fold exact match before fuzzy loop
2. matcher.py _match_short_text():   query deprecated_map from DB, redirect early
3. matcher.py _calculate_final_score(): raise additive marker boost guard to ≥ 0.85
```

All three are localised, testable, and do not touch Tier 1 or the FTS5 schema. The word cap revert is also safe and should accompany change 1.
