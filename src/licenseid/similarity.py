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
from typing import Optional

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


def build_probe(query_words: list[str]) -> Optional[str]:
    """Build the mid-query probe sample used by fragment_similarity().

    Only useful when the query is long enough that the probe is a real
    subsample; short queries scan fast without it (see fragment_similarity's
    q_len < 500 branch, which is where probes apply).
    """
    q_len = len(query_words)
    if not PROBE_WORDS * 2 <= q_len < 500:
        return None
    mid = q_len // 2
    half = PROBE_WORDS // 2
    return " ".join(query_words[mid - half : mid + half])


def fragment_similarity(
    norm_input: str,
    search_text: str,
    probe: Optional[str],
) -> tuple[float, str]:
    """Similarity for fragment inputs (query shorter than candidate).

    Probe gate first: a short mid-query sample scans the candidate ~80x
    faster than the full fragment.  Weak candidates (probe score below
    PROBE_GATE) are scored by the probe alone and never pay for the
    full O(q x c) scan.  Candidates that pass get a single alignment
    pass (score + window in one scan) followed by a token_sort_ratio
    re-score of the aligned window.
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
    probe: Optional[str] = None,
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
    elif q_len >= c_len * 0.8:
        similarity = fuzz.token_sort_ratio(norm_input, search_text) / 100.0
    else:
        if q_len < 500:
            similarity, best_window = fragment_similarity(
                norm_input, search_text, probe
            )
        else:
            similarity = fuzz.token_sort_ratio(norm_input, search_text) / 100.0

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
