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

from licenseid import LicenseDatabase, resolve

#: White space other than a line break, which ends a value's line.
SPACES = ["\t", "\xa0", " ", " ", "　"]
VALUES = ["GPL-2.0{0}or{0}later", "GPL-2.0{0}or later", "MIT{0}or later"]


@pytest.mark.parametrize("space", SPACES, ids=[f"U+{ord(s):04X}" for s in SPACES])
@pytest.mark.parametrize("value", VALUES)
def test_any_white_space_before_the_grant_reads_as_a_space(
    corpus_db: LicenseDatabase, value: str, space: str
) -> None:
    got = resolve(value.format(space), corpus_db)
    spaced = resolve(value.format(" "), corpus_db)
    assert spaced["expression"] is not None
    if space == "\t" or value.startswith("MIT"):
        assert (got["expression"], got["category"]) == (
            spaced["expression"],
            spaced["category"],
        )
    else:
        # BUG: the ID's text keeps the space and reads as a qualifier stated
        # twice; fixed in the next commit.
        assert got["expression"] is None
        assert got["reason"] == "qualifier stated twice: GPL-2.0 or later"
