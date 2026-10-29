# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Adversarial compounds for ``resolve()`` (task T7): operator case and
spacing, unbalanced and mixed brackets, grants and quotes per operand,
references, duplicates, controls, and the limits that keep deep nesting and
long chains away from the parser, each timed with distinct payloads.
"""
# pylint: disable=missing-function-docstring

import time

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from resolver_corpus import LICENSE_LIST, list_rows

from licenseid import LicenseDatabase, resolve
from licenseid.identifiers import MAX_PARSE_DEPTH, MAX_PARSE_OPERATORS

#: ``(value, (expression, category, reason))``
ANSWERS: list[tuple[str, tuple[str | None, str, str | None]]] = [
    # operator case and spacing
    ("MIT Or ISC", ("ISC OR MIT", "lexical", None)),
    ("MIT  OR   ISC", ("ISC OR MIT", "lexical", None)),
    ("MIT\tAND\nISC", ("ISC AND MIT", "lexical", None)),
    ("(MIT)OR(ISC)", ("ISC OR MIT", "lexical", None)),
    ('MIT"OR"ISC', (None, "unresolved", None)),  # no operator in a word
    # the grammar refused
    ("MIT OR OR ISC", (None, "malformed", "parse failed: Unexpected 'OR'")),
    ("OR MIT", (None, "malformed", "parse failed: Unexpected 'OR'")),
    ("(MIT OR ISC))", (None, "malformed", "parse failed: Missing matching '('")),
    ("((MIT OR ISC)", (None, "malformed", "parse failed: Unexpected '('")),
    ("[MIT OR (ISC]", (None, "malformed", "parse failed: Unexpected 'OR'")),
    ("{MIT OR ISC)", (None, "malformed", "mismatched brackets")),
    ("()", (None, "unresolved", None)),
    ("(Foo OR Bar", (None, "unresolved", "parse failed: Unexpected '('")),  # no licence
    # mixed brackets, properly nested
    ("[MIT OR (ISC AND {0BSD})]", ("MIT OR 0BSD AND ISC", "lexical", None)),
    # WITH
    (
        "MIT WITH LLVM-exception OR ISC WITH LLVM-exception",
        ("ISC WITH LLVM-exception OR MIT WITH LLVM-exception", "lexical", None),
    ),
    ("MIT WITH LLVM-exception WITH LLVM-exception", (None, "unresolved", None)),
    # grants and "+" per operand, at every position
    ("GPL-2.0 or later OR MIT", ("GPL-2.0-or-later OR MIT", "stated_qualifier", None)),
    ("MIT OR GPL-2.0 or later", ("GPL-2.0-or-later OR MIT", "stated_qualifier", None)),
    (
        "MIT AND GPL-2.0 or later AND Apache-2.0",
        ("Apache-2.0 AND GPL-2.0-or-later AND MIT", "stated_qualifier", None),
    ),
    (
        "GPL-2.0 (or later) OR MIT",
        ("GPL-2.0-or-later OR MIT", "stated_qualifier", None),
    ),
    ("GPL-2.0 + OR MIT", ("GPL-2.0-or-later OR MIT", "plus_to_or_later", None)),
    ("GPL-2.0 or later OR GPL-2.0+", ("GPL-2.0-or-later", "stated_qualifier", None)),
    (
        "GPL-2.0-or-later or later OR MIT",
        (None, "malformed", "operand not resolved: GPL-2.0-or-later or later"),
    ),
    (
        "MIT OR LicenseRef-x+",
        (None, "malformed", "operand not resolved: LicenseRef-x+"),
    ),
    ("MIT OR +", (None, "unresolved", "operand not resolved: +")),
    ("(or later) OR MIT", (None, "unresolved", None)),
    # P35 (decided by the maintainer): an ID with no -or-later form takes "+"
    ("GPL-2.0 or MIT or later", ("GPL-2.0 OR MIT+", "assumed_only", None)),
    ("MIT OR later OR ISC", ("ISC OR MIT+", "stated_qualifier", None)),
    ("Apache-2.0 OR later OR ISC", ("Apache-2.0+ OR ISC", "stated_qualifier", None)),
    # a mark after a grant stays in its leaf, judged as alone
    ("GPL-2.0 or later, OR MIT", ("GPL-2.0-or-later OR MIT", "stated_qualifier", None)),
    ("GPL-2.0 or later-ish OR MIT", (None, "unresolved", None)),  # no grant
    ("GPL-2.0 or later- OR MIT", (None, "unresolved", None)),  # "-" ends no grant
    ("GPL-2.0 or later/ OR MIT", (None, "unresolved", "character dropped: U+002F")),
    # prose: a part of several words, and no operator or none between two
    ("MIT License (MIT) OR ISC", (None, "unresolved", None)),
    ("(Apache License 2.0", (None, "unresolved", None)),
    # quotes per operand
    ("MIT OR 'ISC'", ("ISC OR MIT", "lexical", None)),
    ('"MIT" AND "ISC', (None, "unresolved", "character dropped: U+0022")),
    # references
    ("LicenseRef-a OR LicenseRef-a", ("LicenseRef-a", "lexical", None)),
    ("LicenseRef-a OR licenseref-a", ("LicenseRef-a OR licenseref-a", "exact", None)),
    (
        "LicenseRef-a OR DocumentRef-x:LicenseRef-a",
        ("DocumentRef-x:LicenseRef-a OR LicenseRef-a", "lexical", None),
    ),
    (
        "MIT WITH DocumentRef-d:AdditionRef-y OR MIT WITH AdditionRef-x",
        (
            "MIT WITH AdditionRef-x OR MIT WITH DocumentRef-d:AdditionRef-y",
            "lexical",
            None,
        ),
    ),
    # duplicates
    ("MIT OR MIT AND MIT", ("MIT", "lexical", None)),
    ("mit OR MIT", ("MIT", "lexical", None)),
    ("(MIT AND ISC) OR (ISC AND MIT)", ("ISC AND MIT", "lexical", None)),
    # controls and surrogates in an operand refuse the whole
    ("MIT OR ISC\u200b", (None, "unresolved", "control or format character: U+200B")),
    ("MIT OR \udcff", (None, "unresolved", "lone surrogate")),
    ("MIT OR\x00ISC", (None, "unresolved", "control or format character: U+0000")),
]


@pytest.mark.parametrize(("value", "expected"), ANSWERS, ids=[v for v, _ in ANSWERS])
def test_an_adversarial_compound_gets_its_answer(
    corpus_db: LicenseDatabase,
    value: str,
    expected: tuple[str | None, str, str | None],
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["reason"]) == expected


def _short_ids(count: int) -> list[str]:
    """*count* distinct listed IDs, the shortest first: a chain of distinct
    operands that stays under the input cap of 2,000 characters."""
    ids = sorted((str(row[0]) for row in list_rows(LICENSE_LIST, "licenses")), key=len)
    return ids[:count]


def _chain(count: int, operator: str = "OR") -> str:
    return f" {operator} ".join(_short_ids(count))


@pytest.mark.parametrize(
    ("operators", "read"),
    [(MAX_PARSE_OPERATORS, True), (MAX_PARSE_OPERATORS + 1, False)],
    ids=["at-cap", "over-cap"],
)
def test_a_chain_is_read_up_to_the_operator_cap(
    corpus_db: LicenseDatabase, operators: int, read: bool
) -> None:
    value = _chain(operators + 1)
    assert len(value) <= 2000
    got = resolve(value, corpus_db)
    if read:
        assert got["expression"] is not None
        assert len(got["operands"]) == operators + 1
    else:
        assert (got["category"], got["reason"]) == ("unresolved", "too many operators")


@pytest.mark.parametrize(
    ("operator", "reason"),
    [("and", None), ("AND", "operand not resolved: foo bar")],
)
def test_prose_over_the_operator_cap_is_still_prose(
    corpus_db: LicenseDatabase, operator: str, reason: str | None
) -> None:
    """The shape is judged before the cap: 160 phrases of two words are no
    compound, as 10 are, not ``too many operators``."""
    for count in (10, 160):
        got = resolve(f" {operator} ".join(["foo bar"] * count), corpus_db)
        assert (got["category"], got["reason"]) == ("unresolved", reason)


@pytest.mark.parametrize(
    ("depth", "reason"),
    [(MAX_PARSE_DEPTH, None), (MAX_PARSE_DEPTH + 1, "too deeply nested")],
    ids=["at-cap", "over-cap"],
)
def test_nesting_is_read_up_to_the_depth_cap(
    corpus_db: LicenseDatabase, depth: int, reason: str | None
) -> None:
    """Brackets around one operand of two, so that the whole is no pair."""
    value = "MIT OR " + "(" * depth + "ISC" + ")" * depth
    got = resolve(value, corpus_db)
    assert got["reason"] == reason
    assert (got["expression"] is None) == (reason is not None)


#: Distinct, balanced payloads, each under the input cap, and the slowest of
#: them measured at about 40 ms on Python 3.10 (0.6.0: about the same).
PAYLOADS = {
    "chain": _chain(150),
    "chain-lower": " or ".join(_short_ids(150)).lower(),
    "and-of-ors": " AND ".join(
        f"({a} OR {b})" for a, b in zip(*[iter(_short_ids(120))] * 2)
    ),
    "with": " OR ".join(f"{i} WITH LLVM-exception" for i in _short_ids(60)),
    "grants": " OR ".join(f"GPL-{i}.0 or later" for i in range(1, 80)),
    "quotes": " OR ".join(f'"{i}"' for i in _short_ids(120)),
    "nested": "MIT OR " + "([{" * 50 + "ISC" + "}])" * 50,
    "spaced-nesting": "( " * 300 + "MIT" + " )" * 300,
    "spaces": "x" + " " * 1990,
    "or-run": "OR " * 600,
    "or-words": "MIT" + " OR" * 600,
    "openers": "(" * 1000 + "MIT",
    "closers": "MIT" + ")" * 1000,
}


@pytest.mark.parametrize("name", list(PAYLOADS))
def test_a_long_or_deep_compound_is_fast(corpus_db: LicenseDatabase, name: str) -> None:
    """Under 2 s each: 10x headroom and more for CI's Python 3.10."""
    value = PAYLOADS[name]
    assert len(value) <= 2000
    start = time.monotonic()
    resolve(value, corpus_db)
    assert time.monotonic() - start < 2.0
