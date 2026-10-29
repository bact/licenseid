# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` and a ``;`` between licences (task T8b; decisions P81 to
P86). Characterisation first: the answers before the rule, so that the
change shows as a flip of the values marked ``MOVES``."""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve

#: Today: unresolved, the reason of the old rule, one operand for the whole.
OLD = [
    "MIT ; Apache 2",  # MOVES
    "MIT;Apache-2.0",  # MOVES
    "MIT; Apache-2.0; ISC",  # MOVES
    "MIT OR ISC; Apache-2.0",  # MOVES
    "MIT and ISC; Apache-2.0",  # MOVES
    "MIT or ISC;Apache-2.0",  # MOVES
    "(MIT; ISC)",  # MOVES
    "MIT; foo",
    "MIT; Apache-2.0;",  # MOVES: the last ; is an ending
]


@pytest.mark.parametrize("value", OLD, ids=lambda v: v[:24])
def test_today_a_semicolon_list_is_one_unresolved_operand(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert got["category"] == "unresolved"
    assert len(got["operands"]) == 1 or value == "MIT or ISC;Apache-2.0"


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("MIT; OR ISC", "ISC OR MIT"),  # the ; ends an operand (P79)
        ("MIT; and ISC", "ISC AND MIT"),
        ("MIT;", "MIT"),
        ("MIT OR ISC;", "ISC OR MIT"),
    ],
)
def test_the_neighbours_that_keep_their_answer(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    assert resolve(value, corpus_db)["expression"] == expression
