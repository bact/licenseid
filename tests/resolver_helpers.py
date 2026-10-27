# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Shared by the ``resolve`` tests."""

from licenseid.resolvertypes import Resolution


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
