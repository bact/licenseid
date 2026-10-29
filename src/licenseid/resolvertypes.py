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

#: The version of the result's shape: 2 has ``operands``, ``components``
#: and ``Step.by``, and no ``expression`` category.
SCHEMA: Final = 2

# The steps that change only the form of the text and decide nothing; the
# others are the resolver's decisions or an expansion of a qualifier.
LEXICAL_KINDS: Final = frozenset(
    {
        "brackets",
        "dedupe",
        "id_case",
        "operator_case",
        "reorder",
        "trailing_name",
        "trim",
        "trove_path",
        "unquote",
        "whitespace",
    }
)

SPDX_LIST: Final = "spdx-license-list"
#: PyPA's trove classifiers (``License :: ...``), as ``licenseid.trovenames``
#: records them: a vocabulary of names, never an authority on IDs.
TROVE_LIST: Final = "pypi-trove-classifiers"
#: The steps that rest on the trove list, not on the SPDX one.
TROVE_KINDS: Final = frozenset({"trove_name", "trove_path"})

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
    "trove_name": "names",
    "trove_path": "names",
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
    "trove_name",
    "deprecated_ambiguous",
    "assumed_only",
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
    "trove_name",
    "deprecated_ambiguous",
    "assumed_only",
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
    "trove_name": "resolver_rule",
    "deprecated_ambiguous": "list_data",
    "assumed_only": "none",
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
        "by": str,
    },
)


class Resolver(TypedDict):
    """Who resolved."""

    name: str
    version: str
    url: str
    purl: str


class Component(TypedDict):
    """A tool that took part beside the resolver (the expression parser)."""

    name: str
    version: str
    url: str
    purl: str


class Operand(TypedDict):
    """One leaf of the value: one word, an ID or a reference, or ``X WITH
    Y``, with its "+" or grant, read as that text would be alone (a loose ID
    with a space is no operand; per operand only a balanced pair of quotes).
    ``span`` is ``[start, end)`` in code points of the raw ``input``;
    ``text`` is ``input[start:end]``."""

    text: str
    span: list[int]
    expression: str | None
    category: Category
    trust: Trust
    steps: list[Step]
    expansions: list[Step]
    candidates: list[str]
    reason: str | None


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

    ``schema`` is the version of this shape (:data:`SCHEMA`). ``expression``
    is the SPDX expression to record, in canonical order, or None when the
    value names nothing, or a compound has an operand that names nothing. A
    bare deprecated ID (``GPL-3.0``) is returned as written (category
    ``assumed_only``), with the licences it might be in ``candidates``,
    sorted. ``steps`` are the applied or declined changes in order: those of
    the whole value, of each operand, then of the compound; ``expansions``
    hold the qualifier steps, kept apart from ``steps``. ``operands`` holds
    each licence named, as it reads alone, in the order written;
    ``components`` the tools besides licenseid that took part (the
    expression parser, for a compound). ``reason`` says why a value was
    refused, as ``CONDITION[: DETAIL]`` (``character dropped: U+003F``,
    ``operand not resolved: Foo``, ``operand of several words: BSD
    3-Clause``); None for every other answer.
    """

    schema: int
    input: str
    expression: str | None
    category: Category
    trust: Trust
    steps: list[Step]
    expansions: list[Step]
    candidates: list[str]
    operands: list[Operand]
    resolver: Resolver
    components: list[Component]
    lists: list[ListInfo]
    reason: str | None


def _list_of(kind: str) -> str:
    """The list a step of *kind* rests on, or ``""`` if it rests on none."""
    if kind in TROVE_KINDS:
        return TROVE_LIST
    return SPDX_LIST if kind in LIST_PROVIDES else ""


def step(kind: str, applied: bool, source: str, target: str, detail: str = "") -> Step:
    """One step of the public shape, citing the list if its kind rests on one."""
    return {
        "kind": kind,
        "applied": applied,
        "from": source,
        "to": target,
        "list": _list_of(kind),
        "detail": detail,
        "by": "",  # licenseid did it; a step of another tool names it
    }
