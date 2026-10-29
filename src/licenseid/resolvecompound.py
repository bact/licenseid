# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The operands of a declared value, each read as it would be alone.

A value that names one licence is one operand; :func:`operand_of` puts the
reading of a leaf (:mod:`licenseid.resolveleaf`) in the public shape.
"""

from licenseid.resolveleaf import Found, category_of
from licenseid.resolvertypes import TRUST, Operand


def operand_of(text: str, start: int, found: Found) -> Operand:
    """The public form of the leaf *text*, which starts at code point
    *start* of the raw input, read into *found*. A leaf that resolved to
    nothing, and was not refused, keeps no step."""
    category = category_of(found)
    kept = found.expression is not None or found.reason is not None
    return {
        "text": text,
        "span": [start, start + len(text)],
        "expression": found.expression,
        "category": category,
        "trust": TRUST[category],
        "steps": list(found.steps) if kept else [],
        "expansions": list(found.expansions) if kept else [],
        "candidates": list(found.candidates),
        "reason": found.reason,
    }
