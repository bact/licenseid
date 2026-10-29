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

#: Read today, refused after: a mark at the start touching the ID (BUG), and
#: two or more marks, or an ellipsis, at the end.
MOVES = {
    ".GPL-3.0-only": "GPL-3.0-only",  # BUG: a cut value, AGPL-3.0-only
    "...GPL-3.0-only": "GPL-3.0-only",  # BUG
    "-MIT": "MIT",  # BUG
    "MIT..": "MIT",
    "MIT...": "MIT",
    "MIT.,": "MIT",
    "MIT .": None,  # refused as a dangling mark today, read after
}
#: Refused today, read after: one ; or : at the end.
READ_AFTER = ["MIT;", "MIT :", "Apache-2.0;", "MIT License;"]
#: The same before and after.
KEEPS = {
    "MIT.": "MIT",
    "MIT,": "MIT",
    "MIT ,": "MIT",
    "GPLv2 or later;": "GPL-2.0-or-later",
}


@pytest.mark.parametrize("value", sorted(MOVES), ids=lambda v: v[:20])
def test_before_the_rule_these_are_read(corpus_db: LicenseDatabase, value: str) -> None:
    assert resolve(value, corpus_db)["expression"] == MOVES[value]  # MOVES


@pytest.mark.parametrize("value", READ_AFTER)
def test_before_the_rule_these_are_refused(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] is None  # MOVES


@pytest.mark.parametrize("value", sorted(KEEPS), ids=lambda v: v[:20])
def test_these_are_read_as_before(corpus_db: LicenseDatabase, value: str) -> None:
    assert resolve(value, corpus_db)["expression"] == KEEPS[value]
