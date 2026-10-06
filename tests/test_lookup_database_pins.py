# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Pins found by mutation: one behaviour of the lookup path per test.

Companion to ``test_lookup_database_hardening.py``.
"""

# pylint: disable=missing-function-docstring,protected-access

import contextlib
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest
from conftest import posix_only
from db_asserts import (  # noqa: F401  # pylint: disable=unused-import
    probe_does_not_hang,
    safe_home,
)
from db_variants import make_ready_file_db, writer

from licenseid import DatabaseNotReadyError
from licenseid import database as database_module
from licenseid.database import LicenseDatabase
from licenseid.dbcheck import (
    check_database_ready,
    lookup_error,
    needs_writing,
    unreadable_error,
)
from licenseid.dbschema import schema_state
from licenseid.errors import typed
from licenseid.fingerprint import extract_ngrams
from licenseid.fingerprintstore import store_fingerprints


def _columns(path: Path) -> set[str]:
    with contextlib.closing(sqlite3.connect(path)) as conn:
        return {r[1] for r in conn.execute("PRAGMA table_info(licenses)")}


def test_a_write_without_create_never_makes_the_file(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "gone.db")
    with writer(path) as conn:
        conn.execute("DROP INDEX idx_licenses_name")
    real = schema_state

    def state_then_vanish(connections: object) -> str:
        state = real(connections)  # type: ignore[arg-type]
        path.unlink()  # the file goes between the read and the write
        return state

    with (
        mock.patch.object(database_module, "schema_state", state_then_vanish),
        pytest.raises(DatabaseNotReadyError),
    ):
        LicenseDatabase(str(path), create=False)
    assert not path.exists(), "a write without create made the file"


def test_a_write_inside_a_reading_block_has_its_own_connection(
    tmp_path: Path,
) -> None:
    path = make_ready_file_db(tmp_path / "w.db")
    db = LicenseDatabase(str(path))
    with db.reading():
        db.get_metadata()  # the shared, read-only connection is open now
        with db._connection(write=True) as conn:
            conn.execute("INSERT OR REPLACE INTO db_metadata VALUES ('k', 'v')")
    with contextlib.closing(sqlite3.connect(path)) as conn:
        row = conn.execute("SELECT value FROM db_metadata WHERE key='k'").fetchone()
    assert row == ("v",)


@posix_only  # symlinks
def test_a_dangling_symlink_is_not_a_missing_file(tmp_path: Path) -> None:
    link = tmp_path / "l.db"
    link.symlink_to(tmp_path / "nowhere.db")
    exc = sqlite3.OperationalError("unable to open database file")
    assert "licenseid update" not in str(lookup_error(str(link), exc))
    assert "licenseid update" in str(lookup_error(str(tmp_path / "m.db"), exc))


def test_a_path_below_a_file_is_not_found(tmp_path: Path) -> None:
    (tmp_path / "f").write_text("x")
    with pytest.raises(DatabaseNotReadyError) as info:
        check_database_ready(str(tmp_path / "f" / "x.db"))
    assert str(info.value).startswith("database: not found: "), info.value


def test_an_error_without_text_is_named_by_its_type() -> None:
    error = unreadable_error("x.db", sqlite3.DatabaseError(""))
    assert str(error) == "database: unreadable: x.db: DatabaseError"


def test_typed_names_the_class_and_folds_the_text() -> None:
    assert typed(sqlite3.OperationalError("a; b\nc")) == "OperationalError: a, b c"


def test_needs_writing_is_for_sqlite_errors_only() -> None:
    text = "attempt to write a readonly database"
    assert needs_writing(sqlite3.OperationalError(text))
    assert not needs_writing(OSError(text))
    assert not needs_writing(None)


@posix_only  # a FIFO
@pytest.mark.parametrize("suffix", ["", "-journal"])
def test_a_fifo_behind_a_vfs_uri_does_not_hang(tmp_path: Path, suffix: str) -> None:
    path = make_ready_file_db(tmp_path / "v.db")
    if not suffix:
        path.unlink()
    os.mkfifo(f"{path}{suffix}")
    out = probe_does_not_hang(f"file://{path}?vfs=unix")
    assert "DatabaseNotReadyError" in out, out


@pytest.fixture(name="old_column")
def _old_column(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Path]:
    if sqlite3.sqlite_version_info < (3, 35):
        pytest.skip("ALTER TABLE DROP COLUMN needs SQLite 3.35")
    path = make_ready_file_db(tmp_path / "old.db")
    with writer(path) as conn:
        conn.execute(f"ALTER TABLE licenses DROP COLUMN {request.param}")
    yield path


@pytest.mark.parametrize("old_column", ["norm_license_id", "norm_name"], indirect=True)
def test_a_database_without_a_norm_column_gets_it(
    old_column: Path, request: pytest.FixtureRequest
) -> None:
    column = request.node.callspec.params["old_column"]
    assert column not in _columns(old_column)
    LicenseDatabase(str(old_column), create=False)
    assert column in _columns(old_column)


def test_a_row_without_a_name_is_normalised_to_empty_not_none(
    tmp_path: Path,
) -> None:
    path = make_ready_file_db(tmp_path / "n.db")
    with writer(path) as conn:
        conn.execute("UPDATE licenses SET name = NULL, norm_name = NULL")
    names = LicenseDatabase(str(path), create=False).get_all_names_and_ids()
    assert [n["norm_name"] for n in names] == [""]


def test_stored_norm_columns_are_kept_not_recomputed(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "k.db")
    with writer(path) as conn:
        conn.execute(
            "UPDATE licenses SET norm_license_id = 'stored', norm_name = 'kept'"
        )
    names = LicenseDatabase(str(path), create=False).get_all_names_and_ids()
    assert [(n["norm_license_id"], n["norm_name"]) for n in names] == [
        ("stored", "kept")
    ]


def test_store_fingerprints_replaces_the_old_ones(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "fp.db")
    with writer(path) as conn:
        conn.execute("INSERT INTO license_fingerprints VALUES ('MIT', 'stale', 1.0)")
    store_fingerprints(LicenseDatabase(str(path))._connections)
    with contextlib.closing(sqlite3.connect(path)) as conn:
        row = conn.execute(
            "SELECT count(*) FROM license_fingerprints WHERE ngram = 'stale'"
        ).fetchone()
    assert row == (0,)


def test_fingerprint_hits_keep_the_best_score_per_license(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "hit.db")
    text = "permission is hereby granted free of charge to any person obtaining"
    first, second = sorted(extract_ngrams(text))[:2]
    with writer(path) as conn:
        conn.execute("DELETE FROM license_fingerprints")
        conn.execute(
            "INSERT INTO license_fingerprints VALUES ('MIT', ?, 0.2)", (first,)
        )
        conn.execute(
            "INSERT INTO license_fingerprints VALUES ('MIT', ?, 0.9)", (second,)
        )
    assert LicenseDatabase(str(path)).find_fingerprint_hits(text) == {"MIT": 0.9}
