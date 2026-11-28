# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tier 1 retrieval: the List texts that share word 3-grams with an input,
as ``licenseid.gramselect`` selects them, and the hinted candidates,
filtered the same way.

Whole text first (plan of 0.10.0, section 3.1, steps 5 to 7): when the
search of ``TEXTS`` (``licenseid.textcandidates``) finds exactly one text in
the input, Tier 2 scores that text's same-text group and three runner-ups
(``gramselect.narrowed``), which rank under it; otherwise the selection."""

from collections.abc import Collection, Iterable, Sequence
from typing import Final, NamedTuple

from licenseid.database import (
    LicenseDatabase,
    candidate_rows,
    gram_scores,
    list_flags,
    text_source,
)
from licenseid.exprflags import with_judged_flags
from licenseid.gramselect import (
    GRAM_LIMIT,
    Filters,
    ListFlags,
    Narrowed,
    beyond_bar,
    filtered,
    narrowed,
    passes,
    selected,
)
from licenseid.idoptions import excluded_ids, folded
from licenseid.listlookup import fold_case
from licenseid.normalize import normalize_text, strip_comment_prefixes
from licenseid.textcandidates import TextCandidates
from licenseid.textgrams import GramScore
from licenseid.textnames import text_groups
from licenseid.types import CandidateMatch, DetectOptions

# The first hints given are added with their text (they rank on their
# similarity); a later one has none and scores 0. Each costs a Tier 2 pass
# (MIT text on the real List: 0.007 s with no hint, 0.1 s with 10, 0.4 s with
# 50, and the same with 200 or all 739 other IDs), so the text stops at 50.
MAX_HINTS_WITH_TEXT: Final = 50


def drop_excluded(
    candidates: Iterable[CandidateMatch], excluded: Collection[str]
) -> list[CandidateMatch]:
    """*candidates* without an excluded ID (*excluded* case-folded). For the
    marker candidates (titles, "version 2"), free text that joins the pool
    after Tier 1's filters."""
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
    lists the IDs that are, any case), as candidates that pass the filters
    of Tier 1 (``gramselect.passes``): ``exclude``, ``only_spdx`` (on by
    default) and ``only_common`` drop one, as they drop a text. An ID with no
    row is skipped. IDs compare case-folded: "mit" beside MIT, or an ID
    given twice, is added once.

    Each carries its own text, so it ranks on its similarity, for the first
    :data:`MAX_HINTS_WITH_TEXT` hints that are added (a set in sorted order;
    a duplicate, an ID with no row and one a filter drops use no place); a
    later one, and a row with no text (a deprecated ID kept as written), has
    none and scores 0.
    A later hint still costs its row and judged-flags lookups, as it must be
    a candidate with its flags to rank last. The detector adds them after the
    markers, so a hint never replaces a marker candidate."""
    seen = folded(present)
    filters = filters_of(options)
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
        flags = ListFlags(
            bool(details["is_spdx"]),
            bool(details["is_high_usage"]),
            bool(details["is_osi_approved"]),
            bool(details["is_fsf_libre"]),
        )
        if not passes(details["license_id"], flags, filters):
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
    """Add to *candidates*, which Tier 1 filled (none when the gram bar left
    none), the *markers* (without an excluded ID), then the hinted
    candidates. Last, so a hint never replaces a marker's candidate (the
    same text and flags)."""
    excluded = excluded_ids(options.get("exclude", []))
    add_unseen(candidates, drop_excluded(markers, excluded))
    present = [c["license_id"] for c in candidates]
    add_unseen(candidates, hinted_candidates(db, options, present))


class Candidates(NamedTuple):
    """The candidates of Tier 1 for an input."""

    found: list[CandidateMatch]
    #: Whether the input had more distinct grams than were looked up
    #: (``gramselect.GRAM_LIMIT``): then ``TEXTS`` is None.
    bounded: bool
    #: The text found whole that Tier 2 was narrowed to, with its runner-ups;
    #: None when Tier 2 scores the selection.
    narrowed: Narrowed | None = None


def filters_of(options: DetectOptions) -> Filters:
    """The filters *options* set: ``only_spdx`` is on by default."""
    return Filters(
        excluded_ids(options.get("exclude", [])),
        options.get("only_spdx", True),
        options.get("only_common", False),
    )


def gram_text(text: str) -> str:
    """What Tier 1 reads of *text*: its comment prefixes off, then
    normalised whole (the line rules of ``normalize_text`` need its real line
    breaks, as the List texts had when they were posted)."""
    return normalize_text(strip_comment_prefixes(text))


def text_candidates(
    db: LicenseDatabase, text: str, norm_input: str | None = None
) -> TextCandidates:
    """The whole-text search of *text* (*norm_input*: its normalised form,
    if the caller has it): the grams of :func:`gram_text` are looked up at
    its first use, once."""
    return TextCandidates(
        normalize_text(text) if norm_input is None else norm_input,
        lambda: gram_scores(db, gram_text(text), GRAM_LIMIT),
        lambda: text_source(db),
    )


def _narrowed(
    db: LicenseDatabase, texts: TextCandidates, passed: list[GramScore]
) -> Narrowed | None:
    """Tier 2 narrowed to the one text the search of *texts* finds, with no
    answer to rank first, or None (no text, several, the guard, or the
    filters took it out: *passed* is the filtered table)."""
    found = texts.found("")
    if found is None or len(found.rows) != 1:
        return None
    row = found.rows[0]
    group = text_groups(db, [row]).get(row) or (row,)
    return narrowed(texts.table.rows, passed, group)


def get_candidates(
    db: LicenseDatabase,
    options: DetectOptions,
    text: str,
    texts: TextCandidates | None = None,
) -> Candidates:
    """The candidates of Tier 1 for *text*: the grams of :func:`gram_text`
    looked up once, the score table filtered by *options* (``exclude``,
    ``only_spdx``, ``only_common``) without the texts a text they took out
    beats on both counts (``gramselect.beyond_bar``), then the texts
    ``gramselect.narrowed`` keeps when the whole-text search of *texts* (made
    here if not given) finds one text, else those ``gramselect.selected``
    keeps, best first, each with its text and row. Neither under the none
    bar."""
    texts = text_candidates(db, text) if texts is None else texts
    table = texts.table
    passed = beyond_bar(
        table.rows, filtered(table.rows, list_flags(db), filters_of(options))
    )
    rows: Sequence[GramScore] = selected(passed)
    # Under the none bar no text is a candidate, found whole or not.
    narrow = _narrowed(db, texts, passed) if rows else None
    if narrow is not None:
        rows = narrow.rows
    return Candidates(
        candidate_rows(db, [row.license_id for row in rows]),
        table.bounded,
        narrow,
    )
