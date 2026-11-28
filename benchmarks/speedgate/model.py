# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Shapes shared by the builders, the runner and the comparison."""

import hashlib
import json
from typing import Any, Final, TypedDict

#: Sets that run ``detect()`` over cases, in the order they are run.
DETECT_SETS: Final = ("core", "prose", "many", "cjk", "options", "roadmap")

#: The width of a rounded score in a result: the public score has 4 places.
SCORE_PLACES: Final = 4


class Case(TypedDict, total=False):
    """One input of a set. ``options`` are ``detect()`` keywords, ``want`` the
    licence a fixture is made from, ``texts_call`` asks for ``texts()`` too."""

    key: str
    text: str
    kind: str
    options: dict[str, Any]
    want: str | None
    texts_call: bool


class Measure(TypedDict, total=False):
    """What one case gave: the top 3 rows, ``TEXTS`` and CPU milliseconds."""

    rows: list[list[Any]]
    texts_row: Any
    texts: Any
    cpu_ms: float
    texts_ms: float
    chars: int
    error: str


def canonical(value: Any) -> str:
    """JSON with sorted keys and no spaces: what a hash is taken of."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    """The SHA-256 of ``canonical(value)``."""
    return hashlib.sha256(canonical(value).encode("ascii")).hexdigest()


def base_id(expression: str | None) -> str | None:
    """An expression without its ``-only``, ``-or-later`` or ``+`` tail, as
    the weak labels are compared (a declared ``GPL-2.0`` meets either)."""
    if not expression:
        return expression
    for tail in ("-only", "-or-later", "+"):
        if expression.endswith(tail):
            return expression[: -len(tail)]
    return expression
