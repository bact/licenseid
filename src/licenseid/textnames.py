# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``TEXTS`` of a ``detect()`` result: the List texts the input holds whole.

The search itself is :func:`licenseid.wholetexts.found_rows`, which gives
one row ID for each text it finds (the smallest of the licences that share
it). This module asks it, when the top result is a text match of an input of
:data:`MIN_TOKENS` tokens or more, and names each found text as ``detect()``
would name an unstated text of it under the ``variant`` in force:

- the text of the answer's own group (the licences with its text, the answer
  among them) is the answer's ID;
- any other group is its ``-or-later`` form under ``or-later``, else its
  ``-only`` form (``as-written`` too: a bare ID has no text). A group with
  neither form shows its shortest ID (``MPL-2.0`` of
  ``MPL-2.0-no-copyleft-exception``).

``TEXTS`` is a fact about the input: ``exclude``, ``hint``, ``only_spdx`` and
``only_common`` do not touch it.
"""

import contextlib
import contextvars
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Final

from licenseid.database import LicenseDatabase, text_corpus, text_parts
from licenseid.textcorpus import input_tokens
from licenseid.types import InternalMatch, RawMatch, Variant
from licenseid.variants import replacement_of
from licenseid.wholetexts import found_rows

__all__ = [
    "MIN_TOKENS",
    "found_rows",
    "has_tokens",
    "held_texts",
    "named_texts",
    "skipped",
]

#: The fewest tokens an input has to hold any text whole by a search. Most
#: List texts are 40 words or more; the few shorter ones (FSFUL) are found
#: only as an exact answer, which needs no search.
MIN_TOKENS: Final = 40

#: Set while the caller never prints ``TEXTS`` (``is-*``, ``is_*()``, the
#: terse ``detect``): the search is then skipped.
_SKIPPED: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "licenseid_texts_skipped", default=False
)

_WITH: Final = re.compile(r"\s+WITH\s+", re.IGNORECASE | re.ASCII)
_ONLY: Final = "-only"
_OR_LATER: Final = "-or-later"


@contextlib.contextmanager
def skipped() -> Iterator[None]:
    """Within the block, :func:`held_texts` searches nothing: the caller does
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


def _head(expression: str) -> str:
    """*expression* without its exception: ``GPL-2.0-only`` for
    ``GPL-2.0-only WITH Classpath-exception-2.0``."""
    return _WITH.split(expression, maxsplit=1)[0]


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
    duplicates, sorted. *answer* is the ID of the answer as it is shown;
    *groups* has the licences with one text of each ID that shares it (an ID
    that is not in it is alone)."""
    answer_row = _head(replacement_of(_head(answer)) or _head(answer)).lower()
    named: set[str] = set()
    for row in rows:
        group = groups.get(row) or (row,)
        if any(member.lower() == answer_row for member in group):
            named.add(_head(answer))
        else:
            named.add(_group_name(group, variant))
    return sorted(named)


def held_texts(
    db: LicenseDatabase,
    norm_input: str,
    results: Sequence[RawMatch | InternalMatch],
    variant: Variant,
) -> list[str] | None:
    """The List texts the input holds whole, as :func:`named_texts` names
    them, or None: *results* has no text match first, the input is under
    :data:`MIN_TOKENS` tokens, nothing is found, or the input is too long
    to search. An answer that is exact holds its own text and no search is
    made, whatever its length (a List text may be under 40 words). The caller
    gives the list to every result. Within :func:`skipped` it is None."""
    top = results[0] if results else None
    if _SKIPPED.get() or top is None or top["method"] != "text":
        return None
    answer = _head(top["license_id"])
    if top["exact"]:
        return [answer]
    if not has_tokens(norm_input):
        return None
    found = found_rows(norm_input, text_corpus(db), replacement_of(answer) or answer)
    if not found:
        return None
    parts = text_parts(db)
    groups = {i: parts[i].same_text for i in found if i in parts}
    return named_texts(found, answer, variant, groups)
