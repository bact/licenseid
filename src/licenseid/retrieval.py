# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tier 1 retrieval: fetch candidates from the FTS5 index for a query text
and filter them; the hinted candidates, filtered the same way."""

from collections.abc import Collection, Iterable
from typing import Final

from licenseid.database import LicenseDatabase
from licenseid.exprflags import with_judged_flags
from licenseid.ftsquery import MAX_TERMS
from licenseid.idoptions import excluded_ids, folded
from licenseid.listlookup import fold_case
from licenseid.normalize import normalize_text, strip_comment_prefixes
from licenseid.types import CandidateMatch, DetectOptions

# Tail-only additions (candidates found only via the tail query in
# _search_candidates_by_length(), not its head query) are capped at this many,
# bounding the head+tail union at 75 candidates and Tier 2 (RapidFuzz) work
# accordingly. See _search_candidates_by_length() for the full rationale.
TAIL_ONLY_CAP: int = 25

# The first hints given are added with their text (they rank on their
# similarity); a later one has none and scores 0. Each costs a Tier 2 pass
# (MIT text on the real List: 0.8 s with no hint, 1.6-2.0 s with 50, 3.4-3.8 s
# with 200, about 10 s with all 740 IDs), so the text stops at 50.
MAX_HINTS_WITH_TEXT: Final = 50


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

      Tail query: pass norm_words[-MAX_TERMS:] -- exactly the last 20 words --
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

    tail_query = " ".join(norm_words[-MAX_TERMS:])
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
    excluded: Collection[str],
) -> list[CandidateMatch]:
    """Drop candidates with no ID, an excluded ID (*excluded* case-folded,
    see licenseid.idoptions), or failing the only_spdx/only_common metadata
    filters."""
    filtered: list[CandidateMatch] = []
    for cand in raw_candidates:
        license_id = cand.get("license_id")
        if not license_id or fold_case(license_id) in excluded:
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


def drop_excluded(
    candidates: Iterable[CandidateMatch], excluded: Collection[str]
) -> list[CandidateMatch]:
    """*candidates* without an excluded ID (*excluded* case-folded). For the
    marker candidates (titles, "version 2"), free text that joins the pool
    after Tier 1's filter."""
    return [c for c in candidates if fold_case(c["license_id"]) not in excluded]


def add_unseen(
    candidates: list[CandidateMatch], extra: Iterable[CandidateMatch]
) -> None:
    """Append to *candidates* each of *extra* whose ID is not there yet."""
    seen = {c["license_id"] for c in candidates}
    for cand in extra:
        if cand["license_id"] not in seen:
            candidates.append(cand)
            seen.add(cand["license_id"])


def hinted_candidates(
    db: LicenseDatabase, options: DetectOptions, present: Iterable[str]
) -> list[CandidateMatch]:
    """The ``hint`` IDs of *options* that are no candidate yet (*present*
    lists the IDs that are, any case), as candidates that passed the filters
    full-text search passes: ``exclude``, ``only_spdx`` (on by default) and
    ``only_common`` drop one, as they drop a Tier 1 candidate. An ID with no
    row is skipped. IDs compare case-folded: "mit" beside MIT, or an ID
    given twice, is added once.

    Each carries its own text, so it ranks on its similarity, for the first
    :data:`MAX_HINTS_WITH_TEXT` hints that are added (a set in sorted order;
    a duplicate, an ID with no row and one a filter drops use no place); a
    later one, and a row with no text (a deprecated ID kept as written), has
    none and scores 0.
    A later hint still costs its row and judged-flags lookups, as it must be
    a candidate with its flags to rank last. The detector adds them after the
    markers and the mixed-content search, so a hint never counts towards that
    search's gate and never replaces a marker candidate."""
    seen = folded(present)
    only_spdx = options.get("only_spdx", True)
    only_common = options.get("only_common", False)
    excluded = excluded_ids(options.get("exclude", []))
    hinted: list[CandidateMatch] = []
    for h_id in options.get("hint", ()):
        if fold_case(h_id) in seen:
            continue
        details = db.get_license_details(h_id)
        if not details:
            continue
        details = with_judged_flags(details, db)
        seen |= {fold_case(details["license_id"]), fold_case(h_id)}
        cand = CandidateMatch(
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
        # A hint a filter drops is no candidate and takes no place.
        if not _filter_candidates([cand], only_spdx, only_common, excluded):
            continue
        if len(hinted) < MAX_HINTS_WITH_TEXT:
            cand["search_text"] = db.get_search_text(details["license_id"])
        hinted.append(cand)
    return hinted


def add_free_text(
    db: LicenseDatabase,
    options: DetectOptions,
    candidates: list[CandidateMatch],
    markers: Iterable[CandidateMatch],
) -> None:
    """Add to *candidates*, which Tier 1 and the mixed-content search
    filled, the *markers* (without an excluded ID), then the hinted
    candidates. Last, so a hint never counts towards the mixed-content gate
    and never replaces a marker's candidate (the same text and flags)."""
    excluded = excluded_ids(options.get("exclude", []))
    add_unseen(candidates, drop_excluded(markers, excluded))
    present = [c["license_id"] for c in candidates]
    add_unseen(candidates, hinted_candidates(db, options, present))


def get_candidates(
    db: LicenseDatabase,
    data: DetectOptions,
    text: str,
) -> list[CandidateMatch]:
    """Fetch and filter candidates from the database: where the options
    exclude, only_spdx and only_common act on Tier 1 (``hint`` acts in
    :func:`hinted_candidates`, through the same filters)."""
    only_spdx = data.get("only_spdx", True)
    only_common = data.get("only_common", False)
    excluded = excluded_ids(data.get("exclude", []))

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
    return _filter_candidates(raw_candidates, only_spdx, only_common, excluded)
