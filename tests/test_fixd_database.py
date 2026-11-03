# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Fix batch D of the 0.7.0 review: the database handle and its inputs.

The public ``LicenseDatabase(path)`` wrote licenseid's tables into another
program's SQLite file and made a file out of a mistyped name; ``detect()``
took any object as ``file_path`` (an ``int`` was opened as a descriptor and
closed); ``DatabaseNotReadyError.condition`` and ``.detail`` were ``""`` for
nothing, where the API says ``None``; ``clear-cache`` named ``database`` as
the subject of a cache file it could not delete.
"""

# pylint: disable=missing-function-docstring,redefined-outer-name

import os
import sqlite3
from pathlib import Path

import pytest
from conftest import make_ready_db_path
from db_asserts import (  # noqa: F401  # pylint: disable=unused-import
    safe_home,  # an autouse fixture: imported to apply it here
)
from db_asserts import run_args as run
from db_variants import make_ready_file_db

from licenseid import DatabaseNotReadyError, LicenseDatabase, LicenseDetector, match


def foreign_wal_file(path: Path) -> Path:
    """Another program's database: a table of its own, in WAL mode."""
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE foo (x)")
    sqlite3.connect(path).close()
    return path


def names_in(path: Path) -> set[str]:
    with sqlite3.connect(path) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}


# --- 1. LicenseDatabase(path) and a foreign file or a missing one ---


def test_pin_a_foreign_file_gets_licenseids_tables(tmp_path: Path) -> None:
    foreign = foreign_wal_file(tmp_path / "f.db")
    LicenseDatabase(str(foreign))  # BUG: no refusal, and the file is written to
    assert {"foo", "licenses", "license_index"} <= names_in(foreign)


def test_pin_a_mistyped_name_is_created_and_then_empty(tmp_path: Path) -> None:
    typo = tmp_path / "typo.db"
    with pytest.raises(DatabaseNotReadyError, match="^database: empty: "):
        match("MIT", LicenseDatabase(str(typo)))  # BUG: not found, as with a path
    assert typo.exists()  # BUG: a read made a file


# --- 2. file_path and db_path types ---


def test_pin_an_int_file_path_closes_the_callers_descriptor(tmp_path: Path) -> None:
    db_path, keep_alive = make_ready_db_path("fixd_fd")
    path = tmp_path / "LICENSE"
    path.write_text("MIT\n", encoding="utf-8")
    descriptor = os.open(path, os.O_RDONLY)
    try:
        with pytest.raises(TypeError, match="expected str, bytes or os.PathLike"):
            LicenseDetector(db_path).detect(file_path=descriptor)  # type: ignore[arg-type]
        with pytest.raises(OSError, match="Bad file descriptor"):  # BUG: closed
            os.fstat(descriptor)
    finally:
        keep_alive.close()


def test_pin_bytes_file_path_fails_late(tmp_path: Path) -> None:
    db_path, keep_alive = make_ready_db_path("fixd_bytes")
    try:
        with pytest.raises(FileNotFoundError):  # BUG: not a TypeError
            LicenseDetector(db_path).detect(file_path=b"x")  # type: ignore[arg-type]
    finally:
        keep_alive.close()


def test_pin_bytes_db_path_fails_deep() -> None:
    with pytest.raises(TypeError, match="startswith first arg"):  # BUG: odd text
        LicenseDetector(b"x")  # type: ignore[arg-type]


# --- 3. DatabaseNotReadyError.condition / .detail ---


def test_pin_the_attributes_default_to_an_empty_string() -> None:
    error = DatabaseNotReadyError("database: unreadable")
    assert (error.condition, error.detail) == ("", "")  # BUG: None means nothing


# --- 4. clear-cache: the subject of a cache file that would not go ---


def test_pin_clear_cache_names_database_for_a_cache_file(tmp_path: Path) -> None:
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    (tmp_path / "licenses.json").mkdir()
    result = run("--db", str(db_path), "clear-cache")
    assert result.exit_code == 1
    last = result.stderr.splitlines()[-1]
    # BUG: the subject is the database, which was deleted
    assert last.startswith(
        f"ERROR: database: delete failed: {tmp_path / 'licenses.json'}: "
    )
