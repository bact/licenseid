# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Generated compounds (``compound_cases``), each with the answer
``resolve()`` gives: characterisation before task T7 reads compounds.

Before T7 a compound is only labelled: category ``expression`` when every
operand is a listed ID or looks like one, ``malformed`` for a "+" after a
stated qualifier, else ``unresolved``; never an expression, never a reason.
"""

import pytest
from compound_cases import generated_compounds
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve

#: The category of each generated compound, before T7.
PINNED: dict[str, str] = {
    "MIT OR isc": "expression",
    'MIT OR "BSD-3-Clause"': "expression",
    "isc OR LicenseRef-x": "expression",
    "Apache2 OR isc": "expression",
    "Apache2 OR Foo": "unresolved",
    "GPL-2.0+ OR DocumentRef-d:LicenseRef-y": "expression",
    "GPL-3.0 OR Apache2": "expression",
    "GPL-3.0 OR GPL-2.0-only+": "malformed",
    "StandardML-NJ OR Apache-2.0 WITH LLVM-exception": "expression",
    "LicenseRef-x OR GPL-2.0+": "expression",
    "LicenseRef-x OR MIT?": "expression",
    "DocumentRef-d:LicenseRef-y OR GPL-2.0 or later": "unresolved",
    "Apache-2.0 WITH LLVM-exception OR GPL-3.0": "expression",
    "GPL-2.0 or later OR MIT": "unresolved",
    'GPL-2.0 or later OR "BSD-3-Clause"': "unresolved",
    '"BSD-3-Clause" OR StandardML-NJ': "expression",
    "Foo OR isc": "unresolved",
    'Foo OR "BSD-3-Clause"': "unresolved",
    "GPL-2.0-only+ OR LicenseRef-x": "malformed",
    "MIT? OR Apache2": "expression",
    "MIT? OR Foo": "unresolved",
    "MIT and isc": "expression",
    'MIT and "BSD-3-Clause"': "expression",
    "isc and LicenseRef-x": "expression",
    "Apache2 and isc": "expression",
    "Apache2 and Foo": "unresolved",
    "GPL-2.0+ and DocumentRef-d:LicenseRef-y": "expression",
    "GPL-3.0 and Apache2": "expression",
    "GPL-3.0 and GPL-2.0-only+": "malformed",
    "StandardML-NJ and Apache-2.0 WITH LLVM-exception": "expression",
    "LicenseRef-x and GPL-2.0+": "expression",
    "LicenseRef-x and MIT?": "expression",
    "DocumentRef-d:LicenseRef-y and GPL-2.0 or later": "unresolved",
    "Apache-2.0 WITH LLVM-exception and GPL-3.0": "expression",
    "GPL-2.0 or later and MIT": "unresolved",
    'GPL-2.0 or later and "BSD-3-Clause"': "unresolved",
    '"BSD-3-Clause" and StandardML-NJ': "expression",
    "Foo and isc": "unresolved",
    'Foo and "BSD-3-Clause"': "unresolved",
    "GPL-2.0-only+ and LicenseRef-x": "malformed",
    "MIT? and Apache2": "expression",
    "MIT? and Foo": "unresolved",
    "(MIT OR isc) AND Apache2": "expression",
    "(isc OR Apache2) AND GPL-2.0+": "expression",
    "(Apache2 OR GPL-2.0+) AND GPL-3.0": "expression",
    "(GPL-2.0+ OR GPL-3.0) AND StandardML-NJ": "expression",
    "(GPL-3.0 OR StandardML-NJ) AND LicenseRef-x": "expression",
    "(StandardML-NJ OR LicenseRef-x) AND DocumentRef-d:LicenseRef-y": "expression",
    (
        "(LicenseRef-x OR DocumentRef-d:LicenseRef-y)"
        " AND Apache-2.0 WITH LLVM-exception"
    ): "expression",
    (
        "(DocumentRef-d:LicenseRef-y"
        " OR Apache-2.0 WITH LLVM-exception) AND GPL-2.0 or later"
    ): "unresolved",
    (
        '(Apache-2.0 WITH LLVM-exception OR GPL-2.0 or later) AND "BSD-3-Clause"'
    ): "unresolved",
    '(GPL-2.0 or later OR "BSD-3-Clause") AND MIT': "unresolved",
    '("BSD-3-Clause" OR MIT) AND isc': "expression",
    "MIT AND (isc OR Apache2)": "expression",
    "isc AND (Apache2 OR GPL-2.0+)": "expression",
    "Apache2 AND (GPL-2.0+ OR GPL-3.0)": "expression",
    "GPL-2.0+ AND (GPL-3.0 OR StandardML-NJ)": "expression",
    "GPL-3.0 AND (StandardML-NJ OR LicenseRef-x)": "expression",
    "StandardML-NJ AND (LicenseRef-x OR DocumentRef-d:LicenseRef-y)": "expression",
    (
        "LicenseRef-x AND (DocumentRef-d:LicenseRef-y"
        " OR Apache-2.0 WITH LLVM-exception)"
    ): "expression",
    (
        "DocumentRef-d:LicenseRef-y"
        " AND (Apache-2.0 WITH LLVM-exception OR GPL-2.0 or later)"
    ): "unresolved",
    (
        'Apache-2.0 WITH LLVM-exception AND (GPL-2.0 or later OR "BSD-3-Clause")'
    ): "unresolved",
    'GPL-2.0 or later AND ("BSD-3-Clause" OR MIT)': "unresolved",
    '"BSD-3-Clause" AND (MIT OR isc)': "expression",
    "[MIT OR isc]": "unresolved",
    '[MIT OR "BSD-3-Clause"]': "unresolved",
    "[isc OR LicenseRef-x]": "unresolved",
    "[Apache2 OR isc]": "unresolved",
    "[Apache2 OR Foo]": "unresolved",
    "[GPL-2.0+ OR DocumentRef-d:LicenseRef-y]": "unresolved",
    "[GPL-3.0 OR Apache2]": "unresolved",
    "[GPL-3.0 OR GPL-2.0-only+]": "unresolved",
    "[StandardML-NJ OR Apache-2.0 WITH LLVM-exception]": "unresolved",
    "[LicenseRef-x OR GPL-2.0+]": "unresolved",
    "[LicenseRef-x OR MIT?]": "unresolved",
    "[DocumentRef-d:LicenseRef-y OR GPL-2.0 or later]": "unresolved",
    "[Apache-2.0 WITH LLVM-exception OR GPL-3.0]": "unresolved",
    "[GPL-2.0 or later OR MIT]": "unresolved",
    '[GPL-2.0 or later OR "BSD-3-Clause"]': "unresolved",
    '["BSD-3-Clause" OR StandardML-NJ]': "unresolved",
    "[Foo OR isc]": "unresolved",
    '[Foo OR "BSD-3-Clause"]': "unresolved",
    "[GPL-2.0-only+ OR LicenseRef-x]": "unresolved",
    "[MIT? OR Apache2]": "unresolved",
    "[MIT? OR Foo]": "unresolved",
    "MIT OR isc OR MIT": "expression",
    'MIT OR "BSD-3-Clause" OR MIT': "expression",
    "isc OR LicenseRef-x OR isc": "expression",
    "Apache2 OR isc OR Apache2": "expression",
    "Apache2 OR Foo OR Apache2": "unresolved",
    "GPL-2.0+ OR DocumentRef-d:LicenseRef-y OR GPL-2.0+": "expression",
    "GPL-3.0 OR Apache2 OR GPL-3.0": "expression",
    "GPL-3.0 OR GPL-2.0-only+ OR GPL-3.0": "malformed",
    "StandardML-NJ OR Apache-2.0 WITH LLVM-exception OR StandardML-NJ": "expression",
    "LicenseRef-x OR GPL-2.0+ OR LicenseRef-x": "expression",
    "LicenseRef-x OR MIT? OR LicenseRef-x": "expression",
    (
        "DocumentRef-d:LicenseRef-y OR GPL-2.0 or later OR DocumentRef-d:LicenseRef-y"
    ): "unresolved",
    (
        "Apache-2.0 WITH LLVM-exception OR GPL-3.0 OR Apache-2.0 WITH LLVM-exception"
    ): "expression",
    "GPL-2.0 or later OR MIT OR GPL-2.0 or later": "unresolved",
    'GPL-2.0 or later OR "BSD-3-Clause" OR GPL-2.0 or later': "unresolved",
    '"BSD-3-Clause" OR StandardML-NJ OR "BSD-3-Clause"': "expression",
    "Foo OR isc OR Foo": "unresolved",
    'Foo OR "BSD-3-Clause" OR Foo': "unresolved",
    "GPL-2.0-only+ OR LicenseRef-x OR GPL-2.0-only+": "malformed",
    "MIT? OR Apache2 OR MIT?": "expression",
    "MIT? OR Foo OR MIT?": "unresolved",
}


def test_the_pins_cover_the_generated_list() -> None:
    """One pin per generated value, in the generated order."""
    assert list(PINNED) == generated_compounds()


@pytest.mark.parametrize("value", list(PINNED), ids=lambda v: v[:40])
def test_a_generated_compound_keeps_its_answer(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """No expression and no reason; the category as pinned."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["reason"]) == (
        None,
        PINNED[value],
        None,
    )


