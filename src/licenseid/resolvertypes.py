# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The result of ``licenseid.resolver``: the types and the fixed vocabularies.

A step is something the resolver did to the input (or declined to do, with
``applied`` false). Its ``kind`` is one of a closed set; a consumer ignores a
kind it does not know. Categories are ordered by how much the resolver had
to decide: the category of a value is the weakest of its steps, or of the
floor a step sets (an unbalanced ``unquote`` counts as ``separator``).
"""

from typing import Final, Literal, TypedDict

# The steps that change only the form of the text and decide nothing; the
# others are the resolver's decisions or an expansion of a qualifier.
LEXICAL_KINDS: Final = frozenset(
    {"brackets", "id_case", "trim", "unquote", "whitespace"}
)

SPDX_LIST: Final = "spdx-license-list"

# What a list must provide for a step of this kind to cite it. A kind that is
# not here rests on no list (a trimmed space, brackets) and cites none. An
# "or later" the author wrote still rests on the -or-later ID being in use.
# ``drop`` is not here on purpose: it is a step that did not apply, and no
# list vouched for a reading that was refused.
LIST_PROVIDES: Final = {
    "id_case": "ids",
    "separator": "ids",
    "version_spelling": "ids",
    "listed_name": "names",
    "deprecated_equal_successor": "deprecation",
    "deprecated_ambiguous": "deprecation",
    "plus_to_or_later": "ids",
    "stated_qualifier": "ids",
    "assumed_only": "deprecation",
}

Category = Literal[
    "exact",
    "lexical",
    "plus_to_or_later",
    "stated_qualifier",
    "separator",
    "version_spelling",
    "listed_name",
    "deprecated_equal_successor",
    "deprecated_ambiguous",
    "assumed_only",
    "expression",
    "malformed",
    "unresolved",
]

Trust = Literal["identity", "list_data", "author_words", "resolver_rule", "none"]

# The weakest-wins order of the categories that give an expression, then the
# ones that do not.
CATEGORY_ORDER: Final[tuple[Category, ...]] = (
    "exact",
    "lexical",
    "listed_name",
    "deprecated_equal_successor",
    "plus_to_or_later",
    "stated_qualifier",
    "separator",
    "version_spelling",
    "deprecated_ambiguous",
    "assumed_only",
    "expression",
    "malformed",
    "unresolved",
)

TRUST: Final[dict[Category, Trust]] = {
    "exact": "identity",
    "lexical": "identity",
    "listed_name": "list_data",
    "deprecated_equal_successor": "list_data",
    "plus_to_or_later": "list_data",
    "stated_qualifier": "author_words",
    "separator": "resolver_rule",
    "version_spelling": "resolver_rule",
    "deprecated_ambiguous": "list_data",
    "assumed_only": "none",
    "expression": "none",
    "malformed": "none",
    "unresolved": "none",
}

Step = TypedDict(
    "Step",
    {
        "kind": str,
        "applied": bool,
        "from": str,
        "to": str,
        "list": str,
        "detail": str,
    },
)


class Resolver(TypedDict):
    """Who resolved."""

    name: str
    version: str
    url: str
    purl: str


#: Where ``resolve()`` read a list: the licence database, or the bundle
#: shipped in the wheel, read into memory.
ListSource = Literal["database", "packaged"]
#: What ``resolve(source=...)`` takes: one of those, or ``auto`` to choose.
Source = Literal["auto", "database", "packaged"]


class ListInfo(TypedDict):
    """One list the answer rests on, and where it was read (``source``)."""

    id: str
    name: str
    version: str | None
    source: ListSource
    url: str | None
    license: str
    provides: list[str]
    id_authority: bool


class Resolution(TypedDict):
    """What ``resolve`` returns for one declared value.

    ``expression`` is the SPDX expression to record, or None when the value
    names no single licence. A bare deprecated ID (``GPL-3.0``) is returned as
    written (category ``assumed_only``), with the licences it might be in
    ``candidates``, sorted. ``steps`` are the applied or declined changes in order;
    ``expansions`` hold the qualifier steps, kept apart from ``steps``.
    ``reason`` says why a value was refused, as ``CONDITION[: DETAIL]``
    (``character dropped: '?'``, ``lone surrogate``); None for every other
    answer.
    """

    input: str
    expression: str | None
    category: Category
    trust: Trust
    steps: list[Step]
    expansions: list[Step]
    candidates: list[str]
    resolver: Resolver
    lists: list[ListInfo]
    reason: str | None


def step(kind: str, applied: bool, source: str, target: str, detail: str = "") -> Step:
    """One step of the public shape, citing the list if its kind rests on one."""
    return {
        "kind": kind,
        "applied": applied,
        "from": source,
        "to": target,
        "list": SPDX_LIST if kind in LIST_PROVIDES else "",
        "detail": detail,
    }
