# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Stateless similarity scoring for Tier 2 (RapidFuzz) license matching.

Pure functions of their arguments only -- no database or detector instance
state -- so they can be tested and reused independently of
LicenseDetector.
"""

import math
from collections.abc import Callable
from collections.abc import Set as AbstractSet
from typing import Final, NamedTuple, Protocol
from unicodedata import east_asian_width

from rapidfuzz import fuzz

from licenseid import regionalign
from licenseid.textgrams import CRITICAL_TOKENS, whole_tokens
from licenseid.types import CandidateMatch, InternalMatch, TextParts

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

# How long an input must be for its text similarity to count in full. The
# alignment scores a fragment against the best window of a licence, so a
# word that occurs anywhere in a long licence ("foo", "copyright notice")
# is a perfect match. Below this length the score is scaled down in
# proportion (text_evidence). Measured in columns, where a wide East Asian
# character takes two: Japanese and Chinese say in one character what
# English says in several. 40 lets a fragment of 34 columns or more pass the
# 0.85 threshold: the Japanese title line of CC-BY-SA-2.1-JP (35) still
# answers; "著作権" (6) and "版权所有" (8), which a licence text holds, do
# not. No licence text is this short (the shortest, diffmark, is 81).
# detect() matches no Latin input of under ten words as text unless
# resolve() reads it (licenseid.resolvefirst), so for one this scale only
# touches ten words or more in under 40 columns; Han and kana are not cut.
EVIDENCE_COLUMNS: int = 40


# A licence text of the List may hold parts a copy leaves out (Apache-2.0's
# appendix, the whole GPL-3.0 inside LGPL-3.0): its core is the text without
# them (licenseid.coretext). An input of about the core's length is scored
# against the core as well, by token_sort_ratio alone (no alignment), and the
# higher similarity counts. About: each has at least this share of the other's
# words. The share is the one of the near-full-text rule below (``q_len >=
# c_len * 0.8``): shorter, an input is a fragment of the core; longer, it holds
# more than the core (the optional parts, which the whole text has), and
# scoring it twice would double the cost of a long input for nothing.
CORE_MIN_SHARE: float = 0.8


class Regions(Protocol):  # pylint: disable=too-few-public-methods
    """Where a candidate's text holds the input (``licenseid.wordregion``)."""

    def region(self, license_id: str, text: str) -> tuple[int, int] | None:
        """The slice of *text* (the text of *license_id*) to align the input
        with, or None for the whole text."""


class Query(NamedTuple):
    """One input as Tier 2 reads it, made once per call (:func:`query_of`)."""

    #: The normalised input.
    text: str
    #: Its words (split on white space).
    words: int
    #: Its distinct words.
    tokens: AbstractSet[str]
    #: The probe sample (build_probe).
    probe: str | None
    #: Where each candidate's text holds the input; None: the whole text.
    regions: Regions | None = None
    #: Widen an aligned window to whole words (``--diff`` shows it so).
    snap: bool = False
    #: A character the input does not hold (``regionalign.aligned``).
    wall: str = "\0"
    #: What this call has already scored, by what the score depends on (the
    #: text, never the licence): licences that share one text are scored
    #: once (:func:`_scored_once`). None: nothing is kept.
    done: dict[tuple[object, ...], tuple[float, str]] | None = None


def query_of(
    norm_input: str, regions: Regions | None = None, *, snap: bool = False
) -> Query:
    """*norm_input* ready for :func:`calculate_base_similarity`."""
    words = norm_input.split()
    held = set(norm_input)
    wall = next(chr(code) for code in range(len(held) + 1) if chr(code) not in held)
    probe = build_probe(words)
    return Query(norm_input, len(words), set(words), probe, regions, snap, wall, {})


def _scored_once(
    query: Query,
    key: tuple[object, ...],
    score: Callable[[], tuple[float, str]],
) -> tuple[float, str]:
    """``score()``, or what it gave for *key* earlier in this call: a score
    of the input depends on the text compared (and where the words locate the
    input in it), never on the licence that holds it, so twins (licences of
    one normalised text) pay for one alignment."""
    if query.done is None:
        return score()
    if key not in query.done:
        query.done[key] = score()
    return query.done[key]


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
    without one, or of ALIGN_MAX_WORDS words or more. A query too long in
    characters to scan still gets one; alignment_affordable keeps it unused.
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


