# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Shared by the ``match`` tests."""

from matcher_db import Lic

from licenseid.resolvertypes import Resolution

# GPL-2.0 as the List has it: -only and -or-later in use, the bare ID
# deprecated with no successor, and GPL-2.0+ replaced by -or-later.
GPL2 = (
    Lic("GPL-2.0-only", "GNU General Public License v2.0 only"),
    Lic("GPL-2.0-or-later", "GNU General Public License v2.0 or later"),
    Lic("GPL-2.0", "GNU General Public License v2.0 only", is_deprecated=True),
)
GPL2_PLUS = Lic(
    "GPL-2.0+",
    "GNU General Public License v2.0 or later",
    is_deprecated=True,
    superseded_by="GPL-2.0-or-later",
)


#: The start of the reason a refusal gets when no reader gave it one
#: (``licenseid.resolvereason.no_reading``, P5 of the contract batch).
NOT_FOUND = "not found: "


def no_reader_reason(reason: str | None) -> bool:
    """Whether *reason* is the one a value gets that no reader claimed."""
    return reason is not None and reason.startswith(NOT_FOUND)


def summary(r: Resolution) -> tuple[object, ...]:
    """What a resolve test compares: the expression, the category, the step
    kinds, each expansion and whether it applied, and the candidates."""
    return (
        r["expression"],
        r["category"],
        [s["kind"] for s in r["steps"]],
        [(s["kind"], s["applied"]) for s in r["expansions"]],
        r["candidates"],
    )
