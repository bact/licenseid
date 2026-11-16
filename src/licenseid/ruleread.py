# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Whether ``resolve()`` read a value by a rewrite rule, for the ``EXACT`` of a
tag or a field (roadmap item 52)."""

from licenseid.listlookup import ListLookup
from licenseid.resolvefirst import is_exact
from licenseid.resolver import resolve_with


def rule_read(db: ListLookup, value: str) -> bool:
    """Whether ``resolve()`` reads *value* by a rewrite rule, so that a tag or
    a field of it is not exact, as the argument is not (``resolvefirst``)."""
    resolution = resolve_with(db, value)
    return resolution["expression"] is not None and not is_exact(resolution)


def tag_inexact(db: ListLookup, leading: str, granted: str, expression: str) -> bool:
    """Whether a tag is not exact. A tag is judged by the expression it
    answers, *leading*, not by the words after it on its line (a comment
    closer, another tag, prose): "only" before an operator (*expression*
    differs from *granted*) drops a licence, else a rule read the expression
    (``GPL2+``, ``GPLv2 or later``: the ID before a grant, judged alone)."""
    return expression != granted or rule_read(db, leading)
