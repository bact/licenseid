# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The white space between an ID and its "or later" grant
(``match-resolve-0-8.md`` section 7): any white space reads as a space.
"""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from ordering_helpers import DASHED

from licenseid import LicenseDatabase, resolve

#: White space other than a line break, which ends a value's line.
SPACES = ["\t", "\xa0", " ", " ", "　"]
VALUES = [
    "GPL-2.0{0}or{0}later",
    "GPL-2.0{0}or later",
    "MIT{0}or later",
    "MIT OR GPL-2.0{0}or later",  # a compound's operand (resolvecompound)
    "GPL-2.0 WITH Classpath-exception-2.0{0}or later",  # the licence's grant
]


@pytest.mark.parametrize("space", SPACES, ids=[f"U+{ord(s):04X}" for s in SPACES])
@pytest.mark.parametrize("value", VALUES)
def test_any_white_space_before_the_grant_reads_as_a_space(
    corpus_db: LicenseDatabase, value: str, space: str
) -> None:
    got = resolve(value.format(space), corpus_db)
    spaced = resolve(value.format(" "), corpus_db)
    assert spaced["expression"] is not None
    assert (got["expression"], got["category"]) == (
        spaced["expression"],
        spaced["category"],
    )


@pytest.mark.parametrize(("dashed", "spaced"), DASHED, ids=[d for d, _ in DASHED])
def test_a_dash_between_words_reads_as_a_space(
    corpus_db: LicenseDatabase, dashed: str, spaced: str
) -> None:
    want = resolve(spaced, corpus_db)["expression"]
    assert want is not None
    assert resolve(dashed, corpus_db)["expression"] == want


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("GPL-2.0; or later", "character dropped: U+003B"),
        ("GPL-2.0 ? or later", "character dropped: U+003F"),
        ("MIT -", "character dropped: U+002D"),  # a dash alone at the end
    ],
)
def test_a_mark_that_is_no_dash_is_still_refused(
    corpus_db: LicenseDatabase, value: str, reason: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert got["reason"] == reason


@pytest.mark.parametrize("value", ["GPL-2.0-or-later", "LGPL-2.1-or-later"])
def test_the_id_itself_is_no_grant(corpus_db: LicenseDatabase, value: str) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (value, "exact")
