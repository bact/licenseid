# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The flags of an expression (``licenseid.exprflags``, F1 and F2 of the
contract batch): AND every operand, OR any, WITH the licence's, in
three-valued logic (D8): an operand that cannot be judged is None, an OR with
a true operand is true and an AND with a false one false; on the List only
when every ID is."""
# pylint: disable=redefined-outer-name,missing-function-docstring

from collections.abc import Generator

import pytest
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db

from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.exprflags import declared_flags, expression_flags, judged_flags
from licenseid.identifiers import parse_declared

ROWS = (
    Lic("MIT", "MIT License", True, True, True),
    Lic("0BSD", "BSD Zero Clause License", True, True, False),
    Lic("WTFPL", "WTFPL", True, False, True),
    Lic("Proprietary-1.0", "A licence neither approves", True, False, False),
    Lic("GPL-2.0-only", "GNU General Public License v2.0 only", True, True, True),
)


@pytest.fixture
def db_path() -> Generator[str, None, None]:
    yield from seeded_db("exprflags", ROWS, ["Classpath-exception-2.0"])


@pytest.fixture
def db(db_path: str) -> LicenseDatabase:
    return LicenseDatabase(db_path, create=False)


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
        # an operand that cannot be judged: None, unless a judged operand
        # decides it (a true one for OR, a false one for AND: D8)
        ("LicenseRef-x", False, None, None),
        ("MIT OR LicenseRef-x", False, True, True),
        ("Proprietary-1.0 AND LicenseRef-x", False, False, False),
        ("MIT AND Apache-2.0", False, None, None),  # Apache-2.0: no row here
        ("DocumentRef-d:LicenseRef-x OR MIT", False, True, True),
        ("LicenseRef-x WITH Classpath-exception-2.0", False, None, None),
        ("LicenseRef-x OR MIT", False, True, True),  # either order
        ("LicenseRef-x OR LicenseRef-y", False, None, None),
        ("Proprietary-1.0 OR LicenseRef-x", False, None, None),  # no true one
        ("MIT AND LicenseRef-x", False, None, None),  # no false one
        ("0BSD AND LicenseRef-x", False, None, False),  # FSF: 0BSD is not
        ("WTFPL OR LicenseRef-x", False, None, True),  # OSI: WTFPL is not
        ("LicenseRef-x AND Proprietary-1.0 AND MIT", False, False, False),
        ("LicenseRef-x OR (MIT AND Proprietary-1.0)", False, None, None),
        ("LicenseRef-x OR (MIT AND GPL-2.0-only)", False, True, True),
        ("(LicenseRef-x OR MIT) AND (LicenseRef-y OR 0BSD)", False, True, None),
        ("LicenseRef-x WITH Classpath-exception-2.0 OR MIT", False, True, True),
        ("(MIT OR 0BSD) AND (WTFPL OR LicenseRef-x)", False, None, True),
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


# (tag value, is-osi line value and exit, is-fsf line value and exit)
DECIDED = [
    ("MIT OR LicenseRef-x", ("true", 0), ("true", 0)),
    ("LicenseRef-x OR MIT", ("true", 0), ("true", 0)),
    ("Proprietary-1.0 AND LicenseRef-x", ("false", 1), ("false", 1)),
    ("MIT AND LicenseRef-x", ("", 1), ("", 1)),
    ("0BSD AND LicenseRef-x", ("", 1), ("false", 1)),
    ("LicenseRef-x OR LicenseRef-y", ("", 1), ("", 1)),
]


@pytest.mark.parametrize(("value", "osi", "fsf"), DECIDED)
@pytest.mark.parametrize("as_json", [False, True])
def test_the_predicate_commands_follow_the_operand_that_decides(
    db_path: str,
    value: str,
    osi: tuple[str, int],
    fsf: tuple[str, int],
    as_json: bool,
) -> None:
    """D8: ``is-osi`` and ``is-fsf`` answer, and exit 0 for true, when one
    judged operand decides the compound; empty, exit 1, when it does not."""
    for command, key, (flag, code) in (
        ("is-osi", "is_osi_approved", osi),
        ("is-fsf", "is_fsf_libre", fsf),
    ):
        args = ["--db", db_path, command, *(["--json"] if as_json else [])]
        args += ["--text", f"SPDX-License-Identifier: {value}"]
        result = CliRunner().invoke(cli, args)
        assert result.exit_code == code, (command, result.output)
        if as_json:
            shown = {"true": "true", "false": "false", "": "null"}[flag]
            assert f'"{key}":{shown}' in result.stdout
        else:
            assert result.stdout.endswith(f"\t{key.upper()}={flag}\n")


@pytest.mark.parametrize(("value", "osi", "fsf"), DECIDED)
def test_the_api_predicates_agree(
    db_path: str, value: str, osi: tuple[str, int], fsf: tuple[str, int]
) -> None:
    """``is_osi()`` and ``is_fsf()`` give what the commands print."""
    flags = {"true": True, "false": False, "": None}
    detector = LicenseDetector(db_path)
    text = f"SPDX-License-Identifier: {value}"
    assert detector.is_osi(text) is flags[osi[0]]
    assert detector.is_fsf(text) is flags[fsf[0]]


@pytest.mark.parametrize(
    ("value", "osi", "fsf"),
    [
        ("MIT WITH AdditionRef-x", True, True),  # a WITH takes its licence's
        ("MIT WITH AdditionRef-x OR 0BSD", True, True),
        ("0BSD WITH AdditionRef-x AND WTFPL", False, False),
        ("WTFPL WITH DocumentRef-d:AdditionRef-x OR LicenseRef-y", None, True),
        ("MIT with additionref-x", True, True),  # keywords in any case
    ],
)
def test_an_addition_ref_takes_its_licences_flags(
    db: LicenseDatabase, value: str, osi: bool | None, fsf: bool | None
) -> None:
    """The parser reads no ``AdditionRef-*``; the flags are judged without
    it, and the value is not on the List."""
    assert judged_flags(value, db) == {
        "is_spdx": False,
        "is_osi_approved": osi,
        "is_fsf_libre": fsf,
    }


@pytest.mark.parametrize(
    "value", ["MIT OR 0BSD", "MIT WITH Classpath-exception-2.0", "MIT WITH AdditionRef"]
)
def test_judged_flags_are_declared_flags_without_an_addition_ref(
    db: LicenseDatabase, value: str
) -> None:
    assert judged_flags(value, db) == declared_flags(value, db)


def test_a_whole_input_with_an_addition_ref_carries_its_flags(db_path: str) -> None:
    """``detect()`` answers what resolve() reads with the expression's flags
    (``resolvefirst.match_of``)."""
    (found,) = LicenseDetector(db_path).detect("MIT WITH AdditionRef-x OR 0BSD")
    assert (found["expression"], found["is_spdx"]) == (
        "0BSD OR MIT WITH AdditionRef-x",
        False,
    )
    assert (found["is_osi_approved"], found["is_fsf_libre"]) == (True, True)
