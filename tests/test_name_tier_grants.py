# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""How the name tier reads an "or later" grant, on the names of the whole
3.29.0 List (``licenseid.namerules``; ``test_namehits`` has the made-up rows).

A grant that exempts a cut version is a grant of the licence the hit names,
read by ``licenseid.grantsubject``, and only where the hit's ID carries a
grant: ``Requires Java 1 or later`` is a tool's, and ``Apache License 1 or
later`` names no row of the List. A GPL name that the input writes with
``Lesser``, ``Library`` or ``Affero`` before ``General Public`` is no GPL.
The database holds the List's names and the text of the near neighbours of
the resolver corpus only: a text answer differs on a full one.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name

from collections.abc import Generator
from typing import Any, NamedTuple

import pytest
from conftest import GivenWarnings, make_memory_db_path
from resolver_corpus import corpus_db_path

from licenseid.detector import LicenseDetector

#: The CLI's default bar: a result below it is no answer.
BAR = 0.85
NAME = "name"


class Top(NamedTuple):
    """The top answer at the bar: expression, method, variant stated."""

    expression: str
    method: str
    stated: bool | None


@pytest.fixture(scope="module")
def detector() -> Generator[LicenseDetector, None, None]:
    for path in corpus_db_path("name_tier_grants", make_memory_db_path):
        yield LicenseDetector(path)


def top(detector: LicenseDetector, text: str, **options: Any) -> Top | None:
    found = [r for r in detector.detect(text=text, **options) if r["score"] >= BAR]
    if not found:
        return None
    first = found[0]
    return Top(first["expression"], first["method"], first["variant_stated"])


# Answers that moved: a cut version whose "or later" is another program's, or
# a licence's that has no -or-later ID, and a GNU name of the LGPL or AGPL.
NONE = [
    # A tool's grant after the cut number (Java 1 is no Apache 1.1).
    "Apache License 1. Requires Java 1 or later",
    "Licensed under the Apache License 1. Requires Java 1 or later",
    "Mozilla Public License 1. Needs Firefox 1+ to run it",
    "Licensed under the Mozilla Public License 1. Requires Python 1 or later to build",
    # A grant of the licence itself, and no -or-later ID to name it.
    "Apache License 1 or later",
    "Mozilla Public License 1 or later",
    "Open Software License 1 or later",
    "Common Development and Distribution License 1 or later",
    # One grant takes out one number: the tool's own `1` is no minor.
    "GNU Free Documentation License v1 or later",
    "GNU Free Documentation License v1. Requires Java 1 or later",
    "GNU Free Documentation License v1 or later. Requires Java 1 or later",
    # The whole version of a tool is no version of the licence.
    "Apache License 1. Requires Java 1.1 or later",
    "Apache License 1, built with Ant 1.1",
    "Mozilla Public License 1. Tested with Firefox 1.1",
    "Academic Free License v2. Requires Python 2.1",
    "Academic Free License v2",  # control: AFL-2.0 and AFL-2.1 both
    # The LGPL and the AGPL are no GPL, with a grant or without.
    "GNU Lesser General Public License v2.0 or later",
    "GNU Lesser General Public License v2.0 only",
    "GNU Affero General Public License v2.0 or later",
    "GNU Affero General Public License v2.0 only",
    "Licensed under the GNU Lesser General Public License v2.0 or later, see COPYING",
    "Lesser GNU General Public License v2.0 or later",
    "GNU Lesser General Public License v2.0 or later (LGPL 2.0)",
    "GNU Lesser General Public License v2.0 or later; v2.0 docs apply",
    "GNU Lesser General Public License v2.0 or later. Version 2.0 or later",
]


@pytest.mark.parametrize("text", [pytest.param(t, id=t[:50]) for t in NONE])
def test_no_answer(detector: LicenseDetector, given: GivenWarnings, text: str) -> None:
    assert top(detector, text) is None
    given.take()


@pytest.mark.parametrize("variant", ["auto", "as-written", "only", "or-later"])
def test_no_answer_whatever_the_variant(
    detector: LicenseDetector, given: GivenWarnings, variant: str
) -> None:
    text = "GNU Lesser General Public License v2.0 or later"
    assert top(detector, text, variant=variant) is None
    given.take()


