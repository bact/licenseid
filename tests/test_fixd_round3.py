# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Fix batch D, round 3: every write of the handle is judged at write time.

``update_from_remote`` wrote into a file that ``reject_foreign_database``
calls ``invalid`` once the schema looked current, made a download before it
found its directory missing, and kept a "no file yet" verdict made at
construction after another process had made the file.
"""

# pylint: disable=missing-function-docstring,redefined-outer-name

import sqlite3
from pathlib import Path

import pytest
from conftest import GivenWarnings, posix_only
from db_asserts import (  # noqa: F401  # pylint: disable=unused-import
    safe_home,  # an autouse fixture: imported to apply it here
)
from db_variants import create_database, make_ready_file_db, writer
from release_fakes import VERSION, online, release_bundle, serve, ship

from licenseid import DatabaseNotReadyError, LicenseDatabase, LicenseIdError
from licenseid.records import BUILD_VERSION
from licenseid.types import UpdateSource


def packaged_update(handle: LicenseDatabase) -> bool:
    """``update_from_remote`` forced from a shipped snapshot: no network."""
    return handle.update_from_remote(source="packaged", force=True, use_cache=False)


def foreign_license_index(path: Path) -> None:
    """licenseid's schema, but ``license_index`` is a plain table of a row:
    ``reject_foreign_database`` calls the file ``invalid``."""
    create_database(path)
    with writer(path) as conn:
        conn.execute("DROP TABLE license_index")
        conn.execute("CREATE TABLE license_index (license_id TEXT, search_text TEXT)")
        conn.execute("INSERT INTO license_index VALUES ('X', 'mine')")


def snapshot(path: Path) -> list[tuple[object, ...]]:
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT * FROM license_index").fetchall()


def test_update_refuses_a_foreign_file_with_a_current_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3-1 (was: ``license_index`` emptied; the constructor, which returns on
    a current schema, did not judge the file, and nothing else did)."""
    ship(monkeypatch, release_bundle(VERSION))
    path = tmp_path / "f.db"
    foreign_license_index(path)
    before = path.read_bytes()
    handle = LicenseDatabase(str(path))
    with pytest.raises(DatabaseNotReadyError, match="^database: invalid: "):
        packaged_update(handle)
    assert path.read_bytes() == before
    assert snapshot(path) == [("X", "mine")]


def test_every_write_path_refuses_a_foreign_file(tmp_path: Path) -> None:
    path = tmp_path / "f.db"
    foreign_license_index(path)
    handle = LicenseDatabase(str(path))
    with pytest.raises(DatabaseNotReadyError, match="^database: invalid: "):
        handle._write_db_records([], [], [], None)  # pylint: disable=protected-access
    with pytest.raises(DatabaseNotReadyError, match="^database: invalid: "):
        handle._ensure_schema()  # pylint: disable=protected-access
    assert snapshot(path) == [("X", "mine")]


def test_a_write_to_a_ready_database_is_refused_while_it_is_locked(
    tmp_path: Path,
) -> None:
    """A write cannot judge a file somebody holds locked, so it is refused,
    as the CLI refuses; reads stay fail-open (see round 2)."""
    path = make_ready_file_db(tmp_path / "licenses.db")
    handle = LicenseDatabase(str(path))
    write = handle._write_db_records  # pylint: disable=protected-access
    holder = sqlite3.connect(path, isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(DatabaseNotReadyError, match="database is locked"):
            write([], [], [], None)
    finally:
        holder.close()


@posix_only
def test_update_through_a_vfs_uri_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3-1 (was: the 740 licences of a real copy became the bundle's one)."""
    ship(monkeypatch, release_bundle(VERSION))
    path = make_ready_file_db(tmp_path / "licenses.db")
    before = path.read_bytes()
    handle = LicenseDatabase(f"{path.as_uri()}?vfs=unix")
    with pytest.raises(DatabaseNotReadyError, match="^database: invalid: "):
        packaged_update(handle)
    assert path.read_bytes() == before


@pytest.mark.parametrize("source", ["auto", "compact", "upstream"])
def test_update_into_a_missing_directory_fails_at_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: UpdateSource
) -> None:
    """R3-2 (was: a download first, and for ``upstream`` the cache file
    blamed): main's line, no request, no file."""
    fake = serve(monkeypatch, online())
    path = tmp_path / "no" / "such" / "x.db"
    handle = LicenseDatabase(str(path))
    with pytest.raises(LicenseIdError) as raised:
        handle.update_from_remote(source=source)
    assert str(raised.value) == (
        "database: update failed: OperationalError: unable to open database file"
    )
    fake.assert_not_called()
    assert not path.parent.exists()


def test_a_file_made_meanwhile_is_judged_before_the_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3-3 (was: rebuilt over a newer build, which must never be rebuilt)."""
    ship(monkeypatch, release_bundle(VERSION))
    path = tmp_path / "licenses.db"
    handle = LicenseDatabase(str(path))  # no file yet
    make_ready_file_db(path)  # another process's update
    with writer(path) as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO db_metadata VALUES (?, ?)",
            [("license_list_version", VERSION), ("build_version", "99")],
        )
    assert BUILD_VERSION != "99"
    before = path.read_bytes()
    assert not handle.update_from_remote(source="packaged", use_cache=False)
    assert path.read_bytes() == before  # unchanged: already at the version


def test_a_foreign_file_made_meanwhile_is_refused_by_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ship(monkeypatch, release_bundle(VERSION))
    path = tmp_path / "late.db"
    handle = LicenseDatabase(str(path))
    foreign_license_index(path)
    with pytest.raises(DatabaseNotReadyError, match="^database: invalid: "):
        packaged_update(handle)
    assert snapshot(path) == [("X", "mine")]


def test_an_empty_file_made_meanwhile_is_completed_by_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, given: GivenWarnings
) -> None:
    ship(monkeypatch, release_bundle(VERSION))
    path = tmp_path / "late.db"
    handle = LicenseDatabase(str(path))
    path.write_bytes(b"")
    assert packaged_update(handle)
    given.take()
    assert handle.get_metadata()["license_list_version"] == VERSION
