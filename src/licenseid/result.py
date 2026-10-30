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
by :func:`text_field`.
"""

from typing import Any

from licenseid.resolvertypes import Resolution, Step
from licenseid.resolvesemicolon import REASON as NO_OPERATOR
from licenseid.types import Detection, InternalMatch, RawMatch

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
        license_id=raw["license_id"],
        method=raw["method"],
        exact=bool(raw["exact"]),
        score=round(max(0.0, min(raw["score"], 1.0)), _DIGITS),
        similarity=_rounded(raw["similarity"]),
        coverage=_rounded(raw["coverage"]),
        is_spdx=bool(raw.get("is_spdx", False)),
        is_osi_approved=bool(raw.get("is_osi_approved", False)),
        is_fsf_libre=bool(raw.get("is_fsf_libre", False)),
    )


def json_line(result: Detection | Resolution) -> str:
    """*result*, a detection or a resolution, as one line of JSON Lines, in
    the JSON Canonicalization Scheme (RFC 8785): sorted keys, no white
    space, ECMAScript numbers (1.0 is 1), so equal results print equal
    bytes. A detection is ASCII: an ID is, and no licence text is in it. A
    resolution holds the value as given (``input``, an operand's ``text``),
    which RFC 8785 writes as it is, in UTF-8, escaping only ``"``, ``\\``
    and the control characters."""
    # Only --json needs it, so detect() and the API do not import it.
    import rfc8785  # pylint: disable=import-outside-toplevel

    # Every value of either shape is JSON; a TypedDict is no Mapping of the
    # union rfc8785 declares, to a type checker.
    fields: Any = result
    return rfc8785.dumps(fields).decode("utf-8")


def text_line(result: Detection) -> str:
    """*result* as KEY=VALUE fields on one line; a value nothing measured
    is empty (``SIMILARITY=``), so every line has the same fields."""

    def number(value: float | None) -> str:
        return "" if value is None else f"{value:.{_DIGITS}f}"

    return (
        f"LICENSE_ID={result['license_id']} METHOD={result['method']} "
        f"EXACT={str(result['exact']).lower()} "
        f"SCORE={number(result['score'])} "
        f"SIMILARITY={number(result['similarity'])} "
        f"COVERAGE={number(result['coverage'])}"
    )


def text_field(value: str | None) -> str:
    r"""*value* as the VALUE of one ``KEY=VALUE`` field of a line whose
    fields a space separates: Python's ``unicode_escape`` (a backslash, a
    tab, a line break, a control and every character outside ASCII become a
    backslash escape: ``\\``, ``\t``, ``\n``, ``\xe9``, ``\u201c``) and
    a space ``\x20``, as the PyPI sample writes its fields
    (``tools/pypi_licence_sample/answer.py``). A field is one word of ASCII,
    whatever the value, so ``awk``, ``cut -d' '`` and ``read -r`` split the
    line into its fields on any locale; ``=`` is kept, as a key ends at the
    first one. None is empty, as is ``""``. :func:`read_text_field`
    reverses it."""
    if value is None:
        return ""
    return value.encode("unicode_escape").decode("ascii").replace(" ", "\\x20")


def read_text_field(field: str) -> str:
    """The value :func:`text_field` wrote as *field*."""
    return field.encode("ascii").decode("unicode_escape")


def _fields(**values: str | None) -> str:
    """``KEY=VALUE`` fields, in the order given, each value by
    :func:`text_field`."""
    return " ".join(f"{key}={text_field(value)}" for key, value in values.items())


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
        _fields(
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
        _fields(STEP=step["kind"], FROM=step["from"], TO=step["to"]) for step in applied
    ]
    reason = resolution["reason"]
    if reason is not None:
        lines.append(_fields(REASON=reason))
    if reason == NO_OPERATOR:
        lines += [
            _fields(
                OPERAND=operand["text"],
                EXPRESSION=operand["expression"],
                CATEGORY=operand["category"],
            )
            for operand in resolution["operands"]
        ]
    return lines
