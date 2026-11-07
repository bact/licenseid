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

An input that is one URL, which ``resolve()`` refused or did not read, gets
no match at all, by name or text: ``.``, ``/`` and ``-`` make words of it
that Tiers 0 to 2 read as a licence the page is not
(``https://www.gnu.org/licenses/gpl-3.0.en.html`` as ``AGPL-3.0-only``).

A word count is no measure of Chinese or Japanese, written without spaces:
an input whose letters are nine in ten Han or kana is not cut. Sliced from the
four such texts of the List at 4 to 13 characters, Tiers 1 and 2 answered
the licence or its other version 592 times in 593 (1 no answer), and
28 of 30 short phrases that are no licence got no answer; an input that
mixes in Latin words (``GPL 第三版``, was ``AGPL-1.0-only``) is cut by its
words. Korean is written with spaces, and its words are counted. Such an
input is weighed by its length instead (:func:`licenseid.similarity.text_evidence`,
40 columns, about the width of ten words): a few Han letters that a licence
holds (``著作権``, ``版权所有``) answered it at 1.0 for a word they share.
"""

import re
from typing import Final

from licenseid.errors import shown
from licenseid.resolvertypes import Category, Resolution
from licenseid.types import LicenseFlags, Method, RawMatch
from licenseid.urlkey import is_url
from licenseid.warning import warn

#: The fewest normalised words Tiers 1 and 2 match, of an input resolve()
#: refused.
MIN_TEXT_WORDS: Final = 10

#: A Han or kana letter: of a script written without spaces between words.
_NO_SPACES: Final = re.compile(
    "[\u3005-\u3007\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff"
    "\uf900-\ufaff\uff66-\uff9f\U00020000-\U0003134f]"
)

#: The share of an input's letters that are Han or kana for it to be read
#: as written without spaces.
_MIN_NO_SPACES_SHARE: Final = 0.9

#: The readings of a licence's name, not of its ID.
_BY_NAME: Final[frozenset[Category]] = frozenset(
    (
        "alias_name",
        "license_url",
        "listed_name",
        "prose_form",
        "text_title",
        "trove_name",
    )
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


def too_short(resolution: Resolution, text: str, *, whole: bool) -> bool:
    """Whether *text*, a normalised input *resolution* refused, is too short
    to match as text: fewer than :data:`MIN_TEXT_WORDS` words, unless its
    letters are mostly Han or kana. If so, and the text is the *whole* input
    (no tag was taken out, which its reader judged), say why it is no
    licence value (``input: too few words for text: not found: GNU GPL
    v2``)."""
    words = len(text.split())
    if words >= MIN_TEXT_WORDS or resolution["expression"] is not None:
        return False
    if _written_without_spaces(text):
        return False
    if whole and words:
        warn("input", "too few words for text", _detail(resolution["reason"] or ""))
    return True


def unread_url(resolution: Resolution, text: str) -> bool:
    """Whether *text*, the whole input, is one URL (in one pair of angle
    brackets or none) that *resolution* gave no expression. If so, say why it
    is no licence value, as :func:`too_short` does (``input: too few words
    for text: url names several licences: ...``)."""
    url = text.strip()
    if len(url) > 2 and url[0] == "<" and url[-1] == ">":
        url = url[1:-1]
    if resolution["expression"] is not None or not is_url(url):
        return False
    warn("input", "too few words for text", _detail(resolution["reason"] or ""))
    return True


def _written_without_spaces(text: str) -> bool:
    """Whether *text* has a letter, and :data:`_MIN_NO_SPACES_SHARE` of its
    letters are Han or kana (a clause letter, ``第7条b``, may stand among
    them)."""
    letters = [ch for ch in text if ch.isalpha()]
    han_kana = sum(1 for ch in letters if _NO_SPACES.match(ch))
    return bool(letters) and han_kana >= _MIN_NO_SPACES_SHARE * len(letters)


def _detail(reason: str) -> str:
    """*reason* as the DETAIL of a warning: a ";" would start its ACTION, so
    the mark a reason names is spelt out (``operator not stated: semicolon``)
    and any other is a ",", as :func:`licenseid.errors.shown` writes it."""
    if reason.endswith(": ;"):
        reason = reason[:-1] + "semicolon"
    return shown(reason)