# Answers that must stay: the hit carries the grant, or the grant is not the
# name's business.
STAY = [
    # A cut number with a grant of the licence: the hit is the one -or-later ID.
    (
        "GNU Lesser General Public License v2 or later",
        Top("LGPL-2.1-or-later", NAME, True),
    ),
    (
        "GNU Lesser General Public License v2.1 or later",
        Top("LGPL-2.1-or-later", NAME, True),
    ),
    (
        "GNU Lesser General Public License v3 or later",
        Top("LGPL-3.0-or-later", NAME, True),
    ),
    (
        "GNU Lesser General Public License v3.0 or later",
        Top("LGPL-3.0-or-later", NAME, True),
    ),
    (
        "GNU Library General Public License v2 or later",
        Top("LGPL-2.0-or-later", NAME, True),
    ),
    (
        "GNU Affero General Public License v3 or later",
        Top("AGPL-3.0-or-later", NAME, True),
    ),
    (
        "GNU Free Documentation License v1.3 or later",
        Top("GFDL-1.3-or-later", NAME, True),
    ),
    ("GNU General Public License v2.0 or later", Top("GPL-2.0-or-later", NAME, True)),
    (
        (
            "Licensed under the GNU General Public License v3.0 or later; "
            "docs under GFDL v1.3 or later"
        ),
        Top("GPL-3.0-or-later", NAME, True),
    ),
    # The LGPL or AGPL named beside the GPL: the GPL's name is written too.
    (
        (
            "GNU General Public License v3.0 or later. Not the GNU Affero General "
            "Public License"
        ),
        Top("GPL-3.0-or-later", NAME, True),
    ),
    (
        "GNU General Public License v2.0 only. See also: Lesser General Public License",
        Top("GPL-2.0-only", NAME, True),
    ),
    # A grant of another program's, written apart: the variant is not stated.
    (
        "GNU General Public License v3.0. Requires Python 3 or later",
        Top("GPL-3.0-only", NAME, False),
    ),
    (
        "GNU General Public License v2.0\nRequires Python 3.8 or later.",
        Top("GPL-2.0-only", NAME, False),
    ),
    (
        "GNU General Public License v2.0. LGPL v2.0 or later applies to the docs",
        Top("GPL-2.0-only", NAME, False),
    ),
    # A version written in full right after the name, and a tool's after it.
    ("Apache License 1.1. Requires Java 1", Top("Apache-1.1", NAME, None)),
    ("Apache License 1.1, built with Ant 1", Top("Apache-1.1", NAME, None)),
    ("Apache License 2", Top("Apache-2.0", NAME, None)),
    (
        (
            "EGENIX.COM PUBLIC LICENSE AGREEMENT\nVersion 1.1.0\n\nThis license "
            "agreement is based on the Python CNRI License Agreement, a widely "
            "accepted open- source license.\n\n1."
        ),
        Top("eGenix", NAME, None),
    ),
    # The number of a name that has several is found where the name has it.
    (
        (
            "Licensed under the PNG Reference Library License v1 "
            "(for libpng 0.5 through 1.6.35)"
        ),
        Top("libpng-1.6.35", NAME, None),
    ),
    ("LGPL-2+", Top("LGPL-2.0-or-later", "id", True)),
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [pytest.param(text, top_, id=text[:50]) for text, top_ in STAY],
)
def test_answers_that_stay(
    detector: LicenseDetector, given: GivenWarnings, text: str, expected: Top
) -> None:
    assert top(detector, text) == expected
    given.take()


@pytest.mark.parametrize(
    "text",
    [
        "GNU Lesser General Public License or any later version, v2",
        "GNU Lesser General Public License v2. Use this License or any later version",
    ],
)
def test_a_grant_with_no_number_is_no_error(
    detector: LicenseDetector, given: GivenWarnings, text: str
) -> None:
    """A grant of the licence that names no version exempts no number."""
    top(detector, text)
    given.take()
