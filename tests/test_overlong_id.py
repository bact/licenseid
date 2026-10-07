# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""An overlong ID ending in ``+`` is no match, not a broken database.

``get_license_by_id_prefix`` used to build a SQL ``LIKE`` pattern from its
input, and SQLite refuses a pattern over 50,000 bytes.  The prefix is now
compared in memory.  The rows below reproduce the old failure, pin what must
not change, and guard the fix.
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
from licenseid.dbcache import fold_case
from licenseid.dbconnection import Connections
from licenseid.errors import DatabaseNotReadyError, InvalidInputError
from licenseid.matcher import AggregatedLicenseMatcher

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
def matcher(db_path: str) -> AggregatedLicenseMatcher:
    return AggregatedLicenseMatcher(db_path)


def match_ids(matcher: AggregatedLicenseMatcher, **kwargs: str) -> list[str]:
    return [r["license_id"] for r in matcher.match(**kwargs)]


@pytest.mark.parametrize(
    ("prefix", "found"),
    [
        ("Apache-2", "Apache-2.0"),
        ("apache-2", "Apache-2.0"),  # ASCII case fold
        ("Apache-1", None),  # ties on length
        ("AB-", None),  # ties on length
        ("GPL-2.0", "GPL-2.0-only"),  # the deprecated GPL-2.0 is left out
        ("MIT", "MIT"),  # a whole ID is its own prefix
        ("", None),
        ("  ", None),
        ("Zzz", None),
        ("Apache%", None),  # wildcards are literal
        ("Apache_2", None),
        ("Apache\\", None),  # a backslash is an ordinary character
        ("Apache\\-2", None),  # not an escape (LIKE's ESCAPE made it "-")
        ("M\\IT", None),
    ],
)
def test_prefix_lookup(db_path: str, prefix: str, found: str | None) -> None:
    details = LicenseDatabase(db_path, create=False).get_license_by_id_prefix(prefix)
    assert (details["license_id"] if details else None) == found


def test_prefix_lookup_edge_is_stripped(db_path: str) -> None:
    db = LicenseDatabase(db_path, create=False)
    details = db.get_license_by_id_prefix("  Apache-2 \n")
    assert details is not None
    assert details["license_id"] == "Apache-2.0"


TWINS = (
    Lic("Foo-1.0", "Foo deprecated", is_deprecated=True),  # first, so a NOCASE
    Lic("FOO-1.0", "Foo active"),  # lookup of the folded ID finds this one
    Lic("Kelvin-1.0", "Kelvin licence"),
)


@pytest.mark.parametrize(
    ("prefix", "found", "deprecated"),
    [
        ("foo", "FOO-1.0", False),  # the exact active row, not its twin
        ("Foo", "FOO-1.0", False),
        ("\u212a", None, None),  # KELVIN SIGN is no "k": only ASCII folds
        ("\u212aelvin", None, None),
        ("k", "Kelvin-1.0", False),
    ],
)
def test_prefix_lookup_case(
    prefix: str, found: str | None, deprecated: bool | None
) -> None:
    for path in seeded_db("test_overlong_id_twins", TWINS):
        details = LicenseDatabase(path, create=False).get_license_by_id_prefix(prefix)
        assert (details["license_id"] if details else None) == found
        assert details is None or details["is_deprecated"] is deprecated


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
    matcher: AggregatedLicenseMatcher, kind: str, value: str, ids: list[str]
) -> None:
    assert match_ids(matcher, **{kind: value}) == ids


# What each input gives today; none reaches the prefix lookup with a long
# pattern.  "ids" is the result, "error" an InvalidInputError (a usage error).
NON_TRIGGERING = [
    pytest.param("text", "(" * 5000 + "MIT" + ")" * 5000, ["MIT"], None, id="nested"),
    pytest.param(
        "text", " OR ".join(["MIT"] * 20_000), ["MIT"], None, id="operands-20000"
    ),
    pytest.param("text", "x" * 2_000_000, [], None, id="word-2mb"),
    # 25,001 two-byte characters pass the 50,000-byte mark, yet an explicit ID
    # that is no ID is a usage error before any lookup.
    pytest.param("license_id", "é" * 25_001 + "+", None, "error", id="id-e-acute"),
    pytest.param(
        "text", "SPDX-License-Identifier: " + "é" * 25_001 + "+", [], None, id="tag-e"
    ),
]


