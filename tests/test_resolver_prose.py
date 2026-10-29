# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` reads the prose form of one licence ID (task T8, rules P1 to
P3; decisions Q3, Q18, Q22, P64 to P70)."""
# pylint: disable=missing-function-docstring

import time

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db
from packaged_list import fixture_bundle
from release_fakes import ship

from licenseid import LicenseDatabase, resolve
from licenseid.resolveleaf import Found
from licenseid.resolveprose import read_alone, read_prose
from licenseid.resolvertypes import Resolution
from licenseid.trovenames import TROVE_NAMES

#: Value, expression, step kinds, category.
READ = [
    ("Apache-2.0 license", "Apache-2.0", ["prose_form"], "prose_form"),
    ("Apache-2.0 LICENSE", "Apache-2.0", ["prose_form"], "prose_form"),
    ("MIT Licence", "MIT", ["prose_form"], "prose_form"),
    ("Unlicense license", "Unlicense", ["prose_form"], "prose_form"),
    ("BSD-3-Clause\tLicense", "BSD-3-Clause", ["prose_form"], "prose_form"),
    (
        "BSD 3-Clause License",
        "BSD-3-Clause",
        ["prose_form", "separator"],
        "prose_form",
    ),
    (
        "Apache 2 License",
        "Apache-2.0",
        ["prose_form", "separator", "version_spelling"],
        "prose_form",
    ),
    (
        "Apache License, Version 2.0",
        "Apache-2.0",
        ["prose_form", "separator"],
        "prose_form",
    ),
    ("Apache Licence Version 2.0", "Apache-2.0", ["prose_form", "separator"], None),
    ("Apache License v2.0", "Apache-2.0", ["prose_form", "separator"], None),
    ("Apache License, v 2.0", "Apache-2.0", ["prose_form", "separator"], None),
    ("Apache  License,  VERSION 2.0", "Apache-2.0", ["prose_form", "separator"], None),
    ("The MIT License", "MIT", ["prose_form", "listed_name"], "prose_form"),
    ("the mit license", "MIT", ["prose_form", "listed_name"], None),
    (
        "The BSD 2-Clause License",
        "BSD-2-Clause",
        ["prose_form", "prose_form", "separator"],
        None,
    ),
    ("The Apache-2.0 license", "Apache-2.0", ["prose_form", "prose_form"], None),
    (
        "The Apache License, Version 2.0",
        "Apache-2.0",
        ["prose_form", "prose_form", "separator"],
        None,
    ),
    (
        "The MIT License (MIT)",
        "MIT",
        ["trailing_name", "prose_form", "listed_name"],
        None,
    ),
    (
        "BSD 3-Clause License (BSD-3-Clause)",
        "BSD-3-Clause",
        ["trailing_name", "prose_form", "separator"],
        None,
    ),
    # P64: the end marks the drop guard lets pass
    ("MIT License.", "MIT", ["prose_form"], None),
    ("MIT Licence,", "MIT", ["prose_form"], None),
    (
        "BSD 3-Clause License. ",
        "BSD-3-Clause",
        ["trim", "prose_form", "separator"],
        None,
    ),
    ("Apache License, Version 2.0.", "Apache-2.0", ["prose_form", "separator"], None),
    ("The MIT License...", "MIT", ["prose_form", "listed_name"], None),
]
#: Values that stay unresolved, with the reason for each.
STAYS = [
    "BSD License",  # a trove name that states no licence (Q3)
    "bsd license",
    "Apache Software License",
    "Apache Software License, Version 2.0",
    "Python Software Foundation License",
    "W3C license",  # Q22
    "W3C License.",
    "The W3C License",
    "W3C License (W3C)",
    "Other/Proprietary License",
    "zlib/libpng license",
    "Artistic License",  # a family, no number
    "Dual License",
    "Expat license",
    "Modified BSD License",
    "3-Clause BSD License",
    "License",
    "The License",
    "The",
    "TheMIT License",  # the article stands alone
    "The The Unlicense",  # P75: no second article
    "The The MIT License",
    "MIT License License",  # P75: no second licence word
    "BSD 3-Clause License License",
    "Apache License, Version 2.0 License",
    "GNU General Public License, Version 3",  # P68: no name is reached
    "Apache-2.0 License+",  # a mark after the word helps no reading
    "BSD 3-Clause License+",
    "Apache License, Version 2.0+",
    "The MIT",  # P3 needs P1, P2 or a listed name
    "The Apache-2.0",
    "Apache License",
    "Apache License, Version 3.0",  # no such ID
    "Apache License, Version",
    "Apache License, Version 2.0 License",
    "Apache License, Version 2.0.1",
    "GNU Affero General Public License, Version 3",  # no List name is reached
    "GNU General Public License, Version 3.0",
    "GNU Lesser General Public License v3",  # a trove name: assumed, not P2
    "BSD License v3",
    "MIT License ...",  # a dangling mark is not left off
    "MIT License -",
    "Apache License,Version 2.0",
    "MIT License (Apache-2.0)",  # the parts differ
    "The MIT License (Apache-2.0)",
    "The MIT License ()",
    "MIT (MIT) License",
    "Foo License",
    "MIT OR Apache-2.0 License",  # P1 reads a licence, never an expression
    "MIT License, Apache License, Version 2.0",
]
#: Value, expression, category: the weakest of the parts wins (P1, P2).
WEAKER = [
    ("GPL-3.0 License", "GPL-3.0", "assumed_only"),
    ("GPL-3.0 license.", "GPL-3.0", "assumed_only"),
    ("GPL License, Version 2", "GPL-2.0", "assumed_only"),
    ("The GPLv3 License", "GPL-3.0", "assumed_only"),
    ("GPL-2.0 Licence", "GPL-2.0", "assumed_only"),
]


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("Net-SNMP License", "Net-SNMP"),
        ("Nunit License", "Nunit"),
        ("BSD 2-Clause FreeBSD License", "BSD-2-Clause-FreeBSD"),
        ("eCos license version 2.0", "eCos-2.0"),
    ],
    ids=lambda v: v[:20],
)
def test_a_deprecated_id_is_reached_as_a_separator_spelling_is(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    """P74: the loose key names the right licence; the deprecation policy
    keeps it as written, with no successor (`deprecated_ambiguous`)."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["trust"]) == (
        expression,
        "deprecated_ambiguous",
        "list_data",
    )
    assert kinds(got)[0] == "prose_form"


