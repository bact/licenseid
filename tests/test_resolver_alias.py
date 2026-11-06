# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` reads the other names a BSD licence is known by
(``licenseid.resolvealias``: ``New BSD``, ``BSD-3``), and ``detect()``
answers them through ``resolve()``."""
# pylint: disable=missing-function-docstring

import re

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db
from resolver_corpus import LICENSE_LIST, list_rows

from licenseid import LicenseDatabase, LicenseIdWarning, resolve
from licenseid.detector import LicenseDetector
from licenseid.exprtokens import WHITE_SPACE
from licenseid.resolvealias import ALIASES, read_alias
from licenseid.resolveleaf import Found

#: ``{ID: (List name, deprecated)}`` of the List fixture.
_LISTED = {
    str(row[0]): (str(row[1]), bool(row[2]))
    for row in list_rows(LICENSE_LIST, "licenses")
}

#: The words of an alias that the List's own name of its ID quotes.
_LIST_WORDS = {"new", "revised", "simplified"}

#: The words of an alias that only the OSI gives (opensource.org, 2026-11-06).
_OSI_WORDS = {"modified"}

_NUMBERS = {"two": "2", "three": "3"}


def _clauses(alias: str) -> str | None:
    """The clause count *alias* states, as digits, or None."""
    found = re.search(r"\b(\d|two|three)\b|bsd-?(\d)\b|bsd ?(\d)\b", alias)
    if found is None:
        return None
    number = next(group for group in found.groups() if group)
    return _NUMBERS.get(number, number)


def test_every_alias_is_checked() -> None:
    assert sorted(ALIASES) == [
        "2-clause bsd",
        "3-clause bsd",
        "bsd 3",
        "bsd-3",
        "bsd3",
        "modified bsd",
        "new bsd",
        "revised bsd",
        "simplified bsd",
        "two-clause bsd",
    ]
    assert all(alias == alias.casefold() for alias in ALIASES)


@pytest.mark.parametrize("alias", sorted(ALIASES))
def test_each_alias_names_its_id_by_the_list_or_the_osi(alias: str) -> None:
    """An alias states the clause count of its ID, or a word the List's name
    of that ID quotes (``"New" or "Revised"``, ``"Simplified"``), or one the
    OSI gives; and its ID is on the List, in use."""
    license_id = ALIASES[alias]
    name, deprecated = _LISTED[license_id]
    assert not deprecated
    words = set(alias.split()) - {"bsd"}
    clauses = _clauses(alias)
    if clauses is not None:
        assert license_id == f"BSD-{clauses}-Clause"
        return
    (word,) = words
    if word in _LIST_WORDS:
        assert f'"{word}"' in name.casefold(), name
    else:
        assert word in _OSI_WORDS


@pytest.mark.parametrize("word", sorted(_OSI_WORDS))
def test_no_list_name_has_an_osi_word(word: str) -> None:
    """A word only the OSI gives names no other licence of the List: no name
    holds it as a word. ``BSD 3-Clause Modification`` and ``BSD Mark
    Modifications License`` are near, and other licences."""
    holders = [
        license_id
        for license_id, (name, _) in _LISTED.items()
        if word in re.findall(r"[a-z]+", name.casefold())
    ]
    assert holders == []


def test_the_list_quotes_each_word_for_one_licence_only() -> None:
    """``New``, ``Revised`` and ``Simplified`` are quoted in one List name
    each, so the word names one licence."""
    for word in _LIST_WORDS:
        holders = [i for i, (n, _) in _LISTED.items() if f'"{word}"' in n.casefold()]
        assert len(holders) == 1, (word, holders)


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("New BSD", "BSD-3-Clause"),
        ("new BSD", "BSD-3-Clause"),
        ("NEW BSD", "BSD-3-Clause"),
        ("modified BSD", "BSD-3-Clause"),
        ("BSD-3", "BSD-3-Clause"),
        ("BSD 3", "BSD-3-Clause"),
        ("bsd3", "BSD-3-Clause"),
        ("3-clause BSD", "BSD-3-Clause"),
        ("Simplified BSD", "BSD-2-Clause"),
        ("2-clause BSD", "BSD-2-Clause"),
    ],
)
def test_an_alias_is_read_as_its_licence(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["trust"]) == (
        expression,
        "alias_name",
        "resolver_rule",
    )
    (the_step,) = got["steps"]
    assert (the_step["kind"], the_step["from"], the_step["to"]) == (
        "alias_name",
        value,
        expression,
    )
    assert the_step["list"] == "spdx-license-list"
    assert (got["candidates"], got["expansions"], got["reason"]) == ([], [], None)
    assert got["operands"][0]["steps"] == got["steps"]


@pytest.mark.parametrize(
    ("value", "reduced", "expression"),
    [
        ("New BSD License", "New BSD", "BSD-3-Clause"),
        ("New BSD license", "New BSD", "BSD-3-Clause"),
        ("New BSD Licence", "New BSD", "BSD-3-Clause"),
        ("Revised BSD License", "Revised BSD", "BSD-3-Clause"),
        ("Modified BSD License", "Modified BSD", "BSD-3-Clause"),
        ("3-Clause BSD License", "3-Clause BSD", "BSD-3-Clause"),
        ("Simplified BSD license", "Simplified BSD", "BSD-2-Clause"),
        ("2-clause BSD License", "2-clause BSD", "BSD-2-Clause"),
        ("Two-clause BSD license", "Two-clause BSD", "BSD-2-Clause"),
    ],
)
def test_an_alias_with_a_licence_word_is_its_prose_form(
    corpus_db: LicenseDatabase, value: str, reduced: str, expression: str
) -> None:
    """P1 takes the final licence word off; the rest is the alias."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (expression, "alias_name")
    assert [(s["kind"], s["from"], s["to"]) for s in got["steps"]] == [
        ("prose_form", value, reduced),
        ("alias_name", reduced, expression),
    ]


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("New BSD License (BSD-3-Clause)", "BSD-3-Clause"),
        ("Simplified BSD License (BSD-2-Clause)", "BSD-2-Clause"),
    ],
)
def test_a_prose_form_of_an_alias_takes_an_agreeing_short_form(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    """A prose form and its short form in brackets read as one licence (as
    ``The MIT License (MIT)``); the bare alias does not (T3 reads a leaf)."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (expression, "alias_name")
    assert [s["kind"] for s in got["steps"]] == [
        "trailing_name",
        "prose_form",
        "alias_name",
    ]


def test_an_alias_takes_an_article_and_an_end_mark(corpus_db: LicenseDatabase) -> None:
    got = resolve("The New BSD License.", corpus_db)
    assert got["expression"] == "BSD-3-Clause"
    assert [s["kind"] for s in got["steps"]] == [
        "separator",
        "prose_form",
        "prose_form",
        "alias_name",
    ]


@pytest.mark.parametrize(
    "value",
    [
        "BSD",  # no clause count: the trove table's "no licence"
        "BSD License",
        "BSD license",
        "'BSD'",
        "BSD-style",
        "BSD 4",  # no project declares it
        "BSD-4",
        "BSD 2",
        "BSD-2",
        "New BSD 4-clause",
        "4-clause BSD",
        "Simplified",
        "New",
        "Revised",
        "FreeBSD",  # the OSI's BSD-2-Clause, the List's FreeBSD-DOC
        "FreeBSD License",
        "Original BSD",
        "NewBSD",
        "New-BSD",
        "New BSD License License",
        "New BSD;;",
        "New BSD?",
        "BSD-3+",  # no grant on an alias
        "New BSD+",
        "New BSD or later",
        "New BSD (BSD-3-Clause)",  # T3 reads its head as a leaf only
        "New BSD License (BSD-2-Clause)",  # the parts differ
        "BSD-3 (BSD-3-Clause)",
        "Revised BSD License (LICENSE.txt)",
        "Néw BSD",
        "BSD-3 Clause Licence Foo",
        "BSD License v3",  # P2: a version, not a clause count
        "BSD License, Version 3",
        "BSD Licence 3",
    ],
)
def test_a_near_neighbour_is_not_read(corpus_db: LicenseDatabase, value: str) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "unresolved"), value
    assert all(s["kind"] != "alias_name" for s in got["steps"])


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("New BSD;;", "character dropped: U+003B"),
        ("New BSD License;;", "character dropped: U+003B"),
        ("New BSD License?", "character dropped: U+003F"),
        ("Simplified BSD License...", "character dropped: U+002E"),
    ],
)
def test_an_alias_does_not_drop_a_mark(
    corpus_db: LicenseDatabase, value: str, reason: str
) -> None:
    """Marks after an alias are refused as after an ID, with the reason of
    the drop guard (``MIT License;;``)."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["reason"]) == (None, reason)
    assert [s["kind"] for s in got["steps"]] == ["drop"]


def test_an_alias_of_one_word_is_an_operand(corpus_db: LicenseDatabase) -> None:
    """An operand reads as it would alone: ``BSD-3`` is one word; ``New
    BSD`` is two, and no operand (P43)."""
    got = resolve("BSD-3 OR MIT", corpus_db)
    assert (got["expression"], got["category"]) == ("BSD-3-Clause OR MIT", "alias_name")
    refused = resolve("MIT OR New BSD", corpus_db)
    assert refused["expression"] is None
    assert refused["reason"] == "operand of several words: New BSD"


def test_an_alias_whose_id_the_list_lacks_names_nothing() -> None:
    for path in seeded_db("alias_lacks", [Lic("MIT", "MIT License")]):
        db = LicenseDatabase(path, create=False)
        assert resolve("New BSD", db)["expression"] is None
        found = Found()
        with db.reading():
            assert not read_alias(db, "New BSD", found)
        assert (found.expression, found.steps) == (None, [])


@pytest.mark.parametrize("value", ["\u017fimplified BSD", "New B\u017fD"])
def test_case_folds_in_ascii_only(corpus_db: LicenseDatabase, value: str) -> None:
    """A long s, which Python's casefold makes an ``s``, folds to no ASCII
    letter of an alias."""
    found = Found()
    assert read_alias(corpus_db, value, found) is False


@pytest.mark.parametrize(
    ("text", "expression"),
    [
        ("New BSD", "BSD-3-Clause"),
        ("BSD-3", "BSD-3-Clause"),
        ("Revised BSD License", "BSD-3-Clause"),
        ("Simplified BSD", "BSD-2-Clause"),
        ("2-clause BSD License", "BSD-2-Clause"),
    ],
)
def test_detect_answers_an_alias_through_resolve(
    corpus_db: LicenseDatabase, text: str, expression: str
) -> None:
    detector = LicenseDetector(corpus_db.location)
    (found,) = detector.detect(text)
    assert (found["expression"], found["method"], found["exact"]) == (
        expression,
        "name",
        True,
    )


def test_an_explicit_id_reads_a_one_word_alias(corpus_db: LicenseDatabase) -> None:
    """``--id BSD-3`` answers as the argument ``BSD-3`` does."""
    detector = LicenseDetector(corpus_db.location)
    (by_id,) = detector.detect(license_id="BSD-3")
    assert [by_id] == detector.detect("BSD-3")
    assert (by_id["expression"], by_id["exact"]) == ("BSD-3-Clause", True)


@pytest.mark.parametrize("text", ["BSD", "BSD License", "BSD 4", "Simplified"])
def test_detect_answers_no_near_neighbour(
    corpus_db: LicenseDatabase, text: str
) -> None:
    """The corpus database holds the BSD texts, so Tiers 1 and 2 have
    something to retrieve: the refusal is not trivially true."""
    with pytest.warns(LicenseIdWarning, match="too few words for text"):
        assert LicenseDetector(corpus_db.location).detect(text) == []


@pytest.mark.parametrize(
    "value",
    ["New  BSD", "New\tBSD", "New\nBSD", "New\u00a0BSD"],
    ids=["two-spaces", "tab", "line-break", "no-break"],
)
def test_a_run_of_white_space_in_an_alias_is_one_space(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == ("BSD-3-Clause", "alias_name")


def test_the_table_fold_splits_on_white_space_alone() -> None:
    """``resolvetable`` folds with ``str.split()``: it must split on
    ``exprtokens.WHITE_SPACE`` and on nothing ``resolve()`` lets through
    (U+001C to U+001F it refuses first)."""
    splits = {
        chr(code) for code in range(0x110000) if len(f"a{chr(code)}b".split()) == 2
    }
    assert splits - set(WHITE_SPACE) == {"\x1c", "\x1d", "\x1e", "\x1f"}
    assert set(WHITE_SPACE) <= splits
