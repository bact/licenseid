# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``match()`` reads trove classifier names and paths and an agreeing
trailing name (task T9, rules T1 to T3; decisions Q3, Q18, Q22, Q23,
P45 to P52)."""
# pylint: disable=missing-function-docstring

import time
from collections.abc import Callable

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db
from packaged_list import fixture_bundle, masked
from release_fakes import ship

from licenseid import LicenseDatabase, match
from licenseid.resolveleaf import Found
from licenseid.resolvertypes import Resolution
from licenseid.resolvetrove import read_named
from licenseid.trovenames import TROVE_NAMES

#: Names the List's own names already read: the answer is a listed name.
LISTED = {
    "Attribution Assurance License",
    "Intel Open Source License",
    "MIT License",
    "Motosoto License",
    "Nethack General Public License",
    "Nokia Open Source License",
    "Open Group Test Suite License",
    "PostgreSQL License",
    "Ricoh Source Code Public License",
    "Sleepycat License",
    "University of Illinois/NCSA Open Source License",
    "X.Net License",
}
#: Names whose bracket the List backs too (T3): `listed_name`, read before the
#: table (P63).
TRAILING = {
    "CMU License (MIT-CMU)",
    "CeCILL-B Free Software License Agreement (CECILL-B)",
    "CeCILL-C Free Software License Agreement (CECILL-C)",
    "Boost Software License 1.0 (BSL-1.0)",
    "Common Development and Distribution License 1.0 (CDDL-1.0)",
    "Eclipse Public License 1.0 (EPL-1.0)",
    "Eclipse Public License 2.0 (EPL-2.0)",
    "Historical Permission Notice and Disclaimer (HPND)",
    "Mozilla Public License 1.1 (MPL 1.1)",
    "Mozilla Public License 2.0 (MPL 2.0)",
    "Open Software License 3.0 (OSL-3.0)",
    "SIL Open Font License 1.1 (OFL-1.1)",
    "The Unlicense (Unlicense)",
}
STATED = sorted(k for k, v in TROVE_NAMES.items() if v.reading == "stated")
ASSUMED = sorted(k for k, v in TROVE_NAMES.items() if v.reading == "assumed")
NONE = sorted(k for k, v in TROVE_NAMES.items() if v.reading == "none")
TROVE = "pypi-trove-classifiers"


@pytest.fixture(name="shipped")
def _shipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """The wheel ships the List of the fixtures, for ``source="packaged"``."""
    ship(monkeypatch, fixture_bundle())


def path_of(name: str) -> str:
    prefix = "License :: OSI Approved :: " if TROVE_NAMES[name].osi else "License :: "
    return prefix + name


def kinds(got: Resolution) -> list[str]:
    return [s["kind"] for s in got["steps"]]


def shown(name: str) -> str:
    return name[:24]


# --- T2: a name of the table ---


@pytest.mark.parametrize("name", STATED, ids=shown)
def test_a_name_that_states_one_licence_is_read(
    corpus_db: LicenseDatabase, name: str
) -> None:
    got = match(name, corpus_db)
    assert got["expression"] == TROVE_NAMES[name].ids[0]
    listed = name in LISTED | TRAILING
    assert got["category"] == ("listed_name" if listed else "trove_name")
    assert got["trust"] == ("list_data" if listed else "resolver_rule")
    expected = {True: ["listed_name"], False: ["trove_name"]}[name in LISTED]
    if name in TRAILING:
        expected = ["trailing_name", "listed_name"]
    assert kinds(got) == (expected if listed else ["trove_name"])
    assert [e["id"] for e in got["lists"]] == (
        ["spdx-license-list"] if listed else ["spdx-license-list", TROVE]
    )
    assert (got["candidates"], got["expansions"], got["reason"]) == ([], [], None)


@pytest.mark.parametrize("name", ASSUMED, ids=shown)
def test_a_name_that_writes_a_bare_deprecated_id_stays_assumed(
    corpus_db: LicenseDatabase, name: str
) -> None:
    bare = TROVE_NAMES[name].ids[0]
    got = match(name, corpus_db)
    assert (got["expression"], got["category"], got["trust"]) == (
        bare,
        "assumed_only",
        "none",
    )
    assert got["candidates"] == [f"{bare}-only", f"{bare}-or-later"]
    assert [(s["kind"], s["applied"]) for s in got["expansions"]] == [
        ("assumed_only", False)
    ]
    assert kinds(got) == ["trove_name"]


@pytest.mark.parametrize("name", NONE, ids=shown)
def test_a_name_that_states_no_licence_is_not_read(
    corpus_db: LicenseDatabase, name: str
) -> None:
    got = match(name, corpus_db)
    assert (got["expression"], got["category"], got["steps"]) == (
        None,
        "unresolved",
        [],
    )
    assert [e["id"] for e in got["lists"]] == ["spdx-license-list"]


@pytest.mark.usefixtures("shipped")
def test_the_step_and_the_list_of_a_trove_name() -> None:
    got = match("ISC License (ISCL)", source="packaged")  # no List name
    (the_step,) = got["steps"]
    assert (the_step["kind"], the_step["from"], the_step["to"], the_step["list"]) == (
        "trove_name",
        "ISC License (ISCL)",
        "ISC",
        TROVE,
    )
    spdx, trove = got["lists"]
    assert spdx["id"] == "spdx-license-list"
    assert (trove["id"], trove["version"], trove["source"]) == (TROVE, None, "packaged")
    assert (trove["provides"], trove["id_authority"]) == (["names"], False)
    assert got["operands"][0]["steps"] == got["steps"]


def test_no_trove_list_when_no_step_rests_on_it(corpus_db: LicenseDatabase) -> None:
    for value in ("MIT", "MIT License", "Apache Software License", "GPL-3.0"):
        assert [e["id"] for e in match(value, corpus_db)["lists"]] == [
            "spdx-license-list"
        ]


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("boost software license 1.0 (bsl-1.0)", "BSL-1.0"),
        ("Boost Software License 1.0 (BSL-1.0)", "BSL-1.0"),
        ("mozilla public license 2.0 (mpl-2.0)", "MPL-2.0"),
    ],
    ids=lambda value: value[:12],
)
def test_the_exact_name_reads_as_strong_as_its_lower_case_form(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    """P63: the List backs the head and the bracket, so the answer is
    `listed_name` however the case is written, and no trove list is named."""
    got = match(value, corpus_db)
    assert (got["expression"], got["category"]) == (expression, "listed_name")
    assert kinds(got)[0] == "trailing_name"
    assert [e["id"] for e in got["lists"]] == ["spdx-license-list"]


@pytest.mark.parametrize(
    "value",
    [
        "W3C license",
        "w3c license",
        "W3C  License",
        "zlib/libpng license",
        "python license (cnri python license)",
        "Python   License (CNRI Python License)",
        "gnu library or lesser general public license (lgpl)",
        "bsd license",
        "License :: OSI Approved :: W3C License",
    ],
    ids=lambda value: value[:20],
)
def test_a_name_that_states_no_licence_is_claimed_however_it_is_written(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """P60 as amended: no later rule may read a `none` name (Q22)."""
    found = Found()
    assert read_named(corpus_db, value, found) is True
    assert (found.expression, found.category) == (None, "unresolved")


@pytest.mark.parametrize(
    "value",
    [
        "isc license (iscl)",
        "ISC  License (ISCL)",
        "Isc License (ISCL)",
    ],
    ids=lambda value: value[:12],
)
def test_a_name_that_states_a_licence_is_matched_exactly(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """The looser match only refuses; the table is read as written."""
    got = match(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "unresolved")


@pytest.mark.parametrize(
    "value",
    [
        "MIT\n(MIT)",
        "MIT\u00a0(MIT)",
        "MIT\u2028(MIT)",
        "MIT (MIT)\n",
        "MIT License\x0b(MIT)",
    ],
    ids=["lf", "nbsp", "ls", "trailing-lf", "vt"],
)
def test_only_spaces_and_tabs_stand_before_the_bracket(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """A value is one line: other white space is no separator (the trim of
    the whole value is a step of its own)."""
    got = match(value, corpus_db)
    if value.strip() == "MIT (MIT)":
        assert got["expression"] == "MIT"
        return
    assert "trailing_name" not in kinds(got)


def test_a_head_that_holds_a_bracket_is_not_dropped(
    corpus_db: LicenseDatabase,
) -> None:
    """The leaf reads `GPL-3.0 (or later)`, but a bracket in the head is
    refused here (P58): the parenthesis dropped is the last one only."""
    got = match("GPL-3.0 (or later) (GPL-3.0+)", corpus_db)
    assert "trailing_name" not in kinds(got)
    assert got["expression"] is None


@pytest.mark.parametrize(
    "value",
    [
        "isc license (iscl)",
        "ISC License (ISCL).",
        " ISC License (ISCL) x",
        "ISC License(ISCL)",
        "ISC License  (ISCL)",
        "Apache Software License",  # Q3: by usage only
        "Python Software Foundation License",
        "PSF License",
        "W3C License",  # Q22
        "GNU Library or Lesser General Public License (LGPL)",
        "BSD License",
        "OSI Approved",
        "Public Domain",
    ],
    ids=lambda value: value[:20],
)
def test_a_near_miss_of_a_trove_name_is_not_read(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "unresolved")


@pytest.mark.parametrize(
    "value",
    ['"ISC License (ISCL)"', "(ISC License (ISCL))", "  ISC License (ISCL)\t"],
    ids=["quoted", "bracketed", "spaced"],
)
def test_a_trove_name_is_read_as_it_is_alone_inside_quotes_and_brackets(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["category"]) == ("ISC", "trove_name")
    assert kinds(got)[-1] == "trove_name"
    assert len(kinds(got)) == 2


# --- T1: a path ---


@pytest.mark.parametrize("name", sorted(TROVE_NAMES), ids=shown)
def test_a_path_is_read_as_its_name_is_alone(
    corpus_db: LicenseDatabase, name: str
) -> None:
    bare, via = match(name, corpus_db), match(path_of(name), corpus_db)
    assert via["expression"] == bare["expression"]
    assert via["category"] == bare["category"]
    assert via["candidates"] == bare["candidates"]
    if bare["expression"] is None:
        assert via["steps"] == []
        return
    assert kinds(via) == ["trove_path", *kinds(bare)]
    assert via["steps"][0]["from"] == path_of(name)
    assert via["steps"][0]["to"] == name
    assert via["steps"][0]["list"] == TROVE
    assert [e["id"] for e in via["lists"]] == [
        "spdx-license-list",
        TROVE,
    ]


@pytest.mark.parametrize(
    "value",
    [
        "License :: OSI Approved",  # a category
        "License :: OSI Approved :: ",
        "License :: OSI Approved :: Apache Software License",  # Q3
        "License :: OSI Approved :: BSD License",
        "License :: MIT License",  # the real classifier is under OSI Approved
        "License :: OSI Approved :: Aladdin Free Public License (AFPL)",
        "License :: OSI Approved :: Foo License",
        "license :: osi approved :: MIT License",
        "License :: OSI Approved :: MIT License :: x",
        "License :: OSI Approved :: MIT License\n",  # trimmed: an exact path
        "License :: OSI Approved ::\nMIT License",
        "OSI Approved :: MIT License",
        "Classifier: License :: OSI Approved :: MIT License",
    ],
    ids=lambda value: ascii(value)[:30],
)
def test_a_value_that_is_no_classifier_is_not_read(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = match(value, corpus_db)
    if value.strip() == "License :: OSI Approved :: MIT License":
        assert got["expression"] == "MIT"  # only the trimming differs
        return
    assert (got["expression"], got["category"]) == (None, "unresolved")


def test_a_path_with_free_spaces_round_the_colons_is_read(
    corpus_db: LicenseDatabase,
) -> None:
    got = match("License::OSI Approved \t::  ISC License (ISCL)", corpus_db)
    assert (got["expression"], got["category"]) == ("ISC", "trove_name")


# --- T3: an agreeing trailing name ---


@pytest.mark.parametrize(
    ("value", "expression", "category", "steps"),
    [
        ("MIT License (MIT)", "MIT", "listed_name", ["trailing_name", "listed_name"]),
        ("MIT (MIT)", "MIT", "lexical", ["trailing_name"]),
        ("mit (MIT)", "MIT", "lexical", ["trailing_name", "id_case"]),
        ("Apache-2.0 (Apache2)", "Apache-2.0", "lexical", ["trailing_name"]),
        ("GPL-3.0 (GPLv3)", "GPL-3.0", "assumed_only", ["trailing_name"]),
        ("GPLv2+ (GPL-2.0+)", "GPL-2.0-or-later", "version_spelling", None),
        ("ISC\t(ISC)", "ISC", "lexical", ["trailing_name"]),
    ],
    ids=lambda value: value if isinstance(value, str) and len(value) < 18 else "",
)
def test_a_parenthesis_that_agrees_with_its_head_is_dropped(
    corpus_db: LicenseDatabase,
    value: str,
    expression: str,
    category: str,
    steps: list[str] | None,
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["category"]) == (expression, category)
    assert kinds(got)[0] == "trailing_name"
    if steps is not None:
        assert kinds(got) == steps
    assert got["steps"][0]["from"] == value
    assert got["lists"][0]["id"] == "spdx-license-list"
    assert [e["id"] for e in got["lists"]] == ["spdx-license-list"]


@pytest.mark.parametrize(
    "value",
    [
        "MIT License (ISC)",  # they differ
        "Apache-2.0 (MIT)",
        "MIT License (see LICENSE)",  # only the head reads
        "Foo License (MIT)",  # only the inside reads
        "MIT License ()",
        "MIT License ( )",
        "(MIT)",  # no head: read as MIT by the brackets rule, not this one
        "MIT (MIT) (MIT)",
        "MIT ((MIT))",
        "MIT (MIT",
        "MIT License(MIT)",  # no white space before the bracket
        "BSD (3-clause)",
        "MPL 2.0 (Mozilla Public License)",
        "Python Software Foundation License (BSD-like)",
        "MIT (MIT) x",
        "Apache License (2.0)",
    ],
    ids=lambda value: value[:22],
)
def test_a_parenthesis_that_does_not_agree_is_not_dropped(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = match(value, corpus_db)
    assert "trailing_name" not in kinds(got)


# --- the other readers ---


@pytest.mark.parametrize(
    "value",
    [
        "ISC License (ISCL) OR MIT",
        "MIT OR ISC License (ISCL)",
        "ISC License (ISCL) and MIT",
        "Freeware OR MIT",
    ],
)
def test_a_trove_name_is_no_operand(corpus_db: LicenseDatabase, value: str) -> None:
    """An operand is one word (Q15, P43): the later rules read the whole
    value, which no table row is."""
    got = match(value, corpus_db)
    assert got["expression"] is None
    assert "trove_name" not in kinds(got)


def test_the_operands_of_a_read_value_are_its_one_operand(
    corpus_db: LicenseDatabase,
) -> None:
    value = "  License :: OSI Approved :: GNU General Public License v3 (GPLv3)"
    got = match(value, corpus_db)
    (operand,) = got["operands"]
    assert operand["text"] == value.strip()
    assert operand["span"] == [2, len(value)]
    assert operand["expression"] == "GPL-3.0"
    assert not got["components"]
    assert kinds(got) == ["trim", "trove_path", "trove_name"]


def test_every_name_and_path_is_read_the_same_without_a_database(
    monkeypatch: pytest.MonkeyPatch, bundle_db: LicenseDatabase
) -> None:
    ship(monkeypatch, fixture_bundle())
    values = [*TROVE_NAMES, *map(path_of, TROVE_NAMES)]
    values += ["MIT License (MIT)", "MIT License (ISC)", "ISC\t(ISC)"]
    for value in values:
        assert masked(match(value, bundle_db)) == masked(
            match(value, source="packaged")
        ), value


# --- cost ---


@pytest.mark.parametrize(
    "payload",
    [
        lambda n: "License ::" + " " * n,
        lambda n: "License :: OSI Approved ::" + " :: " * n,
        lambda n: "x" + " " * n + "(" + " " * n + ")",
        lambda n: "(" * n + ")" * n,
        lambda n: "MIT" + " (MIT)" * n,
        lambda n: "a " * n + "(" + "a " * n + ")",
    ],
    ids=["spaces", "colons", "bracket-spaces", "nested", "repeated", "words"],
)
@pytest.mark.usefixtures("shipped")
def test_the_trove_rules_do_not_backtrack(payload: Callable[[int], str]) -> None:
    start = time.monotonic()
    match(payload(300), source="packaged")
    assert time.monotonic() - start < 2.0


@pytest.mark.benchmark
@pytest.mark.usefixtures("shipped")
@pytest.mark.parametrize("size", [1_900, 30_000])
def test_the_trove_rules_are_linear_on_a_long_value(size: int) -> None:
    for value in (
        "License ::" + " " * size,
        "x" + " " * size + "(" + " " * size + ")",
        "MIT License" + " " * size + "(MIT)",
    ):
        start = time.monotonic()
        match(value, source="packaged")
        assert time.monotonic() - start < 5.0


# --- the list decides ---


def test_a_name_whose_id_the_list_lacks_names_nothing() -> None:
    """The table states ISC; a list without it reads nothing (P54)."""
    for path in seeded_db("trove_lacks", [Lic("MIT", "MIT License")]):
        db = LicenseDatabase(path, create=False)
        assert match("ISC License (ISCL)", db)["expression"] is None
        assert (
            match("License :: OSI Approved :: ISC License (ISCL)", db)["expression"]
            is None
        )
        assert match("MIT License (MIT)", db)["expression"] == "MIT"


def test_a_renamed_id_of_the_table_is_followed() -> None:
    rows = [Lic("ISC", "ISC License", is_deprecated=True, superseded_by="ISC-New")]
    for path in seeded_db("trove_renamed", [*rows, Lic("ISC-New", "ISC New")]):
        got = match("ISC License (ISCL)", LicenseDatabase(path, create=False))
        assert (got["expression"], got["category"]) == ("ISC-New", "trove_name")
        assert kinds(got) == ["trove_name", "deprecated_equal_successor"]


@pytest.mark.parametrize(
    ("value", "claimed", "expression"),
    [
        ("W3C License", True, None),  # none: claimed, so no later rule guesses
        ("OSI Approved", True, None),
        ("License :: OSI Approved :: BSD License", True, None),
        ("ISC License (ISCL)", True, "ISC"),
        ("Foo License", False, None),
        ("Apache Software License (Apache 2.0)", False, None),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_read_named_says_whether_a_rule_claims_the_value(
    corpus_db: LicenseDatabase, value: str, claimed: bool, expression: str | None
) -> None:
    found = Found()
    assert read_named(corpus_db, value, found) is claimed
    assert found.expression == expression
    if claimed:
        assert found.reason is None


# --- a trove name in a compound (P43, P62) ---


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        (
            "License :: OSI Approved :: MIT License OR Apache-2.0",
            "operand of several words: License :: OSI Approved :: MIT License",
        ),
        (
            "GNU Affero General Public License v3 OR MIT",
            "operand of several words: GNU Affero General Public License v3",
        ),
        ("BSD License OR MIT", "operand not resolved: BSD License"),
        (
            "License :: OSI Approved :: BSD License OR MIT",
            "operand not resolved: License :: OSI Approved :: BSD License",
        ),
        ("W3C license OR MIT", "operand not resolved: W3C license"),
    ],
    ids=lambda value: value[:24],
)
def test_a_several_word_trove_name_in_a_compound_is_refused_by_its_shape(
    corpus_db: LicenseDatabase, value: str, reason: str
) -> None:
    """The value stays unresolved (an operand is one word, P43); the reason
    says whether the leaf reads alone, trove names and paths included."""
    got = match(value, corpus_db)
    assert got["expression"] is None
    assert got["reason"] == reason


@pytest.mark.parametrize(
    "leaf",
    ["License :: OSI Approved :: MIT License", "GNU Affero General Public License v3"],
)
def test_the_reason_follows_whether_the_leaf_reads_alone(
    corpus_db: LicenseDatabase, leaf: str
) -> None:
    assert match(leaf, corpus_db)["expression"] is not None
    reason = match(f"{leaf} OR MIT", corpus_db)["reason"]
    assert reason is not None
    assert reason.startswith("operand of several words")
