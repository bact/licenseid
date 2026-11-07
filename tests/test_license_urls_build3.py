# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A database of build 3, which has no ``license_urls``, is read as it is:
opening it writes nothing, so a read-only one answers as before, its pages
of the List read as no rows, and ``update`` rebuilds it with them. Reading a
URL by its ID (``spdx:MIT``) needs no table."""
# pylint: disable=missing-function-docstring

import os
import sqlite3
import stat
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings, posix_only
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import writer
from list_entries import exc_entry, lic_entry
from packaged_list import database_of, synthetic_bundle

from licenseid import resolve
from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.dbcheck import check_database_ready, is_ready, reject_foreign_database
from licenseid.dbconnection import Connections
from licenseid.dbschema import OPTIONAL_OBJECTS, SCHEMA_OBJECTS, schema_state
from licenseid.errors import DatabaseNotReadyError
from licenseid.records import BUILD_VERSION, LicenseInsertRecord, Records

APACHE = "https://www.apache.org/licenses/LICENSE-2.0"
LICENSES = (
    lic_entry("MIT", "MIT License", see_also=["https://opensource.org/license/mit/"]),
    lic_entry("Apache-2.0", "Apache License 2.0", see_also=[APACHE]),
)
TEXTS = {"MIT": "Text of MIT.", "Apache-2.0": "Text of Apache-2.0."}
EXCEPTIONS = (exc_entry("LLVM-exception", "LLVM Exception"),)
RAW = synthetic_bundle(LICENSES, TEXTS, EXCEPTIONS)
OUTDATED = (
    f"WARNING: database: build v3 outdated: current v{BUILD_VERSION}"
    "; run 'licenseid update'\n"
)


def _tables(path: Path) -> set[str]:
    with writer(path) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}


def _url_rows(path: Path) -> int:
    with writer(path) as conn:
        found: int = conn.execute("SELECT COUNT(*) FROM license_urls").fetchone()[0]
    return found


def _build_3(path: Path) -> Path:
    """A database as build 3 left it: no ``license_urls``, stamped 3."""
    database_of(RAW, path)
    with writer(path) as conn:
        conn.execute("DROP TABLE license_urls")
        conn.execute("UPDATE db_metadata SET value = '3' WHERE key = 'build_version'")
    return path


@pytest.fixture(name="build_3")
def _build_3_fixture(tmp_path: Path) -> Path:
    return _build_3(tmp_path / "licenses.db")


@pytest.fixture(name="build_4")
def _build_4_fixture(tmp_path: Path) -> Path:
    path = tmp_path / "licenses.db"
    database_of(RAW, path)
    return path


def _ro_uri(path: Path) -> str:
    return f"file:{path.as_posix()}?mode=ro"


@pytest.fixture(name="mode_444")
def _mode_444() -> Iterator[list[Path]]:
    """Files to make read-only; their mode is restored at the end, so
    ``tmp_path`` can be removed."""
    made: list[Path] = []
    yield made
    for path in made:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _read_only(path: Path, how: str, made: list[Path]) -> str:
    if how == "uri":
        return _ro_uri(path)
    path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    made.append(path)
    if os.access(path, os.W_OK):  # root writes whatever the mode says
        pytest.skip("this user writes to a mode-444 file")
    return str(path)


def test_the_table_is_licenseids_but_no_read_needs_it() -> None:
    assert OPTIONAL_OBJECTS == {"license_urls"}
    assert OPTIONAL_OBJECTS <= set(SCHEMA_OBJECTS)  # never foreign


def test_a_database_of_build_3_is_current_and_opening_writes_nothing(
    build_3: Path, given: GivenWarnings
) -> None:
    location = str(build_3)
    assert schema_state(Connections(location, False, location, False)) == "current"
    given.take()
    database = LicenseDatabase(location, create=False)
    assert given.lines() == OUTDATED
    assert "license_urls" not in _tables(build_3)
    assert database.get_ids_by_url(str.lower) == {}


@pytest.mark.parametrize("table", [True, False], ids=["build-4", "build-3"])
def test_the_gates_accept_a_database_with_and_without_the_table(
    tmp_path: Path, table: bool
) -> None:
    path = tmp_path / "licenses.db"
    if table:
        database_of(RAW, path)
    else:
        _build_3(path)
    check_database_ready(str(path))
    assert is_ready(str(path))
    reject_foreign_database(str(path))


@pytest.mark.parametrize("other", [None, "notes"], ids=["own", "foreign"])
def test_the_table_is_never_a_foreign_object(build_4: Path, other: str | None) -> None:
    """A database missing a table it needs is ``empty`` for update to fill,
    unless an object beside it is not licenseid's: ``license_urls`` is."""
    with writer(build_4) as conn:
        conn.execute("DROP TABLE db_metadata")
        if other:
            conn.execute(f"CREATE TABLE {other} (x)")
    if other:
        with pytest.raises(DatabaseNotReadyError, match="^database: invalid: "):
            reject_foreign_database(str(build_4))
    else:
        reject_foreign_database(str(build_4))


