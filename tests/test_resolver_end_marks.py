# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` and the marks at the two ends of a value (task T8; decisions
P77 to P79). Characterisation first: the answers before the rule, so that
the change shows as a flip of the values marked ``MOVES``."""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve

#: Refused: a mark at the start, two or more marks or an ellipsis at the end.
REFUSED = {
    ".GPL-3.0-only": "character dropped: U+002E",  # a cut value (P78)
    "...GPL-3.0-only": "character dropped: U+002E",
    "-MIT": "character dropped: U+002D",
    "-- MIT": "character dropped: U+002D",
    "; MIT": "character dropped: U+003B",
    "... MIT": "character dropped: U+002E",
    "MIT..": "character dropped: U+002E",
    "MIT...": "character dropped: U+002E",
    "MIT.,": "character dropped: U+002E U+002C",
    "MIT;;": "character dropped: U+003B",
    "MIT.;": "character dropped: U+003B U+002E",
    "MIT\u2026": "character dropped: U+2026",
    "MIT -": "character dropped: U+002D",
}
#: Read: one single mark at the end, white space around it allowed (P77).
READ = {
    "MIT;": "MIT",
    "MIT :": "MIT",
    "MIT .": "MIT",
    "MIT ; ": "MIT",
    "Apache-2.0;": "Apache-2.0",
    "Apache 2.0:": "Apache-2.0",
    "MIT.": "MIT",
    "MIT,": "MIT",
    "MIT ,": "MIT",
    "GPLv2 or later;": "GPL-2.0-or-later",
    "MIT; OR ISC": "ISC OR MIT",  # an operand follows the rule alone (P79)
    "MIT OR ISC;": "ISC OR MIT",
}


@pytest.mark.parametrize("value", sorted(REFUSED), ids=lambda v: v[:20])
def test_marks_that_are_not_one_ending_are_refused(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert got["reason"] == REFUSED[value]
    assert [s["kind"] for s in got["steps"]] == ["drop"]


@pytest.mark.parametrize("value", sorted(READ), ids=lambda v: v[:20])
def test_one_mark_at_the_end_is_an_ending(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] == READ[value]
    assert got["reason"] is None


def test_the_ending_is_a_separator_step(corpus_db: LicenseDatabase) -> None:
    got = resolve("MIT ; ", corpus_db)
    assert got["category"] == "separator"
    assert [(s["kind"], s["from"], s["to"]) for s in got["steps"]] == [
        ("trim", "MIT ; ", "MIT ;"),
        ("separator", "MIT ;", "MIT"),
    ]
