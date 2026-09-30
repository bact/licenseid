# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Stateless similarity scoring for Tier 2 (RapidFuzz) license matching.

Pure functions of their arguments only -- no database or matcher instance
state -- so they can be tested and reused independently of
AggregatedLicenseMatcher.
"""

import math

from rapidfuzz import fuzz

from licenseid.types import CandidateMatch, InternalMatch

# Probe-gate settings for fragment ranking (query shorter than candidate).
# A full partial_ratio scan of a weak candidate hits RapidFuzz's worst case
# (~50-80 ms per candidate) because no window aligns well.  Scanning with a
# short sample of the query first costs ~80x less, and its score tracks the
# full-fragment score closely: in fixture sampling (incl. distorted inputs)
# no candidate below _PROBE_GATE ever reached the 0.6 alignment threshold.
# Only candidates that pass the probe get the full alignment scan.
PROBE_WORDS: int = 60  # probe sample size (words, taken from query middle)
PROBE_GATE: float = 0.52  # min probe score to run the full alignment scan

# What the full alignment scan and the probe may cost. RapidFuzz's cost grows
# with the query's length in CHARACTERS, whatever they are (per candidate,
# against a licence of 18,000 characters: 700 chars 7 ms, 2,150 chars 124 ms,
# 4,000 chars 758 ms), and so does the probe's. Word counts alone let a blob
# (a long token, embedded base64) of few words and many characters through,
# and characters per word is no better a guide: Japanese and Chinese are
# written without spaces, so their "words" are long too. So:
# - a query of ALIGN_UNPROBED_MAX_CHARS or more always has a probe, cut by
#   characters when it has too few words for the word probe;
# - a probe is at most PROBE_MAX_CHARS long: its cost per candidate jumps
#   past about 500 characters (15 ms at 500, 43 ms at 600, 136 ms at 1,000).
#   Only 16 fixture probes are longer, all Japanese or Chinese; trimming them
#   keeps every one's top answer;
# - the scan takes a query of at most ALIGN_MAX_CHARS (fixture maximum in the
#   probed range: 5,478) and fewer than ALIGN_MAX_WORDS words; a longer one is
#   scored with token_sort_ratio.
ALIGN_MAX_WORDS: int = 500
ALIGN_MAX_CHARS: int = 6000
ALIGN_UNPROBED_MAX_CHARS: int = 1500
PROBE_MAX_CHARS: int = 500


def _center(text: str, size: int) -> str:
    """The middle *size* characters of *text* (all of it if shorter)."""
    if len(text) <= size:
        return text
    start = (len(text) - size) // 2
    return text[start : start + size]


def build_probe(query_words: list[str]) -> str | None:
    """Build the mid-query probe sample used by fragment_similarity().

    The middle PROBE_WORDS words of a query of 120 to 499 words, or the
    middle characters of a shorter one that is long in characters; at most
    PROBE_MAX_CHARS either way. None when the query is short enough to scan
    without one, or too long to be scanned at all (see alignment_affordable).
    """
    q_len = len(query_words)
    if q_len >= ALIGN_MAX_WORDS:
        return None
    if q_len >= PROBE_WORDS * 2:
        mid = q_len // 2
        half = PROBE_WORDS // 2
        return _center(" ".join(query_words[mid - half : mid + half]), PROBE_MAX_CHARS)
    text = " ".join(query_words)
    if len(text) < ALIGN_UNPROBED_MAX_CHARS:
        return None
    return _center(text, PROBE_MAX_CHARS)


def alignment_affordable(norm_input: str, q_len: int) -> bool:
    """Whether the full alignment scan of *norm_input* (*q_len* words) is
    affordable; the one judge of it. See ALIGN_MAX_CHARS."""
    return q_len < ALIGN_MAX_WORDS and len(norm_input) <= ALIGN_MAX_CHARS


def fragment_similarity(
    norm_input: str,
    search_text: str,
    probe: str | None,
) -> tuple[float, str]:
    """Similarity for fragment inputs (query shorter than candidate).

    Probe gate first: a short mid-query sample scans the candidate ~80x
    faster than the full fragment.  Weak candidates (probe score below
    PROBE_GATE) are scored by the probe alone and never pay for the
    full O(q x c) scan.  Candidates that pass get a single alignment
    pass (score + window in one scan) followed by a token_sort_ratio
    re-score of the aligned window.

    Do NOT pass score_cutoff=60 to the alignment call below as a "free"
    speedup (tried and reverted): it makes RapidFuzz return None -- and
    this function flatten the score to a bare 0.0 -- for every candidate
    that doesn't clear 60, rather than their true score.  That looks safe
    (candidates below 0.6 never win the top rank) but isn't: for heavily
    distorted input the TRUE match itself often legitimately scores below
    60, and flattening its score to 0.0 destroys its ranking relative to
    every other sub-60 candidate, which now also reads as 0.0.  Full
    bench_compare caught this as a real regression concentrated exactly
    where predicted -- the heaviest-distortion tier and mixed-content
    fixtures -- down up to -7.93 pts at deeper Recall@N, while low/no
    distortion stayed at +0.00. Confirmed by reverting: regression gone.
    """
    if probe is not None:
        probe_score = fuzz.partial_ratio(probe, search_text) / 100.0
        if probe_score < PROBE_GATE:
            return probe_score, search_text

    alignment = fuzz.partial_ratio_alignment(norm_input, search_text)
    fast_score = (alignment.score / 100.0) if alignment else 0.0
    if fast_score >= 0.6 and alignment:
        best_window = search_text[alignment.dest_start : alignment.dest_end]
        return fuzz.token_sort_ratio(norm_input, best_window) / 100.0, best_window
    return fast_score, search_text


def calculate_base_similarity(
    norm_input: str,
    q_len: int,
    q_tokens: set[str],
    cand: CandidateMatch,
    probe: str | None = None,
) -> tuple[float, float, str]:
    """Calculate base similarity and coverage for a candidate."""
    search_text = cand.get("search_text") or ""
    c_len = cand.get("word_count") or 0
    if c_len == 0:
        c_len = len(search_text.split())

    similarity = 0.0
    best_window = search_text

    if norm_input == search_text:
        similarity = 1.0
    elif q_len >= c_len * 0.8 or not alignment_affordable(norm_input, q_len):
        similarity = fuzz.token_sort_ratio(norm_input, search_text) / 100.0
    else:
        similarity, best_window = fragment_similarity(norm_input, search_text, probe)

    # Semantic Safeguards
    if 0.90 < similarity < 1.0:
        critical_tokens = {"not", "except", "unless", "irrevocable"}
        c_tokens = set(search_text.split())
        for token in critical_tokens:
            if (token in q_tokens) != (token in c_tokens):
                similarity *= 0.95

    coverage = (q_len / c_len) if c_len > 0 else 0.0
    return similarity, coverage, best_window


def calculate_final_score(
    match: InternalMatch,
    boosts: dict[str, float],
    is_pure: bool,
    enable_popularity: bool,
    q_len: int = 0,
) -> float:
    """Calculate the final adjusted score for a match."""
    similarity = match["base_score"]
    coverage = match["coverage"]

    # Fragment inputs (coverage < 0.5) are known to be incomplete slices
    # of a longer license text.  Penalising them for low coverage creates a
    # systematic bias against the correct candidate when several licenses
    # share a common preamble.  Suppress the penalty for fragments and keep
    # it only for inputs that are near-full texts (0.5 ≤ coverage < 0.8).
    # Reference: Type 3 benchmark results (head+tail combinations).
    if coverage < 0.5:
        coverage_penalty = 0.0
    elif coverage < 0.8:
        coverage_penalty = (1.0 - coverage) * 0.02
    else:
        coverage_penalty = 0.0
    coverage_bonus = 0.005 if 0.95 <= coverage <= 1.05 else 0.0

    score = similarity - coverage_penalty + coverage_bonus

    if enable_popularity:
        score += math.log10(max(1, match["pop_score"])) * 0.0001

    marker_conf = boosts.get(match["license_id"], 0.0)
    if marker_conf >= 0.85:
        # Require confidence >= 0.85 before applying any marker boost.
        # Low-confidence markers (< 0.85) on e.g. partial / noisy inputs
        # caused score distortion on Type 4 inputs in benchmarks.
        # For long pure license text with moderate-confidence markers,
        # similarity dominates; use a small additive boost only.
        # For mixed content, short text, OR high-confidence structural
        # detection (>= 0.94, e.g. BSD/GPL header analysis), the marker
        # is authoritative — apply an additive boost plus a confidence
        # floor.
        if is_pure and q_len >= 50 and marker_conf < 0.94:
            score += marker_conf * 0.03
        else:
            score = max(score + marker_conf * 0.05, marker_conf * 0.95)

    return score
