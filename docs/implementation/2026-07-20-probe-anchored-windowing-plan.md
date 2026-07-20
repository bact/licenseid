---
title: "Probe-anchored windowing — plan"
date: 2026-07-20
status: planned
---

# Probe-anchored windowing — plan

Flagged as future work in
[`2026-07-20-speed-optimizations-round-2.md`](2026-07-20-speed-optimizations-round-2.md)
("Investigated, no action taken"). Not implemented — this document is the
plan for a later round to pick up, deliberately, with its own validation
cycle.

---

## Current bottleneck

`fragment_similarity()` (`similarity.py`) is 85%+ of total `match()` time
on realistic workloads. Measured directly: its cost scales with **query
length**, not candidate length —

```
q=80  words, cand=7244 words -> ~2ms   (any candidate length)
q=300 words, cand=464..7244  -> ~47-67ms  (roughly flat across candidate length)
```

For queries in the 120–499 normalised-word range (where `build_probe()`
currently activates), once a candidate passes the cheap 60-word probe
gate (`fuzz.partial_ratio(probe, search_text)`, ~1ms), the function still
pays the full cost of `fuzz.partial_ratio_alignment(norm_input,
search_text)` on the *entire* query — the expensive step the probe was
supposed to let us avoid, but only avoids for candidates that fail the
gate. Roughly half of gated candidates pass (~48.6% in fixture sampling),
so this remaining cost is not small.

`round-2`'s `score_cutoff` idea targeted the same function but pruned on
*score* only, which turned out to corrupt ranking among rejected
candidates for heavily-distorted input (see round-2 doc for the full
postmortem). This idea targets the same cost from a different angle —
avoiding the full-query scan's cost directly, rather than pruning around
it — and carries a different kind of risk.

---

## The idea

`fragment_similarity()` already computes `fuzz.partial_ratio(probe,
search_text)` for the gate check. Switching that to
`fuzz.partial_ratio_alignment(probe, search_text)` costs the same
(verified: alignment mode has no measurable overhead over score-only —
65.75ms vs 65.62ms for the same inputs) and additionally returns *where*
in `search_text` the probe's best match is.

Since the probe is a known slice of the full query
(`query_words[mid-half : mid+half]`, i.e. it starts `mid-half` words into
the query), its match location in the candidate can be used to estimate
where the *full* query would align, without paying for a second, larger
scan:

```python
def fragment_similarity(norm_input, search_text, probe, probe_word_offset=None):
    if probe is not None:
        probe_alignment = fuzz.partial_ratio_alignment(probe, search_text)
        probe_score = (probe_alignment.score / 100.0) if probe_alignment else 0.0
        if probe_score < PROBE_GATE:
            return probe_score, search_text

        # Estimate the full-query window from the probe's match location.
        avg_char_per_word = len(norm_input) / max(1, len(norm_input.split()))
        offset_chars = probe_word_offset * avg_char_per_word
        # Pad generously -- this is an estimate, not a search.
        pad = int(len(norm_input) * 0.2)
        start = max(0, int(probe_alignment.dest_start - offset_chars) - pad)
        end = min(len(search_text), start + len(norm_input) + 2 * pad)
        window = search_text[start:end]

        score = fuzz.token_sort_ratio(norm_input, window) / 100.0
        if score >= 0.6:
            return score, window
        # Estimate missed or scored low -- fall through to the real scan
        # rather than trust a possibly-wrong window (see Risks).

    # Existing full scan -- either no probe, estimate was inconclusive,
    # or this is the non-probe (<120 or >=500 word) path.
    alignment = fuzz.partial_ratio_alignment(norm_input, search_text)
    ...
```

`build_probe()` would need to also return `mid - half` (the probe's word
offset into the query) alongside the probe string itself, since
`fragment_similarity()` needs it to compute `offset_chars`.

If this works, candidates that pass the probe gate get scored via one
`partial_ratio_alignment` call on a **60-word probe** plus one cheap
`token_sort_ratio` call on an **estimated window**, instead of one
`partial_ratio_alignment` call on the **full query** (300+ words). Given
the query-length-driven cost profile above, this should cost close to the
probe-gate case (~1-2ms) instead of the current ~50-65ms for the ~48.6%
of candidates that pass the gate.