@pytest.mark.parametrize(("kind", "value", "ids", "error"), NON_TRIGGERING)
def test_non_triggering_inputs(
    matcher: AggregatedLicenseMatcher,
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


@pytest.mark.parametrize("predicate", ["is_spdx", "is_osi", "is_fsf", "is_open"])
def test_predicate_on_overlong_id_is_false(
    matcher: AggregatedLicenseMatcher, predicate: str
) -> None:
    assert getattr(matcher, predicate)(license_id=BIG + "+") is False


@pytest.mark.parametrize("command", ["match", "is-spdx", "is-osi"])
def test_cli_overlong_id_exits_one(db_path: str, command: str) -> None:
    result = CliRunner().invoke(cli, ["--db", db_path, command, "--id", BIG + "+"])
    assert result.exit_code == 1, result.stderr
    assert "unreadable" not in result.stderr


@pytest.mark.parametrize("prefix", [BIG, "Zzz", "Apache-1"])
def test_prefix_lookup_runs_no_input_built_sql(db_path: str, prefix: str) -> None:
    """After warm-up, no statement holds a LIKE or any part of the input."""
    db = LicenseDatabase(db_path, create=False)
    db.get_license_by_id_prefix("Apache-2")  # fills the table cache
    statements: list[str] = []
    real = Connections.connect

    def trace(self: Connections, write: bool = False) -> sqlite3.Connection:
        conn = real(self, write)
        conn.set_trace_callback(statements.append)
        return conn

    with mock.patch.object(Connections, "connect", autospec=True, side_effect=trace):
        db.get_license_by_id_prefix(prefix)
    assert not any("LIKE" in s.upper() or prefix in s for s in statements), statements


def test_prefix_boundary(db_path: str) -> None:
    db = LicenseDatabase(db_path, create=False)
    longest = max((r.license_id for r in ROWS if not r.is_deprecated), key=len)
    found = db.get_license_by_id_prefix(longest)
    assert found is not None
    assert found["license_id"] == longest
    assert db.get_license_by_id_prefix(longest + "x") is None


@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm"])
@pytest.mark.parametrize("break_db", BREAKERS, ids=lambda f: f.__name__)
def test_real_failure_still_raises(
    tmp_path: Path, break_db: Callable[[Path], None], warm: bool
) -> None:
    """The prefix lookup itself raises on a broken file, cache filled or not:
    a match() would fail earlier, at the deprecated-ID read."""
    path = make_ready_file_db(tmp_path / "b.db")
    db = LicenseDatabase(str(path), create=False)
    if warm:
        assert db.get_license_by_id_prefix("Zzz") is None
    break_db(path)
    with pytest.raises(DatabaseNotReadyError):
        db.get_license_by_id_prefix("Zzz")


def test_null_id_matches_nothing() -> None:
    """A NULL ID (a hand-filled table) is no "None", as SQL's LIKE skipped it."""
    for path in seeded_db("test_overlong_id_null", (Lic("Nonesuch-1.0", "N"),)):
        with sqlite3.connect(path, uri=True) as conn:
            conn.execute("INSERT INTO licenses (license_id, name) VALUES (NULL, 'x')")
        details = LicenseDatabase(path, create=False).get_license_by_id_prefix("no")
        assert details is not None
        assert details["license_id"] == "Nonesuch-1.0"


@pytest.mark.parametrize("stamp", [None, "2026-10-08"], ids=["same", "rebuilt"])
def test_prefix_lookup_follows_a_rebuild(db_path: str, stamp: str | None) -> None:
    """Another process's update is seen once it stamps the database."""
    db = LicenseDatabase(db_path, create=False)
    assert db.get_license_by_id_prefix("Zlib") is None  # fills the cache
    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute("INSERT INTO licenses (license_id, name) VALUES ('Zlib', 'z')")
        stamp_rebuild(conn, stamp)
    details = db.get_license_by_id_prefix("zl")
    assert (details["license_id"] if details else None) == ("Zlib" if stamp else None)


def test_prefix_lookup_folds_each_id_once(db_path: str) -> None:
    """The IDs are folded once per rebuild, not once per lookup: 4,000
    distinct unknown "<id>+" tags used to fold every ID 4,000 times."""
    db = LicenseDatabase(db_path, create=False)
    db.get_license_by_id_prefix("Apache-2")  # fills the cache
    with mock.patch("licenseid.dbcache.fold_case", wraps=fold_case) as spy:
        for i in range(100):
            db.get_license_by_id_prefix(f"Foo-{i}")
    assert spy.call_count == 100  # the prefix only
