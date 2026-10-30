# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""An overlong ID ending in ``+`` is no match, not a broken database.

``get_license_by_id_prefix`` used to build a SQL ``LIKE`` pattern from its
input, and SQLite refuses a pattern over 50,000 bytes. The prefix was then
compared in memory, and since item 39 an ID before a "+" is read by ID or as
a loosely written ID (``looseid``), never by a bare prefix. The rows below
reproduce the old failure, pin what must not change, and guard the fix.
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

import sqlite3
from collections.abc import Callable, Generator
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import BREAKERS, make_ready_file_db, stamp_rebuild
from matcher_db import Lic, seeded_db

from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.dbconnection import Connections
from licenseid.detector import LicenseDetector
from licenseid.errors import DatabaseNotReadyError, InvalidInputError
from licenseid.identifiers import normalize_identifier
from licenseid.versionkey import version_key

MIT_TEXT = (
    "permission is hereby granted free of charge to any person obtaining a copy"
    " of this software and associated documentation files to deal in the"
    " software without restriction including without limitation the rights to"
    " use copy modify merge publish distribute sublicense and sell copies"
)
ROWS = (
    Lic("Apache-2.0", "Apache License 2.0", True, True, True),
    Lic("Apache-1.0", "Apache License 1.0"),
    Lic("Apache-1.1", "Apache License 1.1"),
    Lic("GPL-2.0-only", "GNU General Public License v2.0 only", True, True, True),
    Lic("GPL-2.0-or-later", "GNU General Public License v2.0 or later"),
    Lic("GPL-2.0", "GNU General Public License v2.0", False, is_deprecated=True),
    Lic("MIT", "MIT License", True, True, True, search_text=MIT_TEXT),
    Lic("AB-1", "Made-up licence one"),
    Lic("AB-2", "Made-up licence two"),
)
BIG = "A" * 50_001  # a LIKE pattern of this length is over SQLite's limit
MIT_BODY = MIT_TEXT.capitalize()


@pytest.fixture
def db_path() -> Generator[str, None, None]:
    yield from seeded_db("test_overlong_id", ROWS)


@pytest.fixture
def matcher(db_path: str) -> LicenseDetector:
    return LicenseDetector(db_path)


def match_ids(matcher: LicenseDetector, **kwargs: str) -> list[str]:
    return [r["expression"] for r in matcher.detect(**kwargs)]


@pytest.mark.parametrize(
    ("value", "found"),
    [
        ("Apache-2+", "Apache-2.0+"),  # a version written short
        ("apache-2+", "Apache-2.0+"),
        ("Apache2+", "Apache-2.0+"),
        ("GPL-2+", "GPL-2.0-or-later"),  # the "+" is the -or-later ID in use
        ("GPL2+", "GPL-2.0-or-later"),
        ("GPL-2.0-only+", "GPL-2.0-only+"),  # stated twice: left for refusal
        ("GPL-2.0-or-later+", "GPL-2.0-or-later+"),
        ("MI+", "MI+"),  # a bare prefix names nothing: it was MIT+
        ("Apache-1+", "Apache-1.0+"),  # 1 is 1.0, never 1.1
        ("AB+", "AB+"),  # AB-1 or AB-2: neither
        ("Zzz+", "Zzz+"),
        ("Apache_2+", "Apache-2.0+"),  # "_" is a separator, as in "Apache_2.0"
    ],
)
def test_an_id_before_a_plus_is_read_whole_not_by_prefix(
    db_path: str, value: str, found: str
) -> None:
    db = LicenseDatabase(db_path, create=False)
    assert normalize_identifier(value, db) == found


# The ways an overlong "<id>+" reaches the prefix lookup.  Each must be no
# match (an ID) or leave the text's own licence (MIT) found.
LONG_ID = "Apache-" + "2" * 50_001
REPRODUCTIONS = [
    pytest.param("license_id", BIG + "+", [], id="id-a"),
    pytest.param("license_id", LONG_ID + "+", [], id="id-apache"),
    pytest.param(
        "text",
        f"SPDX-License-Identifier: {BIG}+\n{MIT_BODY}",
        ["MIT"],
        id="spdx-tag",
    ),
    pytest.param("text", f"License: {BIG}+\n{MIT_BODY}", ["MIT"], id="license-line"),
    pytest.param(
        "text",
        f"SPDX-License-Identifier: https://spdx.org/licenses/{BIG}+\n{MIT_BODY}",
        ["MIT"],
        id="spdx-url",
    ),
    pytest.param("text", '{"license": "' + BIG + '+"}', [], id="json"),
    # A seventh route, found while recording the non-triggering rows.
    pytest.param("text", f'[project]\nlicense = "{BIG}+"\n', [], id="toml"),
    # Inside an expression, and a LicenseRef- name.
    pytest.param(
        "text", f"SPDX-License-Identifier: ({BIG}+)\n{MIT_BODY}", ["MIT"], id="parens"
    ),
    # An overlong operand voids the tag, with or without "+", as on main.
    pytest.param("text", f"SPDX-License-Identifier: {BIG}+ OR MIT", [], id="or-1"),
    pytest.param("text", f"SPDX-License-Identifier: MIT OR {BIG}+", [], id="or-2"),
    pytest.param(
        "text",
        f"SPDX-License-Identifier: LicenseRef-{BIG}+\n{MIT_BODY}",
        ["MIT"],
        id="licenseref",
    ),
]