def _resolve(location: str, value: str) -> tuple[str | None, str | None]:
    found = resolve(value, location)
    return found["expression"], found["reason"]


READS = [
    ("MIT", ("MIT", None)),
    ("spdx:MIT", ("MIT", None)),
    ("https://spdx.org/licenses/MIT", ("MIT", None)),
]


@posix_only
@pytest.mark.parametrize("how", ["uri", "mode-444"])
def test_a_read_only_database_of_build_3_answers(
    build_3: Path,
    how: str,
    mode_444: list[Path],
    given: GivenWarnings,
) -> None:
    location = _read_only(build_3, how, mode_444)
    for value, expected in READS:
        assert _resolve(location, value) == expected
    # A page of the List is read from the table, which is not there.
    assert _resolve(location, APACHE) == (None, f"not found: {APACHE}")
    assert given.conditions() == {"build v3 outdated"}
    assert "license_urls" not in _tables(build_3)


@posix_only
@pytest.mark.parametrize("how", ["uri", "mode-444"])
@pytest.mark.parametrize(
    ("args", "first"),
    [
        (["resolve", "MIT"], "EXPRESSION=MIT\tCATEGORY=exact\tTRUST=identity"),
        (["resolve", "spdx:MIT"], "EXPRESSION=MIT\tCATEGORY=license_url"),
        (["detect", "MIT"], "EXPRESSION=MIT\tMETHOD=id\tEXACT=true"),
        (["is-osi", "MIT"], None),
    ],
    ids=["resolve", "spdx-url", "detect", "is-osi"],
)
def test_the_cli_answers_from_a_read_only_database_of_build_3(
    build_3: Path,
    how: str,
    mode_444: list[Path],
    args: list[str],
    first: str | None,
) -> None:
    location = _read_only(build_3, how, mode_444)
    result = CliRunner().invoke(cli, ["--db", location, *args])
    assert result.exit_code == (0 if first else 1), result.stderr
    if first:
        assert result.stdout.startswith(first)
    assert result.stderr == OUTDATED


@posix_only
@pytest.mark.parametrize("how", ["uri", "mode-444"])
def test_a_read_only_database_of_build_4_reads_a_page(
    build_4: Path, how: str, mode_444: list[Path], given: GivenWarnings
) -> None:
    location = _read_only(build_4, how, mode_444)
    assert _resolve(location, APACHE) == ("Apache-2.0", None)
    assert _resolve(location, "MIT") == ("MIT", None)
    assert given.lines() == ""


def test_update_rebuilds_build_3_with_the_pages(build_3: Path) -> None:
    database = database_of(RAW, build_3)
    assert database.get_metadata()["build_version"] == BUILD_VERSION
    assert _url_rows(build_3) == 2
    assert _resolve(str(build_3), APACHE) == ("Apache-2.0", None)


def test_a_failed_rebuild_leaves_no_table(build_3: Path) -> None:
    """The table is made inside the rebuild's transaction: a rebuild that
    fails takes it back with the rest."""
    database = LicenseDatabase(str(build_3))
    bad = Records([cast(LicenseInsertRecord, ("one column",))], [], [], [])
    with pytest.raises(sqlite3.Error):
        database._write_db_records(bad, None)  # pylint: disable=protected-access
    assert "license_urls" not in _tables(build_3)
