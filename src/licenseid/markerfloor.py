# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""When a marker's confidence floor speaks for the whole input.

A marker of confidence ``c`` (a GPL notice, a ``License:`` field, the BSD
clauses) sets a candidate's score to at least ``0.95c``
(``licenseid.similarity.calculate_final_score``): so a notice or a pointer
answers for a file. In a file of several licence texts the marker reads one
of them: Pillow's ``LICENSE``, eleven texts with a GPL notice in one, answered
GPL-2.0-or-later.

So the floor stays unless the input is longer than the marker's licence text
(coverage above :data:`MAX_WHOLE_COVERAGE`) and the whole-text search
(``licenseid.wholetexts.found_rows``, the search of ``TEXTS``) finds texts
that are not all the marker's (its same-text group, an ``-only`` or
``-or-later`` twin or a deprecated ID's replacement included, an exception
dropped). Then the candidate keeps the additive boost only.

The rule acts only on positive evidence: a search that finds nothing (a text
it cannot confirm, such as a BSD-3-Clause text with a copyright block inside)
keeps the floor, as before. The search runs at most once per input, only
where a floor binds above that coverage, and directly, never through
``licenseid.textnames.held_texts``: an output that does not print ``TEXTS``
(terse ``detect``, ``is-*``, ``is_*()``) gives the same answer as ``-v``.
Measured in ``working-docs/implementation/whole-texts.md``.
"""

from collections.abc import Mapping, Sequence
from typing import Final

from licenseid.database import LicenseDatabase, text_corpus, text_parts
from licenseid.listlookup import fold_case
from licenseid.textnames import has_tokens, without_exception
from licenseid.types import InternalMatch
from licenseid.variants import replacement_of
from licenseid.wholetexts import found_rows

__all__ = ["MAX_WHOLE_COVERAGE", "doubt_floors", "floor_doubted"]

#: The top of the band in which an input is about the whole licence text
#: (the coverage bonus of ``licenseid.similarity``): above it, the input is
#: longer than the text and may hold others.
MAX_WHOLE_COVERAGE: Final = 1.05


def _row_key(marker_id: str) -> str:
    """The folded ID of the licence row *marker_id* names: without its
    exception, a deprecated ID as its replacement."""
    head = without_exception(marker_id)
    return fold_case(replacement_of(head) or head)


def floor_doubted(
    rows: Sequence[str] | None,
    marker_id: str,
    groups: Mapping[str, Sequence[str]],
) -> bool:
    """Whether the whole texts found, the row IDs *rows* (None or empty:
    none), include one that is not the text of *marker_id*. *groups* has the
    licences with one text of each ID that shares it (an ID not in it is
    alone)."""
    if not rows:
        return False
    key = _row_key(marker_id)
    return any(
        all(fold_case(member) != key for member in groups.get(row) or (row,))
        for row in rows
    )


def _search(
    db: LicenseDatabase, norm_input: str, marker_id: str
) -> tuple[list[str] | None, dict[str, tuple[str, ...]]]:
    """The row IDs of the texts *norm_input* holds whole (None: none, or an
    input too short or too long to search), and the same-text group of each.
    *marker_id* wins a tie, as an answer does in ``TEXTS``."""
    if not has_tokens(norm_input):
        return None, {}
    head = without_exception(marker_id)
    rows = found_rows(norm_input, text_corpus(db), replacement_of(head) or head)
    if not rows:
        return None, {}
    parts = text_parts(db)
    return rows, {row: parts[row].same_text for row in rows if row in parts}


def doubt_floors(
    ranked: Sequence[InternalMatch], norm_input: str, db: LicenseDatabase
) -> None:
    """Take back from each of *ranked* (scored, not yet sorted) the floor
    lift its marker gave it where :func:`floor_doubted` says the input holds
    other licence texts and its coverage is above
    :data:`MAX_WHOLE_COVERAGE`. The search of *norm_input* runs once, at the
    first such match."""
    found: tuple[list[str] | None, dict[str, tuple[str, ...]]] | None = None
    for match in ranked:
        lift = match.get("floor_lift", 0.0)
        if lift <= 0.0 or match["coverage"] <= MAX_WHOLE_COVERAGE:
            continue
        if found is None:
            found = _search(db, norm_input, match["license_id"])
        if floor_doubted(found[0], match["license_id"], found[1]):
            match["score"] -= lift
            del match["floor_lift"]
