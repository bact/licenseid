# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` and the words and marks a loose reading drops (task T8,
R7 item 3). Characterisation: what the resolver answered before the guard
of dropped words, so that the change shows as a flip of ``MOVES``."""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve

#: Read today by dropping a list marker, a comment marker or a dangling mark.
MOVES = {
    "REM MIT": "MIT",
    "1. MIT": "MIT",
    "x. MIT": "MIT",
    "iv. MIT": "MIT",
    "- MIT": "MIT",
    "-- MIT": "MIT",
    "MIT -": "MIT",
    "Apache 2.0 -": "Apache-2.0",
    "MIT ...": "MIT",
    ". MIT": "MIT",
}
#: Not read today, and not after: a negation or a qualifier is no marker.
STAYS = [
    "not MIT",
    "no MIT",
    "except MIT",
    "MIT modified",
    "MIT-like",
    "MIT style",
    "MIT draft",
    "MIT v2",
    "copyright MIT",
    "x MIT",
    "MIT.txt",
]


@pytest.mark.parametrize("value", sorted(MOVES), ids=lambda v: v[:24])
def test_before_the_guard_a_dropped_word_is_read(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert resolve(value, corpus_db)["expression"] == MOVES[value]  # MOVES


@pytest.mark.parametrize("value", STAYS, ids=lambda v: v[:24])
def test_a_negation_or_qualifier_is_not_read(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert resolve(value, corpus_db)["expression"] is None