def text_evidence(norm_input: str) -> float:
    """How far a text similarity of *norm_input* counts, from 0 to 1: its
    length in columns over EVIDENCE_COLUMNS, at most 1."""
    if len(norm_input) >= EVIDENCE_COLUMNS:
        return 1.0  # a column count is never below the character count
    columns = sum(2 if east_asian_width(ch) in ("W", "F") else 1 for ch in norm_input)
    return min(1.0, columns / EVIDENCE_COLUMNS)


def alignment_affordable(norm_input: str, q_len: int) -> bool:
    """Whether the full alignment scan of *norm_input* (*q_len* words) is
    affordable; the one judge of it. See ALIGN_MAX_CHARS."""
    return q_len < ALIGN_MAX_WORDS and len(norm_input) <= ALIGN_MAX_CHARS


def fragment_similarity(
    query: Query, license_id: str, search_text: str
) -> tuple[float, str]:
    """Similarity for fragment inputs (query shorter than candidate).

    Where the input's words locate it in the text (*query*'s ``regions``,
    ``licenseid.wordregion``), the character steps run on that region only:
    their cost follows the characters of both sides. Otherwise on the whole
    text, with the probe gate first: a short mid-query sample scans the
    candidate ~80x faster than the full fragment. Weak candidates (probe
    score below PROBE_GATE) are scored by the probe alone and never pay for
    the full O(q x c) scan. Candidates that pass, or are located, get a
    single alignment pass (score + window in one scan) followed by a
    token_sort_ratio re-score of the aligned window.

    Do NOT pass score_cutoff=60 to the alignment (``regionalign``) as a "free"
    speedup (tried and reverted): RapidFuzz then returns None, flattened
    here to 0.0, for every candidate under 60. For heavily distorted input
    the true match itself often scores under 60, and its rank against the
    other sub-60 candidates is lost: bench_compare showed up to -7.93 points
    at deeper Recall@N in the heaviest-distortion tier and mixed content.
    """
    region = None
    if query.regions is not None:
        region = query.regions.region(license_id, search_text)
    return _scored_once(
        query,
        ("fragment", search_text, region),
        lambda: _fragment_scored(query, search_text, region),
    )


def _fragment_scored(
    query: Query, search_text: str, region: regionalign.Span | None
) -> tuple[float, str]:
    """:func:`fragment_similarity` of *query* with *search_text*, given the
    *region* of it that holds the input (None: the whole text)."""
    if region is None:
        if query.probe is not None:
            probe_score = fuzz.partial_ratio(query.probe, search_text) / 100.0
            if probe_score < PROBE_GATE:
                return probe_score, search_text
        region = (0, len(search_text))
    fast_score, aligned = regionalign.aligned(
        query.text, query.wall, search_text, region
    )
    if fast_score < regionalign.WINDOW_SCORE:
        return fast_score, search_text
    window = search_text[aligned[0] : aligned[1]]
    similarity = fuzz.token_sort_ratio(query.text, window) / 100.0
    start, end = whole_tokens(search_text, *aligned) if query.snap else aligned
    return similarity, search_text[start:end]


def _safeguarded(similarity: float, q_tokens: AbstractSet[str], text: str) -> float:
    """*similarity* less 5 % for each of CRITICAL_TOKENS that only one of
    the query (*q_tokens*) and *text* holds, when it is above 0.9 and
    below 1: a near copy that drops a "not" says the opposite."""
    if 0.90 < similarity < 1.0:
        c_tokens = set(text.split())
        for token in CRITICAL_TOKENS:
            if (token in q_tokens) != (token in c_tokens):
                similarity *= 0.95
    return similarity


