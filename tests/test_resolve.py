# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve``: the SPDX expression a declared value stands for, and how."""

from collections.abc import Generator

import pytest
from matcher_db import Lic, seeded_db

import licenseid
from licenseid import LicenseDatabase
from licenseid.resolve import resolve
from licenseid.resolvetypes import CATEGORY_ORDER, LIST_PROVIDES, TRUST, Resolution

ROWS = (
    Lic("MIT", "MIT License"),
    Lic("Apache-2.0", "Apache License 2.0"),
    Lic("Apache-1.1", "Apache Software License 1.1"),
    Lic("GPL-2.0-only", "GNU General Public License v2.0 only"),
    Lic("GPL-2.0-or-later", "GNU General Public License v2.0 or later"),
    Lic("GPL-2.0", "GNU General Public License v2.0 only", is_deprecated=True),
    Lic(
        "GPL-2.0+",
        "GNU General Public License v2.0 or later",
        is_deprecated=True,
        superseded_by="GPL-2.0-or-later",
    ),
    Lic("GPL-3.0-only", "GNU General Public License v3.0 only"),
    Lic("GPL-3.0-or-later", "GNU General Public License v3.0 or later"),
    Lic("GPL-3.0", "GNU General Public License v3.0 only", is_deprecated=True),
    Lic("SMLNJ", "Standard ML of New Jersey License"),
    Lic(
        "StandardML-NJ",
        "Standard ML of New Jersey License",
        is_deprecated=True,
        superseded_by="SMLNJ",
    ),
    Lic("BSD-2-Clause-FreeBSD", "BSD 2-Clause FreeBSD", is_deprecated=True),
)


@pytest.fixture(name="db")
def _db() -> Generator[LicenseDatabase, None, None]:
    for path in seeded_db("test_resolve", ROWS):
        yield LicenseDatabase(path, create=False)


def _summary(r: Resolution) -> tuple[object, ...]:
    return (
        r["expression"],
        r["category"],
        [s["kind"] for s in r["steps"]],
        [(s["kind"], s["applied"]) for s in r["expansions"]],
        r["candidates"],
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # A: no decision
        ("MIT", ("MIT", "exact", [], [], [])),
        ("mit", ("MIT", "lexical", ["id_case"], [], [])),
        ("\t MIT\n", ("MIT", "lexical", ["trim"], [], [])),
        (" mit ", ("MIT", "lexical", ["trim", "id_case"], [], [])),
        ("Apache-2.0+", ("Apache-2.0+", "exact", [], [], [])),
        ("MIT.", ("MIT", "separator", ["separator"], [], [])),
        ("((mit))", ("MIT", "lexical", ["brackets", "id_case"], [], [])),
        # B: the resolver decides
        (
            "Apache2",
            (
                "Apache-2.0",
                "version_spelling",
                ["separator", "version_spelling"],
                [],
                [],
            ),
        ),
        ("Apache_2.0", ("Apache-2.0", "separator", ["separator"], [], [])),
        ("Apache-2", ("Apache-2.0", "version_spelling", ["version_spelling"], [], [])),
        ("apache license 2.0", ("Apache-2.0", "listed_name", ["listed_name"], [], [])),
        (
            "StandardML-NJ",
            (
                "SMLNJ",
                "deprecated_equal_successor",
                ["deprecated_equal_successor"],
                [],
                [],
            ),
        ),
        # C: expansions
        (
            "GPL-2.0+",
            (
                "GPL-2.0-or-later",
                "plus_to_or_later",
                [],
                [("plus_to_or_later", True)],
                [],
            ),
        ),
        (
            "gpl 2.0+",
            (
                "GPL-2.0-or-later",
                "separator",
                ["separator"],
                [("plus_to_or_later", True)],
                [],
            ),
        ),
        (
            "GPLv2 or any later version",
            (
                "GPL-2.0-or-later",
                "version_spelling",
                ["separator", "version_spelling"],
                [("stated_qualifier", True)],
                [],
            ),
        ),
        # a bare deprecated ID is never narrowed: an offer, kept as written
        (
            "GPL-3.0",
            (
                "GPL-3.0",
                "assumed_only",
                [],
                [("assumed_only", False)],
                ["GPL-3.0-only", "GPL-3.0-or-later"],
            ),
        ),
        (
            "gpl-3.0",
            (
                "GPL-3.0",
                "assumed_only",
                ["id_case"],
                [("assumed_only", False)],
                ["GPL-3.0-only", "GPL-3.0-or-later"],
            ),
        ),
        (
            "GPLv3",
            (
                "GPL-3.0",
                "assumed_only",
                ["separator", "version_spelling"],
                [("assumed_only", False)],
                ["GPL-3.0-only", "GPL-3.0-or-later"],
            ),
        ),
        (
            "BSD-2-Clause-FreeBSD",
            (
                "BSD-2-Clause-FreeBSD",
                "deprecated_ambiguous",
                [],
                [("deprecated_ambiguous", False)],
                [],
            ),
        ),
        # "+" follows the deprecation of its base
        (
            "StandardML-NJ+",
            (
                "SMLNJ+",
                "deprecated_equal_successor",
                ["deprecated_equal_successor"],
                [],
                [],
            ),
        ),
        (
            "BSD-2-Clause-FreeBSD+",
            (
                "BSD-2-Clause-FreeBSD+",
                "deprecated_ambiguous",
                [],
                [("deprecated_ambiguous", False)],
                [],
            ),
        ),
        ("MIT +", ("MIT+", "lexical", ["whitespace"], [], [])),
        (
            "(GPL-2.0)+",
            (
                "GPL-2.0-or-later",
                "plus_to_or_later",
                ["brackets"],
                [("plus_to_or_later", True)],
                [],
            ),
        ),
        # a qualifier twice is malformed; a grant that cannot apply is not dropped
        ("GPL-2.0++", (None, "malformed", [], [], [])),
        ("GPL-2.0-only or later", (None, "malformed", [], [], [])),
        ("GPL-2.0+ or later", (None, "malformed", [], [], [])),
        ("MIT or later", (None, "unresolved", [], [], [])),
        # an expression needs a structure and a listed ID, not just the word "or"
        ("MIT OR Foo", (None, "expression", [], [], [])),
        ("Proprietary or custom", (None, "unresolved", [], [], [])),
        ("Licensed with love", (None, "unresolved", [], [], [])),
        ("AND", (None, "unresolved", [], [], [])),
        ("MIT OR", (None, "unresolved", [], [], [])),
        ("(MIT OR Foo", (None, "unresolved", [], [], [])),
        # D: no answer
        ("Proprietary", (None, "unresolved", [], [], [])),
        ("GPL-2.0-only+", (None, "malformed", [], [], [])),
        ("GPL-2.0-or-later+", (None, "malformed", [], [], [])),
        ("MIT\x00", (None, "unresolved", [], [], [])),
        ("\udc80", (None, "unresolved", [], [], [])),
        ("", (None, "unresolved", [], [], [])),
        ("   ", (None, "unresolved", ["trim"], [], [])),
        ("MIT OR Apache2", (None, "expression", [], [], [])),
        ("(MIT OR Apache2)", (None, "expression", ["brackets"], [], [])),
        ("MIT" + "x" * 200, (None, "unresolved", [], [], [])),
    ],
    ids=lambda v: v[:30] if isinstance(v, str) else "",
)
def test_a_value_resolves_with_its_steps(
    db: LicenseDatabase, value: str, expected: tuple[object, ...]
) -> None:
    """Each value gives its expression, category, steps and offers."""
    assert _summary(resolve(value, db)) == expected