def test_two_readings_of_a_version_form_must_agree() -> None:
    """P68: ``<name> N`` (loose) and ``<name> License N`` (an exact List name)
    that name two licences leave the value unresolved."""
    rows = (
        Lic("Foo-2.0", "Foo Public 2.0", search_text="foo public"),
        Lic("Bar-1.0", "Foo License 2.0", search_text="foo license"),
        Lic("Baz-3.0", "Baz License 3.0", search_text="baz license"),
        Lic("Baz-3", "Baz Free 3.0", search_text="baz free"),
    )
    for path in seeded_db("test_resolver_prose_agree", rows):
        db = LicenseDatabase(path, create=False)
        assert resolve("Foo License, Version 2.0", db)["expression"] is None
        assert resolve("Baz License, Version 3.0", db)["expression"] is not None


def kinds(got: Resolution) -> list[str]:
    return [s["kind"] for s in got["steps"]]


@pytest.fixture(name="shipped")
def _shipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """The wheel ships the List of the fixtures, for ``source="packaged"``."""
    ship(monkeypatch, fixture_bundle())


@pytest.mark.parametrize(("value", "expression", "steps", "category"), READ, ids=str)
def test_a_prose_form_of_one_id_is_read(
    corpus_db: LicenseDatabase,
    value: str,
    expression: str,
    steps: list[str],
    category: str | None,
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] == expression
    assert kinds(got) == steps
    assert got["category"] == (category or "prose_form")
    assert got["trust"] == "resolver_rule"
    assert (got["candidates"], got["expansions"], got["reason"]) == ([], [], None)
    assert [e["id"] for e in got["lists"]] == ["spdx-license-list"]
    assert got["operands"][0]["expression"] == expression
    assert got["operands"][0]["steps"] == [
        s for s in got["steps"] if s["kind"] != "trim"
    ]