@pytest.mark.parametrize(("kind", "value", "ids"), REPRODUCTIONS)
def test_overlong_id_is_no_match(
    matcher: LicenseDetector, kind: str, value: str, ids: list[str]
) -> None:
    assert match_ids(matcher, **{kind: value}) == ids


# What each input gives today; none reaches the prefix lookup with a long
# pattern.  "ids" is the result, "error" an InvalidInputError (a usage error).
NON_TRIGGERING = [
    pytest.param("text", "(" * 5000 + "MIT" + ")" * 5000, ["MIT"], None, id="nested"),
    pytest.param(
        "text", " OR ".join(["MIT"] * 20_000), ["MIT"], None, id="operands-20000"
    ),
    # A long word, not 2 MB: its full-text search costs time in its length.
    pytest.param("text", "x" * 60_000, [], None, id="word-60k"),
    # 25,001 two-byte characters pass the 50,000-byte mark, yet an explicit ID
    # that is no ID is a usage error before any lookup.
    pytest.param("license_id", "é" * 25_001 + "+", None, "error", id="id-e-acute"),
    pytest.param(
        "text", "SPDX-License-Identifier: " + "é" * 25_001 + "+", [], None, id="tag-e"
    ),
]


@pytest.mark.parametrize(("kind", "value", "ids", "error"), NON_TRIGGERING)
def test_non_triggering_inputs(
    matcher: LicenseDetector,
    kind: str,
    value: str,
    ids: list[str] | None,
    error: str | None,
) -> None:
    if error:
        with pytest.raises(InvalidInputError):
            match_ids(matcher, **{kind: value})
        return
    found = match_ids(matcher, **{kind: value})
    if ids is not None:
        assert found == ids


@pytest.mark.parametrize("predicate", ["is_spdx", "is_osi", "is_fsf"])
def test_predicate_on_overlong_id_is_false(
    matcher: LicenseDetector, predicate: str
) -> None:
    assert getattr(matcher, predicate)(license_id=BIG + "+") is False


@pytest.mark.parametrize("command", ["detect", "is-spdx", "is-osi"])
def test_cli_overlong_id_exits_one(db_path: str, command: str) -> None:
    result = CliRunner().invoke(cli, ["--db", db_path, command, "--id", BIG + "+"])
    assert result.exit_code == 1, result.stderr
    assert "unreadable" not in result.stderr


# Short IDs: pytest puts the test ID in PYTEST_CURRENT_TEST, and Windows
# refuses an environment variable over 32,767 characters.
@pytest.mark.parametrize(
    "value", [BIG, "Zzz", "Apache-1"], ids=["big", "unknown", "tie"]
)
def test_an_id_before_a_plus_runs_no_input_built_sql(db_path: str, value: str) -> None:
    """After warm-up, no statement holds a LIKE or any part of the input."""
    db = LicenseDatabase(db_path, create=False)
    normalize_identifier("Apache-2+", db)  # fills the table cache
    statements: list[str] = []
    real = Connections.connect

    def trace(self: Connections, write: bool = False) -> sqlite3.Connection:
        conn = real(self, write)
        conn.set_trace_callback(statements.append)
        return conn

    with mock.patch.object(Connections, "connect", autospec=True, side_effect=trace):
        normalize_identifier(value + "+", db)
    assert not any("LIKE" in s.upper() or value in s for s in statements), statements


@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm"])
@pytest.mark.parametrize("break_db", BREAKERS, ids=lambda f: f.__name__)
def test_real_failure_still_raises(
    tmp_path: Path, break_db: Callable[[Path], None], warm: bool
) -> None:
    """Reading an ID before a "+" raises on a broken file, cache filled or not."""
    path = make_ready_file_db(tmp_path / "b.db")
    db = LicenseDatabase(str(path), create=False)
    if warm:
        assert normalize_identifier("Zzz+", db) == "Zzz+"
    break_db(path)
    with pytest.raises(DatabaseNotReadyError):
        normalize_identifier("Zzz+", db)


@pytest.mark.parametrize("stamp", [None, "2026-10-08"], ids=["same", "rebuilt"])
def test_an_id_before_a_plus_follows_a_rebuild(db_path: str, stamp: str | None) -> None:
    """Another process's update is seen once it stamps the database."""
    db = LicenseDatabase(db_path, create=False)
    assert normalize_identifier("Zlib-1+", db) == "Zlib-1+"  # fills the cache
    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute("INSERT INTO licenses (license_id, name) VALUES ('Zlib-1.0', 'z')")
        stamp_rebuild(conn, stamp)
    assert normalize_identifier("Zlib-1+", db) == ("Zlib-1.0+" if stamp else "Zlib-1+")


def test_each_id_is_keyed_once(db_path: str) -> None:
    """The IDs are keyed once per rebuild, not once per lookup: each distinct
    "<id>+" costs the keys of its own text only."""
    db = LicenseDatabase(db_path, create=False)
    normalize_identifier("Apache-2+", db)  # fills the cache
    with mock.patch("licenseid.versionkey.version_key", wraps=version_key) as spy:
        for i in range(100):
            normalize_identifier(f"Foo-{i}+", db)
    # One key or two per text; one per row would be 100 for each lookup.
    assert spy.call_count <= 2 * 100
