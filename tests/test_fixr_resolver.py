# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Task ``fixr`` of the 0.7.0 review: the ``lists`` of a refused list of
licences, the reason of a refused WITH, of a misplaced "+" in a compound and
of a qualifier on a reference, and one reading of "or later", on the whole
3.29.0 List.

Each test was first a pin of what the branch did (``# BUG:``); it now holds
the new answer.
"""
# pylint: disable=missing-function-docstring

import pytest
from resolver_corpus import corpus_rows

from licenseid import LicenseDatabase, match
from licenseid.resolveleaf import _grant_head
from licenseid.resolvertypes import TROVE_LIST
from tools.pypi_licence_sample.answer import unescape_field


def _answer(db: LicenseDatabase, value: str) -> tuple[str | None, str, str | None]:
    got = match(value, db)
    return got["expression"], got["category"], got["reason"]


# --- item 1: a list an operand's step cites is in ``lists`` -------------------


@pytest.mark.parametrize(
    "value",
    [
        "MIT; ISC License (ISCL)",
        (
            "License :: OSI Approved :: MIT License;"
            " License :: OSI Approved :: ISC License (ISCL)"
        ),
    ],
)
def test_lists_names_the_list_an_operand_cites(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = match(value, corpus_db)
    cited = {s["list"] for o in got["operands"] for s in o["steps"]}
    assert TROVE_LIST in cited
    assert got["steps"] == []  # only an operand cites it
    assert [entry["id"] for entry in got["lists"]] == ["spdx-license-list", TROVE_LIST]


@pytest.mark.parametrize(
    ("value", "trove"),
    [
        ("MIT; ISC", False),
        ("MIT", False),
        ("ISC License (ISCL)", True),
        ("ISC License (ISCL); ISC License (ISCL)", True),  # named once
    ],
)
def test_lists_names_the_trove_list_once_or_not_at_all(
    corpus_db: LicenseDatabase, value: str, trove: bool
) -> None:
    ids = [entry["id"] for entry in match(value, corpus_db)["lists"]]
    assert ids == ["spdx-license-list", *([TROVE_LIST] if trove else [])]


def test_every_list_a_step_cites_is_in_lists(corpus_db: LicenseDatabase) -> None:
    """Over the parity corpus and the PyPI sample: every ``list`` a step or
    an expansion cites, of the value or of an operand, is in ``lists``."""
    missing = {}
    for row in corpus_rows():
        value = unescape_field(row["value"])
        got = match(value, corpus_db)
        steps = [*got["steps"], *got["expansions"]]
        for operand in got["operands"]:
            steps += [*operand["steps"], *operand["expansions"]]
        cited = {s["list"] for s in steps} - {None}
        listed = {entry["id"] for entry in got["lists"]}
        if not cited <= listed:
            missing[value] = cited - listed
    assert not missing


# --- item 2: the reason of a refused WITH -------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # words after the exception: no exception ID, the general reason
        (
            "MIT WITH Classpath-exception-2.0 or something",
            "not found: MIT WITH Classpath-exception-2.0 or something",
        ),
        (
            "Artistic License 1.0 (dist) WITH Autoconf-exception-macro OR Zlib",
            (
                "not found: Artistic License 1.0 (dist) WITH"
                " Autoconf-exception-macro OR..."
            ),
        ),
        ("Apache-2.0 with LLVM exception", "not found: Apache-2.0 with LLVM exception"),
        # one word that is no listed exception
        ("MIT WITH Foo-exception", "exception not found: Foo-exception"),
        ("MIT WITH  Foo-exception\t", "exception not found: Foo-exception"),
        ("Foo WITH Foo-exception", "not found: Foo WITH Foo-exception"),
        ("MIT WITH Foo-exception+", "exception not found: Foo-exception+"),
        # a listed exception and a mark that is no "+"
        (
            "MIT WITH Classpath-exception-2.0x",
            "exception not found: Classpath-exception-2.0x",
        ),
        ("MIT WITH", "not found: MIT WITH"),  # nothing after WITH
        ("MIT WITH ", "not found: MIT WITH"),
    ],
)
def test_an_exception_not_found_is_one_word(
    corpus_db: LicenseDatabase, value: str, expected: str
) -> None:
    assert _answer(corpus_db, value) == (None, "unresolved", expected)


@pytest.mark.parametrize(
    "value",
    [
        "MIT WITH Classpath-exception-2.0+",
        "MIT WITH Classpath-exception-2.0 +",
        "mit with classpath-exception-2.0+",
        "GPL-2.0+ WITH Classpath-exception-2.0+",
        "MIT WITH AdditionRef-x+",
        "MIT WITH AdditionRef-x +",
    ],
)
def test_a_plus_after_an_exception_is_malformed(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert _answer(corpus_db, value) == (
        None,
        "malformed",
        f"plus after an exception: {value}",
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # the licence's own refusal comes first
        (
            "GPL-2.0-only+ WITH Classpath-exception-2.0+",
            (None, "malformed", "qualifier stated twice: GPL-2.0-only+"),
        ),
        (
            "Foo WITH Classpath-exception-2.0+",
            (None, "unresolved", "not found: Foo WITH Classpath-exception-2.0+"),
        ),
        # an operand: its reason is the compound's
        (
            "MIT WITH Classpath-exception-2.0+ OR ISC",
            (
                None,
                "malformed",
                "plus after an exception: MIT WITH Classpath-exception-2.0+",
            ),
        ),
        # two "+": no listed exception and one "+"
        (
            "MIT WITH Classpath-exception-2.0++",
            (None, "unresolved", "exception not found: Classpath-exception-2.0++"),
        ),
        # still read
        (
            "GPL-2.0 WITH Classpath-exception-2.0 or later",
            ("GPL-2.0-or-later WITH Classpath-exception-2.0", "stated_qualifier", None),
        ),
        (
            "GPL-2.0+ WITH Classpath-exception-2.0",
            ("GPL-2.0-or-later WITH Classpath-exception-2.0", "plus_to_or_later", None),
        ),
    ],
)
def test_a_with_around_the_plus(
    corpus_db: LicenseDatabase, value: str, expected: tuple[object, ...]
) -> None:
    assert _answer(corpus_db, value) == expected


# --- item 3: a compound with a misplaced "+" or quoted brackets ---------------


@pytest.mark.parametrize(
    ("value", "group"),
    [
        ("(MIT)+ OR ISC", "(MIT)+"),
        ("MIT OR (ISC)+", "(ISC)+"),
        ("(MIT OR ISC)+", "(MIT OR ISC)+"),
        ("((MIT))+ AND ISC", "((MIT))+"),
        ("[MIT]+ OR ISC", "[MIT]+"),
        ("(Foo OR MIT)+", "(Foo OR MIT)+"),  # one licence named is enough
        ("(MIT)+", "(MIT)+"),  # alone, as before
    ],
)
def test_a_plus_after_a_bracket_in_a_compound(
    corpus_db: LicenseDatabase, value: str, group: str
) -> None:
    assert _answer(corpus_db, value) == (
        None,
        "malformed",
        f"plus after a bracket: {group}",
    )


@pytest.mark.parametrize(
    ("value", "marks"),
    [
        ('"(MIT)" OR Zlib', "U+0022"),
        ('"(MIT OR ISC)" OR Zlib', "U+0022"),
        ("'(MIT)' OR Zlib", "U+0027"),
        ("“(MIT)” OR Zlib", "U+201C U+201D"),
        ('Zlib AND "[MIT]"', "U+0022"),
    ],
)
def test_quotes_around_a_bracket_in_a_compound(
    corpus_db: LicenseDatabase, value: str, marks: str
) -> None:
    """Quote marks come off an operand, not a bracketed group: refused as a
    quote mark in an operand is (``"MIT OR ISC" OR Zlib``), not read."""
    got = match(value, corpus_db)
    assert (got["expression"], got["category"], got["reason"]) == (
        None,
        "unresolved",
        f"character dropped: {marks}",
    )
    assert [(s["kind"], s["applied"]) for s in got["steps"]] == [("drop", False)]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # nothing named in the group, a lower-case operator, a space, a
        # mark after the quote: as before
        ("(Foo)+ OR ISC", (None, "unresolved", "not found: (Foo)+ OR ISC")),
        ('"(Foo)" OR Zlib', (None, "unresolved", 'not found: "(Foo)" OR Zlib')),
        ("(MIT)+ or ISC", (None, "unresolved", "not found: (MIT)+ or ISC")),
        ("(MIT) + OR ISC", (None, "unresolved", "not found: (MIT) + OR ISC")),
        ('"(MIT)"x OR Zlib', (None, "unresolved", 'not found: "(MIT)"x OR Zlib')),
        ('"(MIT) " OR Zlib', (None, "unresolved", 'not found: "(MIT) " OR Zlib')),
        ("x(MIT)x OR Zlib", (None, "unresolved", "not found: x(MIT)x OR Zlib")),
        # not every licence in the quoted group named, or none in it
        (
            '"(MIT OR Foo)" OR Zlib',
            (None, "unresolved", 'not found: "(MIT OR Foo)" OR Zlib'),
        ),
        ('"()" OR MIT', (None, "unresolved", 'not found: "()" OR MIT')),
        # no AND or OR: two operands side by side, as before
        ("(MIT)+ ISC", (None, "unresolved", "not found: (MIT)+ ISC")),
        ('"(MIT)" Zlib', (None, "unresolved", 'not found: "(MIT)" Zlib')),
        # a "+" after an opening bracket
        (
            "(MIT)(+ ISC) OR Zlib",
            (None, "unresolved", "not found: (MIT)(+ ISC) OR Zlib"),
        ),
        ("MIT OR (+ ISC)", (None, "unresolved", "operand not resolved: + ISC")),
        # still read
        ('("MIT") OR Zlib', ("MIT OR Zlib", "lexical", None)),
        ('"(MIT)"', ("MIT", "lexical", None)),
        ("(MIT) OR ISC+", ("ISC+ OR MIT", "lexical", None)),
    ],
)
def test_a_compound_beside_the_misplaced_marks(
    corpus_db: LicenseDatabase, value: str, expected: tuple[object, ...]
) -> None:
    assert _answer(corpus_db, value) == expected


# --- item 4: one reader of "or later" -----------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "GPL-2.0 or later",
        "GPL-2.0 or-later",
        "GPL-2.0 or any later version",
        "GPL-2.0 or_later",
        "GPL-2.0 or.later",
        "GPL-2.0 or _later",
        "GPL-2.0 or later-",
        "GPL-2.0 or later_",
    ],
)
def test_a_spaced_or_later_is_a_stated_qualifier(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["category"]) == (
        "GPL-2.0-or-later",
        "stated_qualifier",
    )
    assert [s["kind"] for s in got["steps"]] == []
    assert [s["kind"] for s in got["expansions"]] == ["stated_qualifier"]


@pytest.mark.parametrize(
    "value",
    [
        "GFDL-1.3-invariants or later",
        "GFDL-1.3-invariants or-later",
        "GFDL-1.3-invariants or_later",
        "GFDL-1.3-invariants or any later version",
        "GFDL-1.3-invariants+",
    ],
)
def test_an_or_later_on_no_licence_is_refused(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """``GFDL-1.3-invariants`` is no licence of the List (only its
    ``-only`` and ``-or-later`` are): every spelling of a grant on it is
    refused alike."""
    assert _answer(corpus_db, value) == (None, "unresolved", f"not found: {value}")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # the suffix joined to the ID: a spelling of the ID
        ("GPL-2.0_or_later", ("GPL-2.0-or-later", "separator", None)),
        ("GPL 2.0-or-later", ("GPL-2.0-or-later", "separator", None)),
        (
            "GFDL-1.3-invariants_or_later",
            ("GFDL-1.3-invariants-or-later", "separator", None),
        ),
        (
            "GFDL-1.3-invariants-or-later",
            ("GFDL-1.3-invariants-or-later", "exact", None),
        ),
        # a listed name keeps its reading
        (
            "GNU General Public License v2.0 or later",
            ("GPL-2.0-or-later", "listed_name", None),
        ),
        # a mark that says something is still refused
        ("GPL-2.0 or later/", (None, "unresolved", "character dropped: U+002F")),
        # a qualifier stated twice, or a word that is no "or later"
        (
            "GPL-2.0-only or later",
            (None, "malformed", "qualifier stated twice: GPL-2.0-only or later"),
        ),
        ("GPL-2.0 orlater", (None, "unresolved", "not found: GPL-2.0 orlater")),
        ("GPL-2.0 or sooner", (None, "unresolved", "not found: GPL-2.0 or sooner")),
    ],
)
def test_beside_a_spaced_or_later(
    corpus_db: LicenseDatabase, value: str, expected: tuple[object, ...]
) -> None:
    assert _answer(corpus_db, value) == expected


@pytest.mark.parametrize(
    ("text", "license_id", "head"),
    [
        ("GPL-2.0 or later", "GPL-2.0-or-later", "GPL-2.0"),
        ("GPL v2 or _ later", "GPL-2.0-or-later", "GPL v2"),
        ("GPL-2.0 or later", "GPL-2.0-only", None),  # no "-or-later" ID
        ("GPL-2.0 or later", "GPL-2.0", None),
        ("GPL 2.0-or-later", "GPL-2.0-or-later", None),  # joined to the ID
        ("GPL-2.0 x or later", "GPL-2.0-or-later", "GPL-2.0 x"),
        ("GPL-2.0 later", "GPL-2.0-or-later", None),  # only part of it
        ("or later", "GPL-2.0-or-later", None),  # no licence before it
    ],
)
def test_grant_head(text: str, license_id: str, head: str | None) -> None:
    assert _grant_head(text, license_id) == head


# --- item 5: a qualifier on a reference is malformed --------------------------


@pytest.mark.parametrize(
    "value",
    [
        "LicenseRef-x+",
        "LicenseRef-x or later",
        "LicenseRef-x or-later",
        "LicenseRef-x or any later version",
        "LicenseRef-x-only or later",
    ],
)
def test_a_qualifier_on_a_reference_is_malformed(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert _answer(corpus_db, value) == (
        None,
        "malformed",
        f"qualifier on a reference: {value}",
    )
