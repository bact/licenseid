# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The public form of a match, and its two output lines.

A tier's record carries its ranking state: a raw score on a scale of its
own (a tag 1.0, an exact ID or name 1.0 or 1.02, a name that only shares
the input's words 1.01, a text match up to about 1.08 with its bonuses)
and, for a text match, the aligned window and the popularity and
deprecation keys. The public form keeps what a reader can use, the same
keys for every method.

A resolution (``licenseid.match()``) is public as it is returned; its text
lines (``licenseid match``) are :func:`resolution_lines`, each value written
by :func:`text_field`. Every other command's result is one record
(:func:`fields_line`, :func:`record_json`).
"""

import re
from collections.abc import Mapping
from typing import Any

from licenseid.resolvertypes import Resolution, Step
from licenseid.resolvesemicolon import REASON as NO_OPERATOR
from licenseid.types import Detection, InternalMatch, RawMatch

# The value of one field: a text, a flag, or nothing (empty in a text line,
# null in JSON).
FieldValue = str | bool | None

# Digits kept in score, similarity and coverage: the text output prints
# four, so JSON and text agree.
_DIGITS = 4


def _rounded(value: float | None) -> float | None:
    # + 0.0 turns -0.0 into 0.0, which text prints as "-0.0000" but JSON as 0.
    return None if value is None else round(value, _DIGITS) + 0.0


def public_result(raw: RawMatch | InternalMatch) -> Detection:
    """*raw* as detect() returns it. The ranking key is capped to 0-1: above
    1 it only orders a tier's own results, and the order is in the list."""
    return Detection(
        expression=raw["license_id"],
        method=raw["method"],
        exact=bool(raw["exact"]),
        score=round(max(0.0, min(raw["score"], 1.0)), _DIGITS),
        similarity=_rounded(raw["similarity"]),
        coverage=_rounded(raw["coverage"]),
        is_spdx=bool(raw.get("is_spdx", False)),
        is_osi_approved=_judged(raw.get("is_osi_approved", False)),
        is_fsf_libre=_judged(raw.get("is_fsf_libre", False)),
    )


def _judged(flag: bool | None) -> bool | None:
    """An OSI or FSF *flag* as a bool, None kept: an expression with an
    operand nobody judged has no answer (``licenseid.exprflags``)."""
    return None if flag is None else bool(flag)


def json_line(result: Detection | Resolution | Mapping[str, object]) -> str:
    """*result*, a detection, a resolution or a record of
    :func:`record_json`, as one line of JSON Lines, in
    the JSON Canonicalization Scheme (RFC 8785): sorted keys, no white
    space, ECMAScript numbers (1.0 is 1), so equal results print equal
    bytes. A detection is ASCII: an ID is, and no licence text is in it. A
    resolution holds the value as given (``input``, an operand's ``text``),
    which RFC 8785 writes as it is, in UTF-8, escaping only ``"``, ``\\``
    and the control characters."""
    # Only --json needs it, so detect() and the API do not import it.
    import rfc8785  # pylint: disable=import-outside-toplevel

    # Every value of each shape is JSON; a TypedDict is no Mapping of the
    # union rfc8785 declares, to a type checker.
    fields: Any = result
    return rfc8785.dumps(fields).decode("utf-8")


def text_line(result: Detection) -> str:
    """*result* as one line of ``KEY=VALUE`` fields (:func:`fields_line`); a
    value nothing measured is empty (``SIMILARITY=``), so every line has the
    same fields."""

    def number(value: float | None) -> str | None:
        return None if value is None else f"{value:.{_DIGITS}f}"

    return fields_line(
        EXPRESSION=result["expression"],
        METHOD=result["method"],
        EXACT=result["exact"],
        SCORE=number(result["score"]),
        SIMILARITY=number(result["similarity"]),
        COVERAGE=number(result["coverage"]),
    )


def no_detection_line() -> str:
    """The line ``detect`` prints when nothing matches (exit 1): every field
    of :func:`text_line`, each empty, so a reader finds the same keys."""
    return fields_line(
        EXPRESSION=None,
        METHOD=None,
        EXACT=None,
        SCORE=None,
        SIMILARITY=None,
        COVERAGE=None,
    )


def no_detection_json() -> str:
    """The object ``detect --json`` prints when nothing matches: every key of
    a :class:`licenseid.types.Detection`, each ``null``."""
    return json_line(dict.fromkeys(Detection.__annotations__))


# What a value holds that would end its field or its line, or be read as an
# escape: each is written as a backslash escape, and nothing else is.
_ESCAPES = {"\\": "\\\\", "\t": "\\t", "\r": "\\r", "\n": "\\n"}
_ESCAPED = str.maketrans(_ESCAPES)
# What read_text_field decodes: the four above, and the escapes output.echo
# writes for a character standard output cannot encode.
_ESCAPE_RE = re.compile(
    r"\\(?:(?P<char>[\\trn])"
    r"|x(?P<x>[0-9a-f]{2})|u(?P<u>[0-9a-f]{4})|U(?P<U>[0-9a-f]{8}))"
)
_UNESCAPED = {"\\\\": "\\", "\\t": "\t", "\\r": "\r", "\\n": "\n"}


def text_field(value: str | None) -> str:
    r"""*value* as the VALUE of one ``KEY=VALUE`` field: as it is, but for a
    backslash, a tab, a carriage return and a line feed, written ``\\``,
    ``\t``, ``\r`` and ``\n``. A field then holds no tab and a line no
    line break, so ``cut -f`` and ``awk -F'\t'`` split a line into its
    fields; ``=`` is kept, as a key ends at the first one. None is empty, as
    is ``""``. A character standard output cannot encode is escaped when the
    line is written (``output.echo``); :func:`read_text_field` reverses
    both."""
    return "" if value is None else value.translate(_ESCAPED)


def read_text_field(field: str) -> str:
    r"""The value :func:`text_field` wrote as *field*, with the ``\xHH``,
    ``\uHHHH`` and ``\UHHHHHHHH`` escapes of ``output.echo`` decoded. Every
    backslash of a value was escaped, so any other one starts an escape."""

    def decoded(escape: re.Match[str]) -> str:
        if escape.group("char"):
            return _UNESCAPED[escape.group(0)]
        return chr(int(escape.group("x") or escape.group("u") or escape.group("U"), 16))

    return _ESCAPE_RE.sub(decoded, field)


def fields_line(**values: FieldValue) -> str:
    """``KEY=VALUE`` fields, in the order given, one tab between them, each
    value by :func:`text_field`, a flag as ``true`` or ``false``: the line
    every command prints."""
    return "\t".join(
        f"{key}={_flag(value) if isinstance(value, bool) else text_field(value)}"
        for key, value in values.items()
    )


def _flag(value: bool) -> str:
    return "true" if value else "false"


def record_json(**values: FieldValue) -> str:
    """The record :func:`fields_line` writes for *values*, as one line of
    JSON (:func:`json_line`): each key in lower case, a flag a JSON
    boolean, nothing ``null``."""
    return json_line({key.lower(): value for key, value in values.items()})


def resolution_lines(resolution: Resolution) -> list[str]:
    """*resolution* as ``licenseid match`` prints it, one data point per line:

    - ``EXPRESSION=<expr> CATEGORY=<category> TRUST=<trust>`` (an empty
      ``EXPRESSION=`` when there is none);
    - ``STEP=<kind> FROM=<from> TO=<to>`` for each step applied, in order,
      then for each qualifier applied (``expansions``: ``GPL-2.0+`` has no
      other step);
    - ``REASON=<reason>`` for a refusal;
    - ``OPERAND=<text> EXPRESSION=<expr> CATEGORY=<category>`` for each
      licence of a value that names several without an operator
      (``MIT ; Apache 2``).

    Every value is written by :func:`text_field`."""
    lines = [
        fields_line(
            EXPRESSION=resolution["expression"],
            CATEGORY=resolution["category"],
            TRUST=resolution["trust"],
        )
    ]
    applied: list[Step] = [
        step
        for step in (*resolution["steps"], *resolution["expansions"])
        if step["applied"]
    ]
    lines += [
        fields_line(STEP=step["kind"], FROM=step["from"], TO=step["to"])
        for step in applied
    ]
    reason = resolution["reason"]
    if reason is not None:
        lines.append(fields_line(REASON=reason))
    if reason == NO_OPERATOR:
        lines += [
            fields_line(
                OPERAND=operand["text"],
                EXPRESSION=operand["expression"],
                CATEGORY=operand["category"],
            )
            for operand in resolution["operands"]
        ]
    return lines
