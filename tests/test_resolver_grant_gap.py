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
    got = resolve(dashed, corpus_db)
    assert got["expression"] == want
    # A dropped dash is a step to the spaced form, trusted as a dropped
    # comma is (#158 review).
    assert got["category"] == "separator"
    assert any(
        s["kind"] == "separator" and spaced.endswith(s["to"]) for s in got["steps"]
    )


@pytest.mark.parametrize(
    "value",
    ["GPL-2.0 or (in - short) any later version", "GPL-2.0 or-later"],
)
def test_a_dash_elsewhere_in_the_grant_is_no_separator(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """Only a dash around the "or" is D10's; one in an aside, or in the
    word "or-later", is the grant's own."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (
        "GPL-2.0-or-later",
        "stated_qualifier",
    )
    assert not got["steps"]


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("GPL-2.0-or later", "GPL-2.0-or-later"),
        ("Apache-2.0-or later", "Apache-2.0+"),
    ],
)
def test_a_dash_that_joins_the_id_to_the_grant_is_spelling(
    corpus_db: LicenseDatabase, value: str, answer: str
) -> None:
    """A dash with no white space beside it is part of a word, read by the
    loose reading with a step (as before #158), not dropped in silence."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (answer, "separator")
    assert got["steps"]


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
