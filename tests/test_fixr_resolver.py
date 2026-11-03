# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Task ``fixr`` of the 0.7.0 review: the ``lists`` of a refused list of
licences, the reason of a refused WITH, of a misplaced "+" in a compound and
of a qualifier on a reference, and one reading of "or later", on the whole
3.29.0 List.

Each test was first a pin of what the branch did (``# BUG:``).
"""
# pylint: disable=missing-function-docstring

import pytest

from licenseid import LicenseDatabase, match


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
    assert "pypi-trove-classifiers" in cited
    # BUG: only the top-level steps are read for the lists
    assert [entry["id"] for entry in got["lists"]] == ["spdx-license-list"]


# --- item 2: the reason of a refused WITH -------------------------------------


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        (
            "MIT WITH Classpath-exception-2.0 or something",
            "exception not found: Classpath-exception-2.0 or something",
        ),
        (
            "Artistic License 1.0 (dist) WITH Autoconf-exception-macro OR Zlib",
            "exception not found: Autoconf-exception-macro OR Zlib",
        ),
        (
            "MIT WITH Classpath-exception-2.0+",
            "exception not found: Classpath-exception-2.0+",
        ),
    ],
)
def test_with_reason(corpus_db: LicenseDatabase, value: str, reason: str) -> None:
    # BUG: words after the exception, or a "+" on a listed one, are called
    # an exception not found
    assert _answer(corpus_db, value) == (None, "unresolved", reason)


# --- item 3: a compound with a misplaced "+" or quoted brackets ---------------


@pytest.mark.parametrize(
    "value", ["(MIT)+ OR ISC", "MIT OR (ISC)+", "(MIT OR ISC)+", '"(MIT)" OR Zlib']
)
def test_compound_reason(corpus_db: LicenseDatabase, value: str) -> None:
    # BUG: the whole value is "not found", not the operand's own reason
    assert _answer(corpus_db, value) == (None, "unresolved", f"not found: {value}")


# --- item 4: one reader of "or later" -----------------------------------------


@pytest.mark.parametrize(
    ("value", "expression", "category"),
    [
        ("GFDL-1.3-invariants or later", "GFDL-1.3-invariants-or-later", "separator"),
        ("GFDL-1.3-invariants or-later", "GFDL-1.3-invariants-or-later", "separator"),
        ("GPL-2.0 or_later", "GPL-2.0-or-later", "separator"),
        ("GPL-2.0 or.later", "GPL-2.0-or-later", "separator"),
    ],
)
def test_or_later_spelling(
    corpus_db: LicenseDatabase, value: str, expression: str, category: str
) -> None:
    # BUG: a spaced "or later" is read as a separator spelling of an ID
    assert _answer(corpus_db, value) == (expression, category, None)


# --- item 5: a qualifier on a reference is malformed --------------------------


@pytest.mark.parametrize(
    "value", ["LicenseRef-x or later", "LicenseRef-x or any later version"]
)
def test_grant_on_reference(corpus_db: LicenseDatabase, value: str) -> None:
    # BUG: unresolved, while ``LicenseRef-x+`` is malformed
    assert _answer(corpus_db, value) == (
        None,
        "unresolved",
        f"qualifier on a reference: {value}",
    )