def core_similarity(
    norm_input: str, q_len: int, core: str, core_words: int, floor: float
) -> float:
    """The similarity of *norm_input* (*q_len* words) to a licence's *core*
    (*core_words* words), or 0 when it is below *floor* (the whole text's)
    or either has fewer than CORE_MIN_SHARE of the other's words.

    A core that cannot reach *floor* costs nothing: token_sort_ratio compares
    the two texts with their words sorted, of the same lengths as the
    normalised texts (one space between words), and the Indel similarity of
    two strings is at most twice the shorter length over the sum of both."""
    if q_len < core_words * CORE_MIN_SHARE or core_words < q_len * CORE_MIN_SHARE:
        return 0.0
    shorter = min(len(norm_input), len(core))
    if 2 * shorter <= floor * (len(norm_input) + len(core)):
        return 0.0
    return fuzz.token_sort_ratio(norm_input, core, score_cutoff=floor * 100.0) / 100.0


def calculate_base_similarity(
    query: Query, cand: CandidateMatch
) -> tuple[float, float, str]:
    """The similarity of the input (*query*) to *cand*, its coverage (the
    input's words over the words of the text compared) and the text it was
    compared with (an aligned window of a fragment).

    The whole text first; then, when *cand* has a core (``core_text``), the
    core, whose similarity counts if it is higher: then the coverage is
    counted over the core's words and the core is the window. A copy that
    leaves out the optional parts (an appendix) thus has a similarity no
    lower than another licence that has none; a bonus can still rank that one
    first (AFL-2.1's core answers AFL-2.0, as on ``main``)."""
    norm_input, q_len, q_tokens = query.text, query.words, query.tokens
    search_text = cand.get("search_text") or ""
    c_len = cand.get("word_count") or 0
    if c_len == 0:
        c_len = len(search_text.split())

    similarity = 0.0
    best_window = search_text

    if norm_input == search_text:
        similarity = 1.0
    elif q_len >= c_len * 0.8 or not alignment_affordable(norm_input, q_len):
        similarity = _scored_once(
            query,
            ("sorted", search_text),
            lambda: (fuzz.token_sort_ratio(norm_input, search_text) / 100.0, ""),
        )[0]
    else:
        similarity, best_window = fragment_similarity(
            query, cand["license_id"], search_text
        )
    similarity = _safeguarded(similarity, q_tokens, search_text)

    core, core_words = cand.get("core_text"), cand.get("core_word_count") or 0
    if core and core_words and similarity < 1.0:
        floor = similarity
        from_core = _safeguarded(
            _scored_once(
                query,
                ("core", core, core_words, floor),
                lambda: (
                    core_similarity(norm_input, q_len, core, core_words, floor),
                    "",
                ),
            )[0],
            q_tokens,
            core,
        )
        if from_core > similarity:
            similarity, best_window, c_len = from_core, core, core_words

    coverage = (q_len / c_len) if c_len > 0 else 0.0
    return similarity, coverage, best_window


def with_core(cand: CandidateMatch, parts: TextParts | None) -> CandidateMatch:
    """*cand* with the core of its licence (``core_text`` and
    ``core_word_count``, from *parts*, ``database.text_parts``), when it has
    one and *cand* has a text: a candidate without its text (a hinted one
    beyond the first) is scored against nothing, its core included."""
    if parts is None or not parts.core or not parts.core_word_count:
        return cand
    if not cand.get("search_text"):
        return cand
    return {**cand, "core_text": parts.core, "core_word_count": parts.core_word_count}


def _unboosted_score(match: InternalMatch, enable_popularity: bool) -> float:
    """The score of *match* before its marker boost."""
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
    return score


def _marker_boosted(
    score: float, marker_conf: float, is_pure: bool, q_len: int
) -> tuple[float, float]:
    """*score* with the boost of a marker of confidence *marker_conf*, and
    the part of it the confidence floor added (0 when the floor is not
    above the additive boost)."""
    if marker_conf < 0.85:
        # Require confidence >= 0.85 before applying any marker boost.
        # Low-confidence markers (< 0.85) on e.g. partial / noisy inputs
        # caused score distortion on Type 4 inputs in benchmarks.
        return score, 0.0
    if is_pure and q_len >= 50 and marker_conf < 0.94:
        # For long pure license text with moderate-confidence markers,
        # similarity dominates; use a small additive boost only.
        return score + marker_conf * 0.03, 0.0
    # For mixed content, short text, OR high-confidence structural
    # detection (>= 0.94, e.g. BSD/GPL header analysis), the marker is
    # authoritative: an additive boost plus a confidence floor. The floor
    # speaks for the whole input; licenseid.markerfloor takes it back where
    # the input holds other licence texts.
    added = score + marker_conf * 0.05
    floor = marker_conf * 0.95
    if floor > added:
        return floor, floor - added
    return added, 0.0


