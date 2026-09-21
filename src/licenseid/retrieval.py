# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tier 1 retrieval: fetch candidates from the FTS5 index for a query text,
then filter them and add the hinted ones."""

from licenseid.database import LicenseDatabase
from licenseid.normalize import normalize_text, strip_comment_prefixes
from licenseid.types import CandidateMatch, MatchRequest

# Tail-only additions (candidates found only via the tail query in
# _search_candidates_by_length(), not its head query) are capped at this many,
# bounding the head+tail union at 75 candidates and Tier 2 (RapidFuzz) work
# accordingly. See _search_candidates_by_length() for the full rationale.
TAIL_ONLY_CAP: int = 25


def _search_candidates_by_length(
    db: LicenseDatabase, norm_text: str
) -> list[CandidateMatch]:
    """Tier 1 retrieval: head query, plus a capped tail query for long
    documents.

    search_candidates builds an OR query from the first 20 words of
    whatever it receives (see database.py).  The caps below control
    which normalised words those are:

      Head query: pass norm_words[:100] so search_candidates uses
        words 0-19 (the preamble/title, which is highly distinctive).
        The 100-word buffer leaves room if the OR-term limit is raised
        again later.

      Tail query: pass norm_words[-20:] -- exactly the last 20 words --
        so search_candidates uses words -20 to -1 (the true end of the
        document: warranty disclaimer, governing-law clause, etc.).
        Benchmarks showed that passing words[-120:] was wrong: FTS5 only
        saw words -120 to -101, which are mid-text and less distinctive
        than the actual tail.  Aligning the slice with the OR-term limit
        (20 words) recovers those end-specific signals.
        Threshold >200 words ensures head (0-99) and tail (last 20) are
        non-overlapping for inputs up to any realistic length.

    Both queries use limit=50 so BM25 ranking is computed over 50
    results before any cap.  Tail-only additions (candidates in the
    tail set but not the head set) are capped at TAIL_ONLY_CAP,
    bounding the union at 75 candidates and Tier 2 (RapidFuzz) work at
    75 passes.

    Benchmark on 469 licences with >200 normalised words showed that
    uncapped tail adds a mean of 33 candidates (median 38, max 50),
    pushing the union to a mean of 83 (max 100).  Because tail
    candidates are in BM25 order the cap retains the most distinctive
    tail-only candidates and discards the rest, which are largely
    generic vocabulary shared across many licences.  The cap does not
    affect the head set (always up to 50).

    These thresholds (100/200/50/25/20) were originally tuned against
    raw word counts; they now slice normalised word counts instead,
    which are usually somewhat shorter (copyright/comment/bullet noise
    removed) — re-validate via bench_compare after this change.
    """
    norm_words = norm_text.split()
    if len(norm_words) <= 100:
        return list(db.search_candidates(norm_text, limit=50, already_normalized=True))

    head_query = " ".join(norm_words[:100])
    raw_candidates = list(
        db.search_candidates(head_query, limit=50, already_normalized=True)
    )
    if len(norm_words) <= 200:
        return raw_candidates

    tail_query = " ".join(norm_words[-20:])
    seen_ids = {c["license_id"] for c in raw_candidates if c.get("license_id")}
    tail_only_added = 0
    tail_candidates = db.search_candidates(
        tail_query, limit=50, already_normalized=True
    )
    for c in tail_candidates:
        if tail_only_added >= TAIL_ONLY_CAP:
            break
        if c.get("license_id") not in seen_ids:
            raw_candidates.append(c)
            seen_ids.add(c["license_id"])
            tail_only_added += 1
    return raw_candidates


def _filter_candidates(
    raw_candidates: list[CandidateMatch],
    only_spdx: bool,
    only_common: bool,
    exclude_list: list[str],
) -> list[CandidateMatch]:
    """Drop candidates with no ID, an excluded ID, or failing the
    only_spdx/only_common metadata filters."""
    filtered: list[CandidateMatch] = []
    for cand in raw_candidates:
        license_id = cand.get("license_id")
        if not license_id or license_id in exclude_list:
            continue

        if only_spdx and not cand.get("is_spdx", False):
            continue
        if (
            only_common
            and not cand.get("is_high_usage", False)
            and not (
                cand.get("is_osi_approved", False) or cand.get("is_fsf_libre", False)
            )
        ):
            continue

        filtered.append(cand)
    return filtered


def _inject_hinted_candidates(
    db: LicenseDatabase, filtered: list[CandidateMatch], hint_list: list[str]
) -> list[CandidateMatch]:
    """Force-include DB-backed hint_list IDs not already present, as
    synthetic candidates (no search_text, so they rank purely on
    marker/metadata signals rather than similarity)."""
    candidate_ids = {c.get("license_id") for c in filtered if c.get("license_id")}
    for h_id in hint_list:
        if h_id not in candidate_ids:
            details = db.get_license_details(h_id)
            if details:
                filtered.append(
                    CandidateMatch(
                        license_id=details["license_id"],
                        search_text="",
                        word_count=details["word_count"],
                        is_spdx=details["is_spdx"],
                        is_high_usage=details["is_high_usage"],
                        is_osi_approved=details["is_osi_approved"],
                        is_fsf_libre=details["is_fsf_libre"],
                        pop_score=details.get("pop_score", 0),
                        is_deprecated=details.get("is_deprecated", False),
                        superseded_by=details.get("superseded_by", ""),
                    )
                )
    return filtered


def get_candidates(
    db: LicenseDatabase,
    data: MatchRequest,
    text: str,
) -> list[CandidateMatch]:
    """Fetch and filter candidates from the database."""
    only_spdx = data.get("only_spdx", True)
    only_common = data.get("only_common", False)
    exclude_list: list[str] = data.get("exclude", [])
    hint_list: list[str] = data.get("hint", [])

    # Strip comment prefixes before FTS5: improves recall for Type 5
    # inputs where license text is wrapped in // / # / * comment markers.
    text = strip_comment_prefixes(text)

    # Normalize the full text once, up front, before any word-count
    # slicing.  normalize_text() applies several line-anchored rules
    # (copyright-notice removal, bullets, comment prefixes, separator
    # runs) that only fire correctly with real line breaks intact.
    # Slicing raw words first and rejoining them with spaces (the
    # previous approach) destroyed that line structure before
    # normalization ever ran, so the query-side text silently skipped
    # rules that index-side normalization (run on the untouched
    # original text in database.py) had already applied — producing
    # FTS5 OR-terms for words that no longer exist in the indexed
    # document.  Normalizing here keeps query-side and index-side
    # normalization consistent.
    norm_text = normalize_text(text)

    raw_candidates = _search_candidates_by_length(db, norm_text)
    filtered = _filter_candidates(raw_candidates, only_spdx, only_common, exclude_list)
    return _inject_hinted_candidates(db, filtered, hint_list)
