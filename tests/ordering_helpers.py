# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Shared by the ordering tests: a ranked candidate, its IDs, the "or later"
phrasings every reader of the grant is held to."""
# pylint: disable=missing-function-docstring

from licenseid.types import InternalMatch

HEADER_OR_LATER = "either version 2, or (at your option) any later version"


# Each phrase: does the tie-breaker read it as "or later" (classify), and does
# the ID path (identifiers) resolve "GPL-2.0 <phrase>" to -or-later?
PHRASES: dict[str, tuple[bool, bool]] = {
    "or (at your option) any later version": (True, True),
    "or later": (True, True),
    "or any later version": (True, True),
    "or a later version": (True, True),
    "or newer": (True, True),
    "or, at your option, any later version": (True, True),
    "or\n * (at your option) any later version": (True, True),
    "or\n// (at your option)\n// any later version": (True, True),
    "or\n# any later version": (True, True),
    "or\n * a later version": (True, True),
    "(or later)": (True, True),
    "[or later]": (True, True),
    "+ or later": (True, True),
    "\n// or later": (True, True),
    "\n * or (at your option) any\n * later version": (True, True),
    "or,\n// a later version": (True, True),
    "or a laterally": (False, False),
    "not any later version": (False, False),
    "no any later version": (False, False),
    "not or a later version": (False, False),
    "not or newer": (False, False),
    "not or later": (False, False),
}


def im(
    license_id: str, score: float, *, deprecated: bool = False, pop: int = 0
) -> InternalMatch:
    """A ranked candidate, as _rank_candidates builds it."""
    return InternalMatch(
        license_id=license_id,
        method="text",
        exact=False,
        score=score,
        similarity=score,
        coverage=score,
        base_score=score,
        pop_score=pop,
        is_deprecated=deprecated,
        best_window="",
    )


def ids(ranked: list[InternalMatch]) -> list[str]:
    return [r["license_id"] for r in ranked]