_WITH = "GPL-2.0-only WITH Classpath-exception-2.0"

#: Shapes task T7 decides (review decisions Q14 to Q21), with the answer:
#: ``(expression, category, step kinds)``. A comment names what it was before.
SHAPES: list[tuple[str, tuple[str | None, str, list[str]]]] = [
    # Q17: the case and spacing of a single WITH are steps (were none, exact)
    (
        "GPL-2.0-only with Classpath-exception-2.0",
        (_WITH, "lexical", ["operator_case"]),
    ),
    ("GPL-2.0-only  WITH Classpath-exception-2.0", (_WITH, "lexical", ["whitespace"])),
    ("GPL-2.0-only\tWITH\tClasspath-exception-2.0", (_WITH, "lexical", ["whitespace"])),
    # Q14: a grant on an ID with no -or-later form is not read
    ("Apache 2.0 or later", (None, "unresolved", [])),
    ("MIT or later", (None, "unresolved", [])),
    # Q14: the hyphenated grant is read by the version key, as a separator
    ("GPL-2.0 or-later", ("GPL-2.0-or-later", "separator", ["separator"])),
    ("GPL-2.0-only or-later", (None, "unresolved", [])),
    # the grant after a WITH is not read
    ("GPL-2.0 WITH Classpath-exception-2.0 or later", (None, "unresolved", [])),
    # Q20: an AdditionRef names itself, as a LicenseRef does (was unresolved)
    ("MIT WITH AdditionRef-x", ("MIT WITH AdditionRef-x", "exact", [])),
    # Q16: a LicenseRef is exempt from the key cap (was unresolved)
    ("LicenseRef-" + "a" * 120, ("LicenseRef-" + "a" * 120, "exact", [])),
    # Q21: square and curly brackets are no brackets
    ("[MIT]", (None, "unresolved", [])),
    ("{MIT OR ISC}", (None, "unresolved", [])),
    ("MIT)", (None, "unresolved", [])),
    # Q14: a grant inside a compound is not read
    ("MIT OR GPL-2.0 or later", (None, "unresolved", [])),
    ("GPL-2.0 or later AND MIT", (None, "unresolved", [])),
    # a repeat, operator case, prose with "or", a slash
    ("MIT OR MIT", (None, "expression", [])),
    ("MIT or Apache-2.0", (None, "expression", [])),
    ("Proprietary or custom", (None, "unresolved", [])),
    ("MIT/Apache-2.0", (None, "unresolved", [])),
    ("MIT OR GPL-2.0-only+", (None, "malformed", [])),
]


@pytest.mark.parametrize(("value", "expected"), SHAPES, ids=[v[:40] for v, _ in SHAPES])
def test_a_shape_t7_decides_keeps_its_answer(
    corpus_db: LicenseDatabase, value: str, expected: tuple[object, ...]
) -> None:
    """The expression, the category and the step kinds as pinned."""
    got = resolve(value, corpus_db)
    kinds = [s["kind"] for s in got["steps"]]
    assert (got["expression"], got["category"], kinds) == expected
    assert got["reason"] is None
