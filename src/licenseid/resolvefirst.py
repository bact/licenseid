# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``detect()`` on an input that is, as a whole, one declared licence value:
``resolve()`` reads it first, so both calls give one expression for it
(``MIT OR Apache-2.0``, ``Apache License, Version 2.0``) where the text tiers
guessed a licence that shares words with it (``ECL-2.0``).

The adapter of ``working-docs/design/match-resolve-0-8.md`` section 3: the
expression is the result's; a result is exact as a tag or a field is, unless
the reading is a guess (trust ``none``, a narrowed ``-only``), so every
channel gives one answer (D2, a stricter ``exact``, is still open); a reading
by name (a step of one) is found by ``name``, any other by ``id``.

An input ``resolve()`` refuses that is shorter than :data:`MIN_TEXT_WORDS`
gets no text match either: on the fixtures and the PyPI sample, Tiers 1 and
2 answered such inputs wrongly four times in five (``GNU GPL v2`` as
``LiLiQ-R-1.1``, ``Proprietary`` as ``AGPL-1.0-only``), and every input from
ten words on rightly. The name tier still answers before that.
"""

from typing import Final

from licenseid.errors import shown
from licenseid.resolvertypes import Category, Resolution
from licenseid.types import LicenseFlags, Method, RawMatch
from licenseid.warning import warn

#: The fewest normalised words Tiers 1 and 2 match, of an input resolve()
#: refused.
MIN_TEXT_WORDS: Final = 10

#: The readings of a licence's name, not of its ID.
_BY_NAME: Final[frozenset[Category]] = frozenset(
    ("listed_name", "prose_form", "text_title", "trove_name")
)


def as_resolved(resolution: Resolution, matches: list[RawMatch]) -> list[RawMatch]:
    """*matches*, the results of the expression of *resolution*, made what
    the resolution says: inexact for a guess (a narrowed ``-only`` already
    is), found by ``name`` when a step read a name, else by ``id``. A
    result not narrowed is written as resolve() writes it (``MirOS OR
    MIT``, the order of ``exprcanon``)."""
    expression = resolution["expression"] or ""
    exact = resolution["trust"] != "none"
    kinds = {entry["kind"] for entry in resolution["steps"]}
    by_name = resolution["category"] in _BY_NAME or not kinds.isdisjoint(_BY_NAME)
    method: Method = "name" if by_name else "id"
    if len(matches) == 1 and matches[0]["exact"]:
        matches[0]["license_id"] = expression
    for match in matches:
        match["exact"] = match["exact"] and exact
        match["method"] = method
    return matches


def match_of(expression: str, flags: LicenseFlags) -> RawMatch:
    """A result of *expression*, found exactly, with its *flags*: for one
    resolve() reads and no marker reader takes (``MIT WITH
    AdditionRef-x``)."""
    return RawMatch(
        license_id=expression,
        method="id",
        exact=True,
        score=1.0,
        similarity=None,
        coverage=None,
        is_spdx=flags["is_spdx"],
        is_osi_approved=flags["is_osi_approved"],
        is_fsf_libre=flags["is_fsf_libre"],
    )


def too_short(resolution: Resolution, words: int, *, whole: bool) -> bool:
    """Whether an input of *words* normalised words, which *resolution*
    refused, is too short to match as text. If so, and the text is the
    *whole* input (no tag was taken out, which its reader judged), say why
    it is no licence value (``input: too few words for text: not found: GNU GPL
    v2``)."""
    if words >= MIN_TEXT_WORDS or resolution["expression"] is not None:
        return False
    if whole and words:
        warn("input", "too few words for text", _detail(resolution["reason"] or ""))
    return True


def _detail(reason: str) -> str:
    """*reason* as the DETAIL of a warning: a ";" would start its ACTION, so
    the mark a reason names is spelt out (``operator not stated: semicolon``)
    and any other is a ",", as :func:`licenseid.errors.shown` writes it."""
    if reason.endswith(": ;"):
        reason = reason[:-1] + "semicolon"
    return shown(reason)
