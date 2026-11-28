# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``TEXTS`` of a ``detect()`` result: the List texts the input holds whole.

The search itself is :func:`licenseid.wholetexts.found_texts`, on the
candidate set of the input (``licenseid.textcandidates``), which gives one
row ID for each text it finds (the smallest of the licences that share it).
``licenseid.firsttext`` asks it once, when the top result is a text match
of an input of :data:`MIN_TOKENS` tokens or more, and hands the result here;
:func:`held_texts` names each found text as ``detect()`` would name an
unstated text of it under the ``variant`` in force:

- the text of the answer's own group (the licences with its text, the answer
  among them) is the answer's ID;
- any other group is its ``-or-later`` form under ``or-later``, else its
  ``-only`` form (``as-written`` too: a bare ID has no text). A group with
  neither form shows its shortest ID (``MPL-2.0`` of
  ``MPL-2.0-no-copyleft-exception``).

``TEXTS`` is a fact about the input: ``exclude``, ``hint``, ``only_spdx`` and
``only_common`` do not touch it. :func:`input_texts` gives it with no answer
(the record of no answer, ``LicenseDetector.texts``): every group by its
variant's name.
"""

import contextlib
import contextvars
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Final

from licenseid.database import LicenseDatabase, text_parts
from licenseid.textcorpus import input_tokens
from licenseid.types import InternalMatch, RawMatch, Variant
from licenseid.variants import replacement_of
from licenseid.wholetexts import Found

if TYPE_CHECKING:  # it imports this module
    from licenseid.textcandidates import TextCandidates

__all__ = [
    "MIN_TOKENS",
    "has_tokens",
    "held_texts",
    "input_texts",
    "named_texts",
    "search_id",
    "skipped",
    "text_groups",
    "without_exception",
]

#: The fewest tokens an input has to hold any text whole by a search. Most
#: List texts are 40 words or more; the few shorter ones (FSFUL) are found
#: only as an exact answer, which needs no search.
MIN_TOKENS: Final = 40

#: Set while the caller never prints ``TEXTS`` (``is-*``, ``is_*()``, the
#: terse ``detect``): the texts are then not named. The search still runs,
#: for ``licenseid.firsttext``.
_SKIPPED: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "licenseid_texts_skipped", default=False
)

_WITH: Final = re.compile(r"\s+WITH\s+", re.IGNORECASE | re.ASCII)
_ONLY: Final = "-only"
_OR_LATER: Final = "-or-later"


@contextlib.contextmanager
def skipped() -> Iterator[None]:
    """Within the block, :func:`held_texts` names nothing: the caller does
    not print ``TEXTS``."""
    token = _SKIPPED.set(True)
    try:
        yield
    finally:
        _SKIPPED.reset(token)


def has_tokens(norm_input: str, least: int = MIN_TOKENS) -> bool:
    """Whether *norm_input* holds *least* tokens or more, counted without
    reading the rest of a long input."""
    if norm_input.isascii():
        return len(norm_input.split(maxsplit=least)) >= least
    return len(input_tokens(norm_input, least)[0]) >= least


def without_exception(expression: str) -> str:
    """*expression* without its exception: ``GPL-2.0-only`` for
    ``GPL-2.0-only WITH Classpath-exception-2.0``."""
    return _WITH.split(expression, maxsplit=1)[0]


def search_id(answer: str) -> str:
    """The row whose group wins a tie in the search for *answer*: its ID
    without the exception, a deprecated ID as its replacement."""
    head = without_exception(answer)
    return replacement_of(head) or head


def text_groups(db: LicenseDatabase, rows: Iterable[str]) -> dict[str, tuple[str, ...]]:
    """The same-text group of each of *rows* that has one in *db*."""
    parts = text_parts(db)
    return {row: parts[row].same_text for row in rows if row in parts}


def _shortest(ids: Iterable[str]) -> str:
    """The shortest ID of *ids* (``GFDL-1.1-only`` of its invariants forms),
    the first in order of ties."""
    return min(ids, key=lambda i: (len(i), i))


def _group_name(group: Iterable[str], variant: Variant) -> str:
    """The ID of a group of licences with one text, as ``detect()`` names an
    unstated text of it under *variant*: ``-or-later`` under ``or-later``,
    else ``-only`` (``as-written`` too: a bare ID has no text to match)."""
    members = list(group)
    suffix = _OR_LATER if variant == "or-later" else _ONLY
    forms = [m for m in members if m.lower().endswith(suffix)]
    return _shortest(forms or members)


def named_texts(
    rows: Iterable[str],
    answer: str,
    variant: Variant,
    groups: Mapping[str, Sequence[str]],
) -> list[str]:
    """The IDs of the row IDs *rows*, each named as the module says, without
    duplicates, in the order of *rows* (the order the input holds them, so
    the first is the text it gives first). *answer* is the ID of the answer
    as it is shown; *groups* has the licences with one text of each ID that
    shares it (an ID that is not in it is alone)."""
    head = without_exception(answer)
    answer_row = search_id(answer).lower()
    named: dict[str, None] = {}
    for row in rows:
        group = groups.get(row) or (row,)
        if any(member.lower() == answer_row for member in group):
            named[head] = None
        else:
            named[_group_name(group, variant)] = None
    return list(named)


def held_texts(
    db: LicenseDatabase,
    results: Sequence[RawMatch | InternalMatch],
    variant: Variant,
    found: Found | None,
) -> list[str] | None:
    """The List texts the input holds whole, as :func:`named_texts` names
    them, or None: *results* has no text match first, or *found*, the search
    ``licenseid.firsttext.settle_texts`` made for that top, is None (the
    input is under :data:`MIN_TOKENS` tokens, nothing is found, or the input
    is too long to search). An answer that is exact holds its own text, whatever
    its length (a List text may be under 40 words). The caller gives the list
    to every result. Within :func:`skipped` it is None."""
    top = results[0] if results else None
    if _SKIPPED.get() or top is None or top["method"] != "text":
        return None
    answer = without_exception(top["license_id"])
    if top["exact"]:
        return [answer]
    if found is None:
        return None
    return named_texts(found.rows, answer, variant, text_groups(db, found.rows))


def input_texts(
    db: LicenseDatabase, texts: "TextCandidates", variant: Variant
) -> list[str] | None:
    """The List texts the input of *texts* (its whole-text search) holds
    whole with no answer to name first: each group as :func:`named_texts`
    names a group not the answer's under *variant*. None as for
    :func:`held_texts`: under :data:`MIN_TOKENS` tokens, nothing found, or
    too long to search."""
    found = texts.found("")
    if found is None:
        return None
    return named_texts(found.rows, "", variant, text_groups(db, found.rows))
