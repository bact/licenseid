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

from licenseid import LicenseDatabase, LicenseIdError
from licenseid.records import BUILD_VERSION


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


def test_pin_update_writes_into_a_foreign_file_with_a_current_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, given: GivenWarnings
) -> None:
    ship(monkeypatch, release_bundle(VERSION))
    path = tmp_path / "f.db"
    foreign_license_index(path)
    assert packaged_update(LicenseDatabase(str(path)))  # BUG: no refusal
    given.take()
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT * FROM license_index").fetchall()
    assert ("X", "mine") not in rows  # BUG: the table was emptied


@posix_only
def test_pin_update_writes_through_a_vfs_uri(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, given: GivenWarnings
) -> None:
    ship(monkeypatch, release_bundle(VERSION))
    path = make_ready_file_db(tmp_path / "licenses.db")
    assert packaged_update(LicenseDatabase(f"{path.as_uri()}?vfs=unix"))  # BUG
    given.take()


def test_pin_update_into_a_missing_directory_downloads_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, given: GivenWarnings
) -> None:
    fake = serve(monkeypatch, online())
    handle = LicenseDatabase(str(tmp_path / "no" / "such" / "x.db"))
    with pytest.raises(LicenseIdError):
        handle.update_from_remote()
    assert fake.called  # BUG: main fails at once, with no request
    assert given.take()  # the cache writes that failed


def test_pin_a_file_made_meanwhile_is_rebuilt_over_a_newer_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, given: GivenWarnings
) -> None:
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
    assert handle.update_from_remote(source="packaged", use_cache=False)  # BUG
    given.take()
