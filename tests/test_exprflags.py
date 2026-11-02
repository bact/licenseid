# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The flags of an expression (``licenseid.exprflags``, F1 and F2 of the
contract batch): AND every operand, OR any, WITH the licence's; None when an
operand cannot be judged; on the List only when every ID is."""
# pylint: disable=redefined-outer-name,missing-function-docstring

from collections.abc import Generator

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db

from licenseid.database import LicenseDatabase
from licenseid.exprflags import expression_flags
from licenseid.identifiers import parse_declared

ROWS = (
    Lic("MIT", "MIT License", True, True, True),
    Lic("0BSD", "BSD Zero Clause License", True, True, False),
    Lic("WTFPL", "WTFPL", True, False, True),
    Lic("Proprietary-1.0", "A licence neither approves", True, False, False),
    Lic("GPL-2.0-only", "GNU General Public License v2.0 only", True, True, True),
)


@pytest.fixture
def db() -> Generator[LicenseDatabase, None, None]:
    for path in seeded_db("exprflags", ROWS, ["Classpath-exception-2.0"]):
        yield LicenseDatabase(path, create=False)


@pytest.mark.parametrize(
    ("expression", "spdx", "osi", "fsf"),
    [
        ("MIT", True, True, True),
        ("MIT+", True, True, True),  # the "+" names the same family
        ("0BSD AND WTFPL", True, False, False),
        ("0BSD OR WTFPL", True, True, True),
        ("0BSD AND (MIT OR WTFPL)", True, True, False),
        ("Proprietary-1.0 OR Proprietary-1.0", True, False, False),
        ("Proprietary-1.0 AND MIT", True, False, False),
        ("GPL-2.0-only WITH Classpath-exception-2.0", True, True, True),
        # an exception not in this database: not on its List, the licence's
        # flags still
        ("MIT WITH Font-exception-2.0", False, True, True),
        # cannot be judged: None, whatever the other operands say
        ("LicenseRef-x", False, None, None),
        ("MIT OR LicenseRef-x", False, None, None),
        ("Proprietary-1.0 AND LicenseRef-x", False, None, None),
        ("MIT AND Apache-2.0", False, None, None),  # Apache-2.0: no row here
        ("DocumentRef-d:LicenseRef-x OR MIT", False, None, None),
        ("LicenseRef-x WITH Classpath-exception-2.0", False, None, None),
        ("(MIT OR 0BSD) AND (WTFPL OR LicenseRef-x)", False, None, None),
    ],
)
def test_the_flags_of_an_expression(
    db: LicenseDatabase, expression: str, spdx: bool, osi: bool | None, fsf: bool | None
) -> None:
    tree = parse_declared(expression)
    assert tree is not None
    assert expression_flags(tree, db) == {
        "is_spdx": spdx,
        "is_osi_approved": osi,
        "is_fsf_libre": fsf,
    }


def test_a_flag_is_a_bool_or_none(db: LicenseDatabase) -> None:
    """A row's 0 and 1 come back as False and True, never as integers."""
    tree = parse_declared("MIT AND 0BSD")
    assert tree is not None
    flags = expression_flags(tree, db)
    assert flags["is_osi_approved"] is True and flags["is_fsf_libre"] is False
