# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` and a mark after a ``+``, an exception or a ``LicenseRef-``,
and a lone dash after a prose form (task T8b; decisions P80 and P81).
Characterisation first: the answers before the rule, so that the change
shows as a flip of the values marked ``MOVES``."""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve

EXCEPTION = "GPL-2.0-only WITH Classpath-exception-2.0"

#: Unresolved with no reason today, and no step: the readers returned before
#: the drop guard. MOVES: refused with its reason, or read as an ending.
SILENT = [
    "MIT+;",  # MOVES: read as MIT+
    "GPL-2.0+.",  # MOVES: read as GPL-2.0-or-later
    "MIT+:",  # MOVES
    "MIT+;;",  # MOVES: refused, character dropped
    "GPL-2.0+?",  # MOVES: refused
    f"{EXCEPTION}?",  # MOVES: refused
    f"{EXCEPTION};",  # MOVES: read
    "LicenseRef-a?",  # MOVES: refused
    "LicenseRef-a;",  # MOVES: read
    "MIT License -",  # MOVES: refused, character dropped
]


@pytest.mark.parametrize("value", SILENT, ids=lambda v: v[:24])
def test_today_these_values_name_nothing_and_say_nothing(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert got["reason"] is None
    assert got["steps"] == []


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("MIT+", "MIT+"),
        ("GPL-2.0+", "GPL-2.0-or-later"),
        (EXCEPTION, EXCEPTION),
        ("LicenseRef-a", "LicenseRef-a"),
        ("LicenseRef-a.", "LicenseRef-a."),  # a dot is an ID character
        ("MIT;", "MIT"),
        ("MIT License ;", "MIT"),
        ("MIT -", None),
    ],
)
def test_the_neighbours_that_keep_their_answer(
    corpus_db: LicenseDatabase, value: str, expression: str | None
) -> None:
    assert resolve(value, corpus_db)["expression"] == expression
