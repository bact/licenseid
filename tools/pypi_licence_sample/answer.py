# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What a fixture pins of a ``licenseid.resolve()`` answer, and how a TSV
file writes it. Shared by ``export`` and by ``tests/resolver_corpus.py``, so
the fixtures and the guard read one definition.

Standard library and ``licenseid`` only.
"""

from collections.abc import Mapping
from typing import Final, NamedTuple

from licenseid.resolvertypes import Resolution

#: The field of a ``None`` expression or an empty list.
NONE_FIELD: Final = "-"
#: The columns of an answer, in the order of the files.
ANSWER_COLUMNS: Final = (
    "expression_0_6_0",
    "category_0_6_0",
    "candidates_0_6_0",
    "steps_0_6_0",
    "expansions_0_6_0",
    "trust_0_6_0",
    "input_same_0_6_0",
)
_YES: Final = "yes"
_NO: Final = "no"


class Answer(NamedTuple):
    """The pinned part of a result: the expression, the category, the
    candidates, the kinds of the steps (in order), the kinds of the expansions
    (a ``!`` after one that did not apply), the trust, and whether ``input``
    is the raw value."""

    expression: str | None
    category: str
    candidates: tuple[str, ...]
    steps: tuple[str, ...]
    expansions: tuple[str, ...]
    trust: str
    input_same: bool


def escape_field(value: str) -> str:
    """*value* as one TSV field: Python ``unicode_escape`` (a tab, a newline,
    a backslash, a non-ASCII character and a lone surrogate survive)."""
    return value.encode("unicode_escape").decode("ascii")


def unescape_field(field: str) -> str:
    """Inverse of :func:`escape_field`."""
    return field.encode("ascii").decode("unicode_escape")


def dump_list(items: tuple[str, ...]) -> str:
    """A list of words as one field: comma-joined, ``-`` when empty."""
    return ",".join(items) or NONE_FIELD


def load_list(field: str) -> tuple[str, ...]:
    """Inverse of :func:`dump_list`."""
    return () if field == NONE_FIELD else tuple(field.split(","))


def answer_of(value: str, result: Resolution) -> Answer:
    """The pinned part of *result*, the answer to *value*."""
    return Answer(
        result["expression"],
        result["category"],
        tuple(result["candidates"]),
        tuple(s["kind"] for s in result["steps"]),
        tuple(s["kind"] + ("" if s["applied"] else "!") for s in result["expansions"]),
        result["trust"],
        result["input"] == value,
    )


def answer_fields(answer: Answer) -> tuple[str, ...]:
    """The TSV fields of *answer*, in :data:`ANSWER_COLUMNS` order."""
    return (
        NONE_FIELD if answer.expression is None else escape_field(answer.expression),
        answer.category,
        dump_list(answer.candidates),
        dump_list(answer.steps),
        dump_list(answer.expansions),
        answer.trust,
        _YES if answer.input_same else _NO,
    )


def answer_from_row(row: Mapping[str, str]) -> Answer:
    """The answer a row records in its :data:`ANSWER_COLUMNS`."""
    expression = row[ANSWER_COLUMNS[0]]
    return Answer(
        None if expression == NONE_FIELD else unescape_field(expression),
        row[ANSWER_COLUMNS[1]],
        load_list(row[ANSWER_COLUMNS[2]]),
        load_list(row[ANSWER_COLUMNS[3]]),
        load_list(row[ANSWER_COLUMNS[4]]),
        row[ANSWER_COLUMNS[5]],
        row[ANSWER_COLUMNS[6]] == _YES,
    )
