# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The result of ``licenseid.resolve``: the types and the fixed vocabularies.

A step is something the resolver did to the input (or declined to do, with
``applied`` false). Its ``kind`` is one of a closed set; a consumer ignores a
kind it does not know. Categories are ordered by how much the resolver had
to decide: the category of a value is the weakest of its steps.
"""

from typing import Final, Literal, TypedDict

# Every kind of step, in the family it belongs to. A: the same text with only
# its form changed (no decision). B: the resolver decides which licence is
# meant. C: an expansion of a qualifier (``-only``, ``-or-later``).
LEXICAL_KINDS: Final = frozenset({"brackets", "id_case", "trim"})
DECISION_KINDS: Final = frozenset(
    {
        "separator",
        "version_spelling",
        "listed_name",
        "deprecated_equal_successor",
        "deprecated_ambiguous",
    }
)
EXPANSION_KINDS: Final = frozenset(
    {"plus_to_or_later", "stated_qualifier", "assumed_only"}
)

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


class ListInfo(TypedDict):
    """One list the answer rests on."""

    id: str
    name: str
    version: str | None
    url: str | None
    license: str
    provides: list[str]
    id_authority: bool


class Resolution(TypedDict):
    """What ``resolve`` returns for one declared value.

    ``expression`` is the SPDX expression to record, or None when the value
    cannot be recorded as one (``candidates`` then lists what it might be,
    sorted). ``steps`` are the applied or declined changes in order;
    ``expansions`` hold the qualifier steps, kept apart from ``steps``.
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
