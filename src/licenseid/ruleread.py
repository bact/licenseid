# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Whether ``resolve()`` read a value by a rewrite rule, for the ``EXACT`` of a
tag or a field (roadmap item 52)."""

from licenseid.hiddenchars import cuts_hidden
from licenseid.listlookup import ListLookup
from licenseid.resolvefirst import is_exact, was_cut
from licenseid.resolver import resolve_with
from licenseid.types import CandidateMatch


def rule_read(db: ListLookup, value: str) -> bool:
    """Whether ``resolve()`` reads *value* by a rewrite rule, so that a tag or
    a field of it is not exact, as the argument is not (``resolvefirst``)."""
    resolution = resolve_with(db, value)
    return resolution["expression"] is not None and not is_exact(resolution)


def tag_inexact(
    db: ListLookup,
    granted: str,
    expression: str,
    *,
    resolved: bool = False,
    field: str | None = None,
) -> bool:
    """Whether a tag is not exact. A tag is judged by the expression it
    answers, *granted* (the leading expression with the grant after it
    applied: ``LGPLv2+`` for ``LGPLv2 or later``), not by the words after it
    on its line (a comment closer, another tag, prose): "only" before an
    operator (*expression* differs from *granted*) drops a licence, else a
    rule read the expression (``GPL2+``, ``GPLv2 or later``). The grant is
    judged with its ID: a cut version is read only as granted
    (``resolve()``: ``version_spelling``), so a value written ``LGPLv2 or
    later`` is no ``LGPL-2.0-or-later`` as written. With *resolved*, the value
    is an expression ``resolve()`` gave, which no rule reads
    (``tests/test_resolve_first_once.py``): it is not read again. A *field*
    (the whole value of a manifest field) is not exact either when ``resolve()``
    cut it: ``MIT or later.`` leaves its end mark off, as ``MIT.`` does."""
    if expression != granted:
        return True
    if resolved:
        return False
    return rule_read(db, granted) or (
        field is not None and was_cut(resolve_with(db, field))
    )


def hidden_cut(value: str, found: list[CandidateMatch]) -> list[CandidateMatch]:
    """*found*, the candidates of a tag or field *value*, none exact if the
    reader left off a hidden character of *value* that is not zero-width, as
    ``resolve()`` judges the argument (``invisible characters``)."""
    if cuts_hidden(value):
        for match in found:
            match["decided"] = True
    return found