@pytest.mark.parametrize(
    "value",
    [
        "mit",
        "Apache2",
        "GPL-2.0+",
        "StandardML-NJ",
        "GPLv2 or later",
        "(mit)",
        " MIT +",
        "Apache License 2.0",
        "StandardML-NJ+",
    ],
)
def test_an_accepted_expression_resolves_to_itself(
    db: LicenseDatabase, value: str
) -> None:
    """Idempotence: the expression of an accepted value is exact."""
    first = resolve(value, db)
    assert first["expression"] is not None
    assert first["expression"] != value  # the input did change
    assert resolve(first["expression"], db)["category"] == "exact"


def test_every_step_cites_a_list_that_provides_its_kind(db: LicenseDatabase) -> None:
    """A step cites the list only for a kind the list provides; a step that
    rests on no list (trimming, brackets, the author's own words) cites none."""
    values = (
        " mit ",
        "(mit)",
        "Apache2",
        "apache license 2.0",
        "StandardML-NJ",
        "BSD-2-Clause-FreeBSD",
        "GPL-2.0+",
        "GPL-3.0",
        "GPL-2.0 or later",
        "MIT +",
    )
    seen = set()
    for value in values:
        r = resolve(value, db)
        lists = {entry["id"]: entry for entry in r["lists"]}
        for step in r["steps"] + r["expansions"]:
            seen.add(step["kind"])
            if step["kind"] in LIST_PROVIDES:
                assert LIST_PROVIDES[step["kind"]] in lists[step["list"]]["provides"]
            else:
                assert step["list"] == ""
    # every kind the table lists is exercised, and so are the ones without a list
    assert seen == set(LIST_PROVIDES) | {
        "trim",
        "whitespace",
        "brackets",
        "stated_qualifier",
    }


def test_the_result_names_the_resolver_and_the_list(db: LicenseDatabase) -> None:
    """Who resolved, and from which list version."""
    r = resolve("MIT", db)
    assert r["resolver"]["version"] == licenseid.__version__
    assert r["resolver"]["purl"] == f"pkg:pypi/licenseid@{licenseid.__version__}"
    (spdx,) = r["lists"]
    assert (spdx["id"], spdx["version"], spdx["id_authority"]) == (
        "spdx-license-list",
        "3.30",
        True,
    )
    assert spdx["url"] == "https://github.com/spdx/license-list-data/releases/tag/v3.30"
    assert spdx["provides"] == sorted(spdx["provides"])


def test_the_same_input_gives_the_same_result(db: LicenseDatabase) -> None:
    """No clock, no randomness."""
    assert resolve("Apache2", db) == resolve("Apache2", db)


def test_the_category_vocabulary_is_closed() -> None:
    """Every category has a trust, and the order lists them all."""
    assert set(TRUST) == set(CATEGORY_ORDER)
