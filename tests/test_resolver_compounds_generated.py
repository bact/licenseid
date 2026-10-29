# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Generated compounds (``compound_cases``), each with the answer
``resolve()`` gives, and the shapes task T7 decided (review decisions Q14 to
Q21).

Before T7 a compound was only labelled ``expression``, with no expression;
the pins of ``fixtures/resolver_compounds_generated.tsv`` are what T7 reads.
"""

from pathlib import Path

import pytest
from compound_cases import generated_compounds
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from tools.pypi_licence_sample.answer import NONE_FIELD, load_list, unescape_field

PINS_FILE = Path(__file__).parent / "fixtures" / "resolver_compounds_generated.tsv"

#: ``(expression, category, step kinds, reason)``
Pin = tuple[str | None, str, tuple[str, ...], str | None]


def _optional(field: str) -> str | None:
    return None if field == NONE_FIELD else unescape_field(field)


def _pins() -> dict[str, Pin]:
    lines = PINS_FILE.read_text(encoding="utf-8").splitlines()
    rows = [line.split("\t") for line in lines if not line.startswith("#")]
    return {
        unescape_field(value): (
            _optional(expr),
            category,
            load_list(steps),
            _optional(why),
        )
        for value, expr, category, steps, why in rows[1:]
    }


#: The answer to each generated compound.
PINNED: dict[str, Pin] = _pins()


def test_the_pins_cover_the_generated_list() -> None:
    """One pin per generated value, in the generated order."""
    assert list(PINNED) == generated_compounds()


@pytest.mark.parametrize("value", list(PINNED), ids=lambda v: v[:40])
def test_a_generated_compound_keeps_its_answer(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """The expression, the category, the step kinds and the reason."""
    got = resolve(value, corpus_db)
    kinds = tuple(s["kind"] for s in got["steps"])
    assert (got["expression"], got["category"], kinds, got["reason"]) == PINNED[value]


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
    # Q14, P35: a grant on an ID with no -or-later form is "+"
    ("Apache 2.0 or later", ("Apache-2.0+", "separator", ["separator"])),
    ("MIT or later", ("MIT+", "stated_qualifier", [])),  # P35
    # Q14: the hyphenated grant is a grant (was separator, by the version
    # key) and a qualifier stated twice is malformed (was unresolved)
    ("GPL-2.0 or-later", ("GPL-2.0-or-later", "stated_qualifier", [])),
    ("GPL-2.0-only or-later", (None, "malformed", [])),
    # the grant after a WITH is the licence's (was unresolved)
    (
        "GPL-2.0 WITH Classpath-exception-2.0 or later",
        ("GPL-2.0-or-later WITH Classpath-exception-2.0", "stated_qualifier", []),
    ),
    # Q20: an AdditionRef names itself, as a LicenseRef does (was unresolved)
    ("MIT WITH AdditionRef-x", ("MIT WITH AdditionRef-x", "exact", [])),
    # Q16: a LicenseRef is exempt from the key cap (was unresolved)
    ("LicenseRef-" + "a" * 120, ("LicenseRef-" + "a" * 120, "exact", [])),
    # Q21: square and curly brackets are brackets (were unresolved)
    ("[MIT]", ("MIT", "lexical", ["brackets"])),
    ("{MIT OR ISC}", ("ISC OR MIT", "lexical", ["brackets", "reorder"])),
    # Q14: a grant inside a compound is read (was unresolved)
    (
        "MIT OR GPL-2.0 or later",
        ("GPL-2.0-or-later OR MIT", "stated_qualifier", ["reorder"]),
    ),
    ("GPL-2.0 or later AND MIT", ("GPL-2.0-or-later AND MIT", "stated_qualifier", [])),
    # a repeat and the operator case are steps (were `expression`)
    ("MIT OR MIT", ("MIT", "lexical", ["dedupe"])),
    (
        "MIT or Apache-2.0",
        ("Apache-2.0 OR MIT", "lexical", ["operator_case", "reorder"]),
    ),
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


#: Shapes task T7 refuses, with the answer: ``(category, reason)``. Before
#: T7 each had no reason; ``MIT)`` was unresolved.
REFUSED: list[tuple[str, tuple[str, str]]] = [
    ("MIT)", ("malformed", "parse failed: Missing matching '('")),
    ("(MIT", ("malformed", "parse failed: Unexpected '('")),
    ("MIT AND", ("malformed", "parse failed: Unexpected 'AND'")),
    ("MIT OR GPL-2.0-only+", ("malformed", "operand not resolved: GPL-2.0-only+")),
    ("MIT/Apache-2.0", ("unresolved", "not an SPDX operator: /")),
    ("MIT | ISC", ("unresolved", "not an SPDX operator: |")),
    ("MIT & ISC", ("unresolved", "not an SPDX operator: &")),
    ("MIT; ISC", ("unresolved", "operator not stated: ;")),  # T8b: listed
    ("MIT, ISC", ("unresolved", "not an SPDX operator: ,")),
    ("MIT OR ISC]", ("malformed", "parse failed: Missing matching '('")),
    ("(MIT OR ISC]", ("malformed", "mismatched brackets")),
    ("LicenseRef-x OR MIT?", ("unresolved", "character dropped: U+003F")),
]


@pytest.mark.parametrize(("value", "expected"), REFUSED, ids=[v for v, _ in REFUSED])
def test_a_shape_t7_refuses_says_why(
    corpus_db: LicenseDatabase, value: str, expected: tuple[str, str]
) -> None:
    """No expression and no operand taken; the category and the reason."""
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert (got["category"], got["reason"]) == expected


#: Values with an operator word that T7 does not read as a compound: a leaf
#: of several words with a lower-case operator, or a lower-case operator and
#: an operand that names nothing. Before T7 they were unresolved, with no
#: reason, as now.
PROSE = [
    "Proprietary or custom",
    "proprietary and confidential",
    "GPL-3.0 or higher",
    "GPL-2.0 and later",
    "MIT or Foo",
    "MIT and",
    "(MIT or",
    "DataRobot Tool and Utility Agreement",
    'BSD 3-clause "New" or "Revised License"',
]


@pytest.mark.parametrize("value", PROSE)
def test_prose_with_an_operator_word_is_no_compound(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """Unresolved, no reason that splits it, one operand: the whole value."""
    got = resolve(value, corpus_db)
    texts = [o["text"] for o in got["operands"]]
    assert (got["category"], got["reason"], texts) == ("unresolved", None, [value])
    assert got["expression"] is None
    assert not got["components"]


#: Values in compound form with a leaf of several words: no compound (Q18),
#: but with the operators in upper case the reason is the first refused
#: operand's (Q15, P43 amended after review); a dropped mark in any case.
FALLBACK = [
    ("Apache License 2.0 OR MIT", "operand of several words: Apache License 2.0", []),
    ("BSD 3-Clause OR Apache-2.0", "operand of several words: BSD 3-Clause", []),
    ("Foo OR Apache License 2.0", "operand not resolved: Foo", []),
    ("MIT OR GPLv2 or later!", "character dropped: U+0021", ["drop"]),
    ("Apache 2.0? OR MIT", "character dropped: U+003F", ["drop"]),
    ("Apache 2.0? or MIT", "character dropped: U+003F", ["drop"]),
    ("Foo or MIT?", "character dropped: U+003F", ["drop"]),
]


@pytest.mark.parametrize(
    ("value", "reason", "kinds"), FALLBACK, ids=[v for v, _, _ in FALLBACK]
)
def test_prose_in_compound_form_says_which_operand_was_refused(
    corpus_db: LicenseDatabase, value: str, reason: str, kinds: list[str]
) -> None:
    """Unresolved, the reason of its first refused operand, its drop step."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["reason"]) == (
        None,
        "unresolved",
        reason,
    )
    assert [s["kind"] for s in got["steps"]] == kinds
