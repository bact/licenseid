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

from licenseid.resolvertypes import Resolution, Step

#: The field of a ``None`` expression or an empty list.
NONE_FIELD: Final = "-"
#: The columns of an answer, in the order of the files.
ANSWER_COLUMNS: Final = (
    "expression_0_6_0",
    "category_0_6_0",
    "candidates_0_6_0",
    "steps_0_6_0",
    "step_targets_0_6_0",
    "expansions_0_6_0",
    "expansion_targets_0_6_0",
    "trust_0_6_0",
    "input_same_0_6_0",
    "reason_0_6_0",
)
_YES: Final = "yes"
_NO: Final = "no"
_NOT_APPLIED: Final = "!"
_COMMA: Final = "\\x2c"


class Answer(NamedTuple):
    """The pinned part of a result. Build it by keyword: two swapped tuple
    fields of the same type would pass the type checker.

    ``steps`` and ``expansions`` are the kinds in order, a ``!`` after one
    that did not apply; ``step_targets`` and ``expansion_targets`` the
    ``to`` of each. ``reason`` is ``None`` for every 0.6.0 answer (the field
    came with T6). ``input_same`` says whether ``input`` is the raw value.
    """

    expression: str | None
    category: str
    candidates: tuple[str, ...]
    steps: tuple[str, ...]
    step_targets: tuple[str, ...]
    expansions: tuple[str, ...]
    expansion_targets: tuple[str, ...]
    trust: str
    input_same: bool
    reason: str | None


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


def dump_targets(items: tuple[str, ...]) -> str:
    """Targets as one field: each escaped, a comma written ``\\x2c``, joined
    by commas, ``-`` when there are none. Raises :class:`ValueError` for an
    empty target, which the field could not tell from none."""
    if "" in items:
        raise ValueError("an empty target cannot be written")
    return dump_list(tuple(escape_field(item).replace(",", _COMMA) for item in items))


def load_targets(field: str) -> tuple[str, ...]:
    """Inverse of :func:`dump_targets`."""
    return tuple(unescape_field(item) for item in load_list(field))


def _kinds(steps: list[Step]) -> tuple[str, ...]:
    """The kinds of *steps*, a ``!`` after one that did not apply."""
    return tuple(s["kind"] + ("" if s["applied"] else _NOT_APPLIED) for s in steps)


def answer_of(value: str, result: Resolution) -> Answer:
    """The pinned part of *result*, the answer to *value*."""
    reason = result["reason"]
    return Answer(
        expression=result["expression"],
        category=result["category"],
        candidates=tuple(result["candidates"]),
        steps=_kinds(result["steps"]),
        step_targets=tuple(s["to"] for s in result["steps"]),
        expansions=_kinds(result["expansions"]),
        expansion_targets=tuple(s["to"] for s in result["expansions"]),
        trust=result["trust"],
        input_same=result["input"] == value,
        reason=reason,
    )


def answer_fields(answer: Answer) -> tuple[str, ...]:
    """The TSV fields of *answer*, in :data:`ANSWER_COLUMNS` order."""
    return (
        NONE_FIELD if answer.expression is None else escape_field(answer.expression),
        answer.category,
        dump_list(answer.candidates),
        dump_list(answer.steps),
        dump_targets(answer.step_targets),
        dump_list(answer.expansions),
        dump_targets(answer.expansion_targets),
        answer.trust,
        _YES if answer.input_same else _NO,
        NONE_FIELD if answer.reason is None else escape_field(answer.reason),
    )


def answer_from_row(row: Mapping[str, str]) -> Answer:
    """The answer a row records in its :data:`ANSWER_COLUMNS`."""
    expression, reason = row[ANSWER_COLUMNS[0]], row[ANSWER_COLUMNS[9]]
    return Answer(
        expression=None if expression == NONE_FIELD else unescape_field(expression),
        category=row[ANSWER_COLUMNS[1]],
        candidates=load_list(row[ANSWER_COLUMNS[2]]),
        steps=load_list(row[ANSWER_COLUMNS[3]]),
        step_targets=load_targets(row[ANSWER_COLUMNS[4]]),
        expansions=load_list(row[ANSWER_COLUMNS[5]]),
        expansion_targets=load_targets(row[ANSWER_COLUMNS[6]]),
        trust=row[ANSWER_COLUMNS[7]],
        input_same=row[ANSWER_COLUMNS[8]] == _YES,
        reason=None if reason == NONE_FIELD else unescape_field(reason),
    )


def answer_diff(old: Answer, new: Answer) -> str:
    """The fields that differ, ``name: old -> new``, joined by ``; ``."""
    return "; ".join(
        f"{name}: {before!r} -> {after!r}"
        for name, before, after in zip(Answer._fields, old, new)
        if before != after
    )
