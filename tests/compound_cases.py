# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Generated compound values for the resolver tests (task T7).

Import as ``from compound_cases import ...`` (tests have no
``__init__.py``). Every value is built from :data:`OPERANDS` and
:data:`SHAPES` in a fixed order, so the list is the same on every run and
under every ``PYTHONHASHSEED``.
"""

from itertools import product

#: One operand of each kind the resolver reads alone: an ID as written, in
#: other case, loosely written, with "+", deprecated (split and renamed), a
#: reference, an exception, a grant in words, in quotes; and some it does
#: not read: an unknown word, a "+" after a qualifier, a dropped mark.
OPERANDS = (
    "MIT",
    "isc",
    "Apache2",
    "GPL-2.0+",
    "GPL-3.0",
    "StandardML-NJ",
    "LicenseRef-x",
    "DocumentRef-d:LicenseRef-y",
    "Apache-2.0 WITH LLVM-exception",
    "GPL-2.0 or later",
    '"BSD-3-Clause"',
    "Foo",
    "GPL-2.0-only+",
    "MIT?",
)

#: How two or three operands are joined.
SHAPES = (
    "{a} OR {b}",
    "{a} and {b}",
    "({a} OR {b}) AND {c}",
    "{a} AND ({b} OR {c})",
    "[{a} OR {b}]",
    "{a} OR {b} OR {a}",
)

#: Operands that read alone as one licence, for the shapes that need three.
_READ = OPERANDS[:11]
#: Every ninth pair: a short list that still meets every operand on both sides.
_STRIDE = 9


def generated_compounds() -> list[str]:
    """Every ninth pair of distinct operands in each two-operand shape, then a
    fixed run of three-operand shapes; distinct values, in a fixed order."""
    values: list[str] = []
    pairs = [(a, b) for a, b in product(OPERANDS, OPERANDS) if a != b]
    for shape in SHAPES:
        if "{c}" in shape:
            triples = zip(_READ, _READ[1:] + _READ[:1], _READ[2:] + _READ[:2])
            values += [shape.format(a=a, b=b, c=c) for a, b, c in triples]
        else:
            values += [shape.format(a=a, b=b) for a, b in pairs[::_STRIDE]]
    return list(dict.fromkeys(values))