@pytest.mark.parametrize("value", STAYS, ids=lambda v: v[:24])
def test_a_near_miss_is_not_read(corpus_db: LicenseDatabase, value: str) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["steps"]) == (
        None,
        "unresolved",
        [],
    ), got["reason"]


@pytest.mark.parametrize(("value", "expression", "category"), WEAKER, ids=str)
def test_the_weakest_part_wins(
    corpus_db: LicenseDatabase, value: str, expression: str, category: str
) -> None:
    """A prose form never narrows a split ID: it keeps both candidates."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (expression, category)
    assert got["trust"] == "none"
    assert kinds(got)[0] in ("prose_form", "trailing_name")
    assert got["candidates"] == [f"{expression}-only", f"{expression}-or-later"]
    assert [(e["kind"], e["applied"]) for e in got["expansions"]] == [
        ("assumed_only", False)
    ]


def test_the_steps_chain_from_the_value_to_the_id(corpus_db: LicenseDatabase) -> None:
    got = resolve("The Apache License, Version 2.0.", corpus_db)
    assert [(s["from"], s["to"], s["detail"]) for s in got["steps"]] == [
        (
            "The Apache License, Version 2.0.",
            "Apache License, Version 2.0",
            "leading article",
        ),
        ("Apache License, Version 2.0", "Apache 2.0", "version"),
        ("Apache 2.0", "Apache-2.0", ""),
    ]
    assert [s["list"] for s in got["steps"]] == ["", "", "spdx-license-list"]
    assert got["input"] == "The Apache License, Version 2.0."


@pytest.mark.parametrize("name", sorted(TROVE_NAMES), ids=lambda n: n[:24])
def test_no_trove_name_is_read_by_a_prose_rule(
    corpus_db: LicenseDatabase, name: str
) -> None:
    """A name of the trove table keeps the answer the table gives, with or
    without a leading article or an end mark; one that states no licence is
    unresolved in every spelling (Q22)."""
    entry = TROVE_NAMES[name]
    for value in (name, f"The {name}", f"{name}.", f"the {name.upper()}"):
        got = resolve(value, corpus_db)
        if entry.reading == "none":
            assert got["expression"] is None, value
        elif value == name:
            assert kinds(got) != ["prose_form"], value


def test_a_name_that_states_no_licence_is_not_read_by_a_prose_form(
    corpus_db: LicenseDatabase,
) -> None:
    for name in (n for n, e in TROVE_NAMES.items() if e.reading == "none"):
        found = Found()
        assert read_prose(corpus_db, name, found) is False or not found.expression


# --- P2 never reaches a List name the author did not write ---


@pytest.mark.parametrize("family", ["GNU General Public", "GNU Affero General Public"])
@pytest.mark.parametrize("number", ["2", "3", "3.0", "2.0"])
@pytest.mark.parametrize("form", ["{} License v{}", "{} License, Version {}"])
def test_a_gnu_name_with_a_bare_version_is_never_narrowed(
    corpus_db: LicenseDatabase, family: str, number: str, form: str
) -> None:
    got = resolve(form.format(family, number), corpus_db)
    assert not (got["expression"] or "").endswith(("-only", "-or-later"))
    assert got["category"] in ("unresolved", "assumed_only", "trove_name")


@pytest.mark.parametrize(
    "value", ["GPL License v3", "LGPL License, Version 2.1", "AGPL License Version 3"]
)
def test_a_family_with_a_bare_version_follows_the_deprecated_policy(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["category"] in ("assumed_only", "unresolved", "prose_form")
    assert not (got["expression"] or "").endswith(("-only", "-or-later"))


# --- the same answer from the packaged list ---


@pytest.mark.usefixtures("shipped")
@pytest.mark.parametrize(
    "value",
    [row[0] for row in READ] + STAYS + [row[0] for row in WEAKER],
    ids=lambda v: v[:24],
)
def test_the_packaged_list_gives_the_same_answer(
    corpus_db: LicenseDatabase, value: str
) -> None:
    from_db, from_bundle = resolve(value, corpus_db), resolve(value, source="packaged")
    for key in ("expression", "category", "trust", "steps", "reason", "candidates"):
        assert from_bundle[key] == from_db[key], key


# --- P62, P43: a prose form is no operand, but it reads alone ---


@pytest.mark.parametrize(
    ("value", "leaf"),
    [
        ("BSD 3-Clause License OR MIT", "BSD 3-Clause License"),
        ("MIT OR BSD 3-Clause License", "BSD 3-Clause License"),
        ("The MIT License OR Apache-2.0", "The MIT License"),
        ("Apache-2.0 license AND MIT", "Apache-2.0 license"),
    ],
    ids=lambda v: v[:24],
)
def test_a_prose_operand_reads_alone_but_is_no_operand(
    corpus_db: LicenseDatabase, value: str, leaf: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert got["reason"] == f"operand of several words: {leaf}"


@pytest.mark.parametrize(
    "value", ["Foo License OR MIT", "BSD License OR MIT", "W3C license OR MIT"]
)
def test_an_operand_that_does_not_read_alone_is_not_resolved(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert (got["reason"] or "").startswith("operand not resolved: ")


def test_read_alone_reads_a_prose_form(corpus_db: LicenseDatabase) -> None:
    found = Found()
    assert read_alone(corpus_db, "BSD 3-Clause License", found) is True
    assert found.expression == "BSD-3-Clause"
    assert read_alone(corpus_db, "Foo License", Found()) is False


# --- time ---


def test_the_rules_are_linear_on_a_small_input(corpus_db: LicenseDatabase) -> None:
    _time_the_rules(corpus_db, 2_000)


@pytest.mark.benchmark
def test_the_rules_are_linear_on_a_large_input(corpus_db: LicenseDatabase) -> None:
    _time_the_rules(corpus_db, 200_000)


def _time_the_rules(db: LicenseDatabase, size: int) -> None:
    """Each rule on the shapes that can backtrack, called directly (``resolve``
    refuses a value over 2,000 characters first)."""
    spaces = " " * size
    payloads = [
        "x" + spaces,
        "Apache" + spaces + "License",
        "Apache" + spaces + "License," + spaces + "Version" + spaces + "2.0",
        "Apache License, Version " + "1" * size + "x",
        "Apache License, Version " + "1." * size + "x",
        "Apache License, v" + spaces,
        "The" + spaces + "The" + spaces + "License",
        "The" + spaces,
        "License " * size,
        "Apache License, Version 2.0 " * (size // 4),
        "The MIT License (" * (size // 4),
        "." * size,
        "MIT License" + "." * size + "," + spaces,
        "x License" + ". " * size,
        "(" * size + "MIT License" + ")" * size,
    ]
    start = time.monotonic()
    for payload in payloads:
        read_prose(db, payload, Found())
    assert time.monotonic() - start < max(2.0, size / 20_000)


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ('"MIT" License', "character dropped: U+0022"),
        ("1. MIT License", "word dropped: 1"),
        ("- MIT License", "character dropped: U+002D"),
        ("The REM MIT License", "word dropped: rem"),
        ("MIT License;", "character dropped: U+003B"),
        ("MIT License:", "character dropped: U+003A"),
        ("MIT License\u2026", "character dropped: U+2026"),
        ("MIT License?", "character dropped: U+003F"),
        ("MIT License*", "character dropped: U+002A"),
        ("BSD 3-Clause License;", "character dropped: U+003B"),
        ("Apache License, Version 2.0?", "character dropped: U+003F"),
    ],
    ids=lambda v: v[:20],
)
def test_a_reduction_that_would_drop_something_is_refused_with_a_reason(
    corpus_db: LicenseDatabase, value: str, reason: str
) -> None:
    """The head of a prose form is read as it is alone, so the drop guard
    judges it (T6, R7 item 3)."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["reason"]) == (None, reason)
    assert [s["kind"] for s in got["steps"]] == ["drop"]
