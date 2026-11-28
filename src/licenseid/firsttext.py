# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A text answer stands in a file of several licence texts only when its text
comes first (roadmap item 59).

``detect()`` ranks one licence per input, so in a file that holds several
List texts the longest one wins on similarity: numpy's ``LICENSE.txt``, its
BSD-3-Clause text and then the bundled runtime texts, answered
``GPL-3.0-only``. By habit a licence file gives the project's own text first
and the bundled ones after it. So when the top result is a text match of an
input of :data:`licenseid.textnames.MIN_TOKENS` tokens or more, the
whole-text search of the input (``licenseid.textcandidates``, the search of
``TEXTS``) is asked for that answer, and where it finds the texts of two or
more same-text groups, the results stand only when the first text found is
the answer's
(``licenseid.markerfloor.found_in``: its same-text group, a deprecated ID's
replacement, an exception dropped). Otherwise there is no answer
(``REASON=several texts`` on the CLI record).

The rule only refuses, never makes an answer, and acts only on positive
evidence: no text found, or the texts of one group, keep the results. A
coverage gate would miss a short text before a long one (MIT, then the
GPL-3.0: the top's coverage is about 1.03), so there is none. An exact answer
is the whole input, one text, and is not searched.

The search runs whatever ``licenseid.textnames.skipped`` says, so terse
``detect``, ``is-*`` and ``is_*()`` give the answer ``-v`` gives; its result
is handed on to ``licenseid.textnames.held_texts``, so ``TEXTS`` costs no
second search. Measured in ``working-docs/implementation/whole-texts.md``.
"""

from collections.abc import Mapping, Sequence

from licenseid.database import LicenseDatabase
from licenseid.markerfloor import found_in
from licenseid.textcandidates import TextCandidates
from licenseid.textnames import search_id, text_groups
from licenseid.types import InternalMatch, RawMatch
from licenseid.wholetexts import Found

__all__ = ["first_stands", "settle_texts"]


def first_stands(
    found: Found | None, answer_id: str, groups: Mapping[str, Sequence[str]]
) -> bool:
    """Whether the answer *answer_id* stands by the whole texts *found*:
    they are of one same-text group at most, or the first of them is the
    text of *answer_id*. *groups* has the licences with one text of each
    row found (a row not in it is alone)."""
    if found is None or len(found.rows) < 2:
        return True
    return found_in([found.first], answer_id, groups)


def settle_texts(
    settled: list[RawMatch | InternalMatch], texts: TextCandidates, db: LicenseDatabase
) -> tuple[list[RawMatch | InternalMatch], Found | None]:
    """*settled*, or no results where :func:`first_stands` refuses its top,
    and the search of *texts* made (None: none made, or nothing found). Only
    a top that is a text match, not exact, of an input of ``MIN_TOKENS``
    tokens or more is searched."""
    top = settled[0] if settled else None
    if top is None or top["method"] != "text" or top["exact"]:
        return settled, None
    answer = top["license_id"]
    found = texts.found(search_id(answer))
    if found is None:
        return settled, None
    stands = first_stands(found, answer, text_groups(db, [found.first]))
    return (settled if stands else []), found