def calculate_final_score(
    match: InternalMatch,
    boosts: dict[str, float],
    is_pure: bool,
    enable_popularity: bool,
    q_len: int = 0,
) -> float:
    """Calculate the final adjusted score for a match."""
    score = _unboosted_score(match, enable_popularity)
    marker_conf = boosts.get(match["license_id"], 0.0)
    return _marker_boosted(score, marker_conf, is_pure, q_len)[0]


def floor_lift(
    match: InternalMatch,
    boosts: dict[str, float],
    is_pure: bool,
    enable_popularity: bool,
    q_len: int = 0,
) -> float:
    """What the marker's confidence floor adds to the score
    :func:`calculate_final_score` gives *match* above its additive boost:
    0 where no floor binds."""
    score = _unboosted_score(match, enable_popularity)
    marker_conf = boosts.get(match["license_id"], 0.0)
    return _marker_boosted(score, marker_conf, is_pure, q_len)[1]


# Maximum additive boost applied to a candidate whose highest-IDF fingerprint
# n-gram has idf_norm == 1.0 (unique to that single license in the corpus).
# Calibrated to be in the same range as the marker boost (~0.05) so that
# fingerprint matches can break ties between near-equal similarity scores
# without overriding genuine similarity differences.
FP_BOOST: Final = 0.05


def score_candidates(
    candidates: list[CandidateMatch],
    query: Query,
    boosts: dict[str, float],
    is_pure: bool,
    enable_popularity: bool,
) -> list[InternalMatch]:
    """Tier 2: each of *candidates* scored against the input (*query*, made
    once for the call: its probe sample and regions), with the marker
    *boosts*; unsorted."""
    norm_input, q_len = query.text, query.words
    ranked: list[InternalMatch] = []

    # Once per query: how far a short query's similarity counts in the score.
    evidence = text_evidence(norm_input)

    for cand in candidates:
        sim, coverage, best_window = calculate_base_similarity(query, cand)
        ranked.append(
            InternalMatch(
                license_id=cand["license_id"],
                method="text",
                # The whole input is the License List's text, both
                # normalised. Stricter than SPDX matching, which lets a
                # copyright line differ (roadmap item 31). An input that
                # normalises to nothing equals no text: a hinted
                # candidate has none.
                exact=bool(norm_input) and norm_input == cand.get("search_text"),
                base_score=sim * evidence,
                similarity=sim,
                coverage=coverage,
                pop_score=cand.get("pop_score", 0),
                is_deprecated=cand.get("is_deprecated", False),
                superseded_by=cand.get("superseded_by", ""),
                best_window=best_window,
                score=0.0,
                is_spdx=bool(cand.get("is_spdx", False)),
                # None (not judged) kept: a synthetic marker candidate.
                is_osi_approved=cand.get("is_osi_approved", False),
                is_fsf_libre=cand.get("is_fsf_libre", False),
            )
        )

    for r in ranked:
        r["score"] = calculate_final_score(r, boosts, is_pure, enable_popularity, q_len)
        lift = floor_lift(r, boosts, is_pure, enable_popularity, q_len)
        if lift > 0.0:
            r["floor_lift"] = lift
    return ranked


def boost_by_fingerprint(
    ranked: list[InternalMatch], fp_hits: dict[str, float]
) -> None:
    """Add to each of *ranked* that shares at least one discriminative n-gram
    with the query (*fp_hits*: licence ID to idf_norm) a bonus proportional to
    the n-gram's uniqueness in the corpus, at most FP_BOOST. This breaks ties
    between high-similarity variants (MIT vs MIT-0, GPL-2.0 vs GPL-3.0)
    without distorting the overall similarity ranking."""
    for r in ranked:
        idf_norm = fp_hits.get(r["license_id"], 0.0)
        if idf_norm > 0.0:
            r["score"] += FP_BOOST * idf_norm