---

## Risks (why this wasn't just implemented)

### 1. `best_window` is user-facing, not just an internal score

Unlike `score_cutoff` (which only affected an internal ranking value for
already-rejected candidates), this changes **which substring of the
candidate gets returned** as `best_window` for *any* candidate scored
this way — including the eventual winner. `best_window` reaches the CLI's
`--diff` flag (`cli.py`'s `show_diff()`), which renders a word-by-word
diff against it. An estimated window that's shifted from the true optimal
alignment would produce a visibly worse or misleading diff even in cases
where the *score* comes out fine. The recall benchmarks (`bench_compare.py`)
do not check `best_window` at all — a regression here could pass every
existing recall check and still ship a broken `--diff` output.

### 2. The offset estimate can be wrong in ways recall benchmarks won't catch

The estimate assumes a **roughly uniform character-to-word ratio** and
that edits/distortion **before** the probe's position in the query don't
shift the corresponding position in the candidate by more than the padding
allows. Both assumptions degrade under exactly the conditions where this
path is hottest — long, moderately-distorted fragments. The `score_cutoff`
postmortem's lesson applies directly here: a change can look exact on the
happy path and still corrupt results specifically in the heavy-distortion
and mixed-content categories, which is where a naive validation pass is
least likely to probe deeply.

### 3. Interacts with the existing fallback complexity

The sketch above already includes a fallback to the full scan when the
estimated window scores below 0.6, to avoid silently returning a bad
score. That fallback needs its own reasoning about how often it fires (if
it fires for most candidates, the optimisation doesn't actually save
anything) and could reintroduce most of the cost it was meant to remove
if the estimate is unreliable often enough.

---

## Validation plan (required before implementation is considered done)

Both of these are required — recall alone is not sufficient given risk
(1) above:

1. **Recall**: full `bench_compare.py`, with specific attention to the
   heaviest-distortion tier (20%) and mixed-content categories — the same
   categories that caught the `score_cutoff` regression. A targeted
   675-fixture direct check (as used in round 2, faster than the full
   ~50-minute run) is an acceptable first pass, but the full benchmark
   should still be run before merging, matching this project's established
   bar for any change to `similarity.py`.
2. **`--diff` quality**: no existing automated check covers this. Needs
   either a new test asserting `best_window` boundaries are within some
   tolerance of a full-scan baseline on a sample of fixtures, or a manual
   review pass comparing `--diff` output before/after on a representative
   sample (verbatim, lightly distorted, and heavily distorted inputs).

---

## A lower-risk variant to consider first

Instead of *estimating* the window location from the probe, use a
**larger probe** (e.g. 150–200 words instead of 60, still drawn from a
fixed position such as the query middle) and run `partial_ratio_alignment`
on that directly — a real search, just over a smaller representative
slice of the query rather than the full 300+ words. This still changes
`best_window`/scoring (a smaller effective query than the true one) but
avoids risk (2) above entirely: the returned window is always the result
of an actual alignment search, never a positional estimate. Cost savings
are smaller (proportional to the size reduction, not to skipping the scan
entirely) but the correctness risk is much easier to reason about and
validate. Worth benchmarking as a cheaper, safer first step before
attempting the full probe-anchored version above.

---

## Expected impact (rough, unvalidated)

For the ~48.6% of 120–499-word-query candidates that currently pass the
probe gate and pay the full ~50-65ms scan: if the estimated-window
approach works as sketched, that drops to roughly the probe-gate's own
cost (~1-2ms) — a large reduction in the single largest remaining cost
in the matching pipeline. Do not treat this number as reliable; it is a
projection from the query-length-vs-cost data above, not a measurement of
the actual implementation, which does not exist yet.

## Status

Not started. Next step, if picked up: prototype the lower-risk "larger
probe" variant first, measure its actual speedup, and decide whether the
full estimated-window version is worth the additional risk and validation
cost before attempting it.
