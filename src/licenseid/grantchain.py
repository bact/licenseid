# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A tag whose "or later" grant an operator follows (``MIT (or later) AND
Apache-2.0``), read as ``resolve()``, the argument and a field read it
(``Apache-2.0 AND MIT+``).

The tag reader ends its expression at a grant (``identifiers.leading_expression``),
so it read the first licence and dropped the rest (0.8.4), then refused the
value (``looseid.lists_after_grant``). :func:`operator_chain` finds the head
of the tag's value that holds the operator chain, by the tag reader's own
rules, and :func:`chain_read` answers what ``resolve()`` reads in it: never
an answer ``resolve()`` refuses, never an operand dropped.
"""

import re
from collections.abc import Callable

from licenseid.classify import grant_end
from licenseid.identifiers import leading_expression, qualify_trailing_grant
from licenseid.listlookup import ListLookup
from licenseid.looseid import drops_words, grant_stop, operator_at
from licenseid.resolvefirst import is_exact
from licenseid.resolver import resolve_with
from licenseid.types import CandidateMatch
from licenseid.variants import ONLY_WORD, qualify_trailing_only, read_from

# The word a grant starts with (as looseid reads it).
_RE_OR_WORD = re.compile(r"\bor\b", re.IGNORECASE)


def chain_read(
    db: ListLookup,
    leading: str,
    expression: str,
    value: str,
    read: Callable[[str], list[CandidateMatch]],
) -> list[CandidateMatch]:
    """The candidates of *value*, a tag's, when an operator follows the grant
    after its *leading* expression (read as *expression*): what ``resolve()``
    reads in its :func:`operator_chain`, through *read* (a reader of an
    expression ``resolve()`` gave), not exact for a rewrite rule and written
    as ``resolve()`` writes it (``resolvefirst.as_resolved``); else none."""
    head = operator_chain(db, leading, expression, value)
    resolution = resolve_with(db, head) if head else None
    if resolution is None or resolution["expression"] is None:
        return []
    found = read(resolution["expression"])
    if len(found) == 1 and not found[0].get("decided"):
        if is_exact(resolution):
            found[0]["license_id"] = resolution["expression"]
        else:
            found[0]["decided"] = True
    return read_from(found, resolution["input"])


def operator_chain(
    db: ListLookup, leading: str, expression: str, value: str
) -> str | None:
    """The head of *value*, a tag's, that ``resolve()`` is to read when an
    operator follows the grant after its *leading* expression (read as
    *expression*; none when the grant ends it): ``MIT (or later) AND
    Apache-2.0`` of ``MIT (or later) AND Apache-2.0 */``. The rest is read as
    a tag reads its value, with the granted licence in front (``MIT+ AND
    Apache-2.0 */``): the head ends where that reading ends, or after a grant
    that ends it, with what is glued to its end. None where that reading
    drops words (a second grant then an operator, a listing, a glued mark,
    an "only" after it), an opening bracket stands before the operator
    (``(AND MIT)``) or the grant stands in brackets that close after it
    (``(MIT or later AND ISC)``)."""
    if not leading:
        leading = _before_first_grant(value)
        expression = qualify_trailing_grant(leading, value)
    end = grant_stop(value, leading) if expression != leading else None
    if not expression or end is None:
        return None
    while end < len(value) and (value[end].isspace() or value[end] in ".:)]"):
        end += 1  # the bracket of "(or later)", an end mark resolve() judges
    start = operator_at(value, end)
    if (
        start is None
        or "(" in value[end:start]
        or "[" in value[end:start]
        # the grant stands in brackets the chain is in too
        or value.count("(", 0, start) != value.count(")", 0, start)
    ):
        return None
    probe = f"{expression} {value[start:]}"
    head = leading_expression(probe)
    if len(head) <= len(expression) + 1:
        return None  # the operator joins nothing
    granted = qualify_trailing_grant(head, probe)
    read = qualify_trailing_only(granted, probe)
    if not read or drops_words(head, read, probe, whole=False, db=db):
        return None
    stop = (grant_stop(probe, head) if granted != head else None) or len(head)
    cut = start + stop - len(expression) - 1
    while cut < len(value) and not value[cut].isspace():
        cut += 1  # resolve() judges what is glued to the end (``MIT?``)
    if ONLY_WORD.match(value[cut:].lstrip()):
        return None  # "AND GPLv2 only": no reading would keep the "only"
    return value[:cut]


def _before_first_grant(value: str) -> str:
    """The expression that *value* starts with up to its first grant, with
    the brackets the grant stands in closed, when nothing else stands before
    the grant (``MIT`` of ``MIT or later OR ISC``, ``(MIT)`` of ``(MIT or
    later) OR ISC``), else ``""``."""
    for word in _RE_OR_WORD.finditer(value):
        if grant_end(value, word.start()) is not None:
            head = value[: word.start()].rstrip()
            head += ")" * max(head.count("(") - head.count(")"), 0)
            return head if leading_expression(head) == head else ""
    return ""
