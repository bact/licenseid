# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A ``;`` between licences, an operator the author did not state (task T8b;
0.7.0 plan, decisions P81 to P86).

``MIT ; Apache 2`` names two licences and does not say how they combine:
``Apache-2.0 AND MIT`` and ``Apache-2.0 OR MIT`` are both fair readings. It
resolves to no expression, and nothing is guessed. Recording the two
licences is still useful: a caller who asks only whether every one of them
is OSI approved has an answer whatever the operator.

:func:`semicolon_parts` cuts a value at the ``;`` outside brackets;
:func:`read_semicolon_list` reads each part as the same text would be read
alone, through the reader its caller passes in, and makes the value
``unresolved`` with the reason :data:`REASON` and one operand for each part,
whatever its own category.

- A ``;`` at the very end is an ending, not an operator (``MIT; ISC;``
  is two parts, P77); a ``;`` inside brackets belongs to the bracket's
  content (``(MIT; ISC) OR GPL-2.0`` is the compound reader's).
- An empty part (``MIT;;ISC``, ``; MIT``) is no list: the value stays as
  it was refused (P82).
- A ``;`` beside an operator word (``MIT; OR ISC``) ends an operand, and the
  compound reader reads it before this module is asked (P79, P84); a part
  that starts with an operator word names no licence besides.
- Fewer than two parts that name a licence, or would but for a mark they
  drop (``Apache 2.0?``), is no list of licences (``MIT; Copyright (c)
  2016``), and neither is one where no part resolves (``-MIT ; -MIT``): the
  value stays as it was (P83, P88).
- A part that starts or ends with an operator word in any case (``MIT; OR
  ISC; Apache-2.0``) means an operator was stated: no list (P84).
- Quote marks are not tracked: a ``;`` inside quotes splits. ``,`` and ``/``
  are never a separator here (P84).

Standard library and ``licenseid`` types only; no state, no lookup of its
own.
"""

from collections.abc import Callable
from typing import Final, NamedTuple

from licenseid.dropguard import trim_end_mark
from licenseid.resolvecompound import operand_of
from licenseid.resolveleaf import Found
from licenseid.resolvertypes import Operand

#: The reason of a value of several licences with no stated operator.
REASON: Final = "operator not stated: ;"
_OPENING: Final = "([{"
_CLOSING: Final = ")]}"
_OPERATOR_WORDS: Final = frozenset({"and", "or", "with"})


class Part(NamedTuple):
    """One part of the value: its text, without the white space around it,
    and where it starts in the value (a code point)."""

    text: str
    start: int


def semicolon_parts(text: str) -> list[Part] | None:
    """The parts of *text* between its top-level ``;``, or None when it is
    not a list: fewer than two parts, an empty part, or a bracket that does not
    close (see the module docstring).
    The one ``;`` at the end, if any, is an ending and left off."""
    body = text.rstrip()
    ended = trim_end_mark(body, ";")
    if ended is not None:
        body = ended
    cuts = _cuts(body)
    if cuts is None or len(cuts) < 2:
        return None
    parts = []
    for begin, end in cuts:
        part = body[begin:end]
        stripped = part.strip()
        if not stripped or _operator_beside(stripped):
            return None
        parts.append(Part(stripped, begin + len(part) - len(part.lstrip())))
    return parts


def _cuts(body: str) -> list[tuple[int, int]] | None:
    """The ``[start, end)`` of each piece of *body* between its ``;`` outside
    brackets, or None for brackets that do not close or a close before its
    open."""
    cuts = []
    depth = begin = 0
    for index, char in enumerate(body):
        if char in _OPENING:
            depth += 1
        elif char in _CLOSING:
            depth -= 1
            if depth < 0:
                return None
        elif char == ";" and depth == 0:
            cuts.append((begin, index))
            begin = index + 1
    cuts.append((begin, len(body)))
    return cuts if depth == 0 else None


def _operator_beside(part: str) -> bool:
    """Whether *part* starts or ends with an operator word in any case, so
    that the ``;`` next to it is not the only operator stated (``MIT; OR
    ISC; Apache-2.0``). Prose such as ``and others`` blocks a list too: the
    narrow side (P84)."""
    words = part.split()
    return words[0].casefold() in _OPERATOR_WORDS or (
        words[-1].casefold() in _OPERATOR_WORDS
    )


def _names_a_licence(found: Found) -> bool:
    """Whether a part's reading named a licence, or would have but for a mark
    or a word it would drop (``Apache 2.0?``: the author named one, and
    doubted it)."""
    return found.expression is not None or any(s["kind"] == "drop" for s in found.steps)


def read_semicolon_list(
    parts: list[Part],
    start: int,
    read: Callable[[str], tuple[Found, bool]],
    found: Found,
) -> tuple[list[Operand], bool] | None:
    """Make *found* the refusal ``operator not stated: ;`` of a value of
    *parts* (which start at code point *start* of the raw input), if two or
    more of them name a licence, and return the operands, one for each part
    as it would be read alone by *read* (its :class:`Found` and whether the
    expression parser ran). None, with *found* as it was, otherwise."""
    cache: dict[str, tuple[Found, bool]] = {}
    for part in parts:
        if part.text not in cache:
            cache[part.text] = read(part.text)
    readings = [cache[part.text][0] for part in parts]
    named = sum(_names_a_licence(found) for found in readings)
    if named < 2 or all(found.expression is None for found in readings):
        return None  # fewer than two licences, or none that resolves (P88)
    operands = [
        operand_of(part.text, start + part.start, cache[part.text][0]) for part in parts
    ]
    found.expression, found.category, found.reason = None, "unresolved", REASON
    return operands, any(parsed for _, parsed in cache.values())
