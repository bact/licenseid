# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A tag that lists another licence after an "or later" grant gets no answer
(roadmap item 46).

``SPDX-License-Identifier: GPL-2.0 or later, ISC`` answered ``GPL-2.0-or-later``,
exact, and dropped ISC; ``resolve()`` (so the argument and a field) refuses
it. The tag reader ends its expression at the grant and judged the words
after it only for "or later" itself. A licence of the List listed after the
grant (a reference, an ID by ``looseid.lists_another``) is refused now;
prose after it keeps the reading (``, see COPYING``, ``, the same as Ruby``).
"""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from grant_channels import CHANNELS, answers

from licenseid import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.looseid import lists_after_grant

#: Tags that list another licence after a grant: no answer.
REFUSED = [
    "GPL-2.0 or later, ISC",
    "GPL-2.0 or later; MIT",
    "GPL-2.0 or later / Apache-2.0",
    "GPL-2.0 or later, LicenseRef-x",
    "GPL-2.0 or later, Zlib",
    "GPL-2.0 or later version, ISC",
    "GPL-2.0 or any later version, ISC",
    "(GPL-2.0 or later), ISC",
    "MIT OR GPL-2.0 or later, ISC",
    "GPL-2.0 or later & MIT",
    "LGPLv2 or later, ISC",
    "((GPL-2.0 or later)), ISC",  # the brackets the reader closes are no offset
    # a licence listed after a grant that another grant ends
    "GPL-2.0 or later, GPL-3.0 or later",
    "GPL-2.0 or later, ISC or later",
    "GPL-2.0 or later; LGPL-2.1 or any later version",
]

#: ``value: expression`` read after a grant: prose, a number, a comment closer.
KEPT = {
    "GPL-2.0 or later, the same as Ruby": "GPL-2.0-or-later",
    "GPL-2.0 or later, see COPYING": "GPL-2.0-or-later",
    "GPL-2.0 or later (see COPYING)": "GPL-2.0-or-later",
    "GPL-2.0 or later, 2009": "GPL-2.0-or-later",
    "GPL-2.0 or later, Intel Corporation": "GPL-2.0-or-later",
    "MIT OR GPL-2.0 or later, see COPYING": "GPL-2.0-or-later OR MIT",
    "MIT AND GPL-2.0 or later, see LICENSE": "GPL-2.0-or-later AND MIT",
    "GPL-2.0 or later -->": "GPL-2.0-or-later",
    "GPL-2.0 or later */": "GPL-2.0-or-later",
    "MIT or later": "MIT+",
    "GPL-2.0 or later": "GPL-2.0-or-later",
}


@pytest.mark.parametrize("value", REFUSED, ids=lambda v: v[:34])
def test_a_tag_that_lists_a_licence_after_a_grant_gets_no_answer(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert answers(corpus_db, value)["tag"] is None


@pytest.mark.parametrize("value", sorted(KEPT), ids=lambda v: v[:34])
def test_prose_after_a_grant_keeps_the_reading_of_a_tag(
    corpus_db: LicenseDatabase, value: str
) -> None:
    top = answers(corpus_db, value)["tag"]
    assert top is not None
    assert top[0] == KEPT[value]


def test_every_channel_refuses_a_licence_listed_after_a_grant(
    corpus_db: LicenseDatabase,
) -> None:
    """The argument refused it already; a field and a tag refuse it now."""
    got = answers(corpus_db, "GPL-2.0 or later, ISC")
    assert got == {"argument": None, "tag": None, "field": None}


def test_a_field_refuses_a_grant_listed_after_a_grant(
    corpus_db: LicenseDatabase,
) -> None:
    """The name tier still guesses for the argument (``MPL-1.1``, not exact);
    ``resolve()`` refuses it."""
    got = answers(corpus_db, "GPL-2.0 or later, GPL-3.0 or later")
    assert got["tag"] is None
    assert got["field"] is None


def test_a_tag_after_a_listing_does_not_hide_the_next_tag(
    corpus_db: LicenseDatabase,
) -> None:
    text = CHANNELS["tag"]("GPL-2.0 or later, ISC") + CHANNELS["tag"]("MIT")
    found = LicenseDetector(corpus_db.location).detect(text=text)
    assert [(d["expression"], d["method"]) for d in found][:1] == [("MIT", "tag")]


@pytest.mark.parametrize(
    ("value", "read", "expected"),
    [
        ("GPL-2.0 or later, ISC", ("GPL-2.0", "GPL-2.0-or-later"), True),
        ("GPL-2.0 or later, see COPYING", ("GPL-2.0", "GPL-2.0-or-later"), False),
        ("GPL-2.0 or later, ISC", ("GPL-2.0", "GPL-2.0"), False),  # no grant applied
        ("(GPL-2.0 or later), ISC", ("(GPL-2.0)", "(GPL-2.0-or-later)"), True),
        ("((GPL-2.0 or later)), ISC", ("((GPL-2.0))", "((GPL-2.0-or-later))"), True),
    ],
)
def test_lists_after_grant_starts_at_the_end_of_the_grant(
    corpus_db: LicenseDatabase,
    value: str,
    read: tuple[str, str],
    expected: bool,
) -> None:
    assert lists_after_grant(corpus_db, read[0], read[1], value) is expected
