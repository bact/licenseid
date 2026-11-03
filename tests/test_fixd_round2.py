# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Fix batch D, round 2: where the database handle writes.

The handle refused a database that another process held locked (and a
read-only ``vfs=`` URI), because it judged the file at every open; a failed
``update`` left the mistyped file behind; a dangling symlink was created.
"""

# pylint: disable=missing-function-docstring,redefined-outer-name

import sqlite3
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import posix_only
from db_asserts import run_args as run
from db_asserts import (  # noqa: F401  # pylint: disable=unused-import
    safe_home,  # an autouse fixture: imported to apply it here
)
from db_variants import create_database, make_ready_file_db
from release_fakes import VERSION, release_bundle, ship

from licenseid import DatabaseNotReadyError, LicenseDatabase

HOLD = 2.0  # seconds the child holds the lock: longer than the 1 s probe wait

_HOLDER = """
import sqlite3, sys, time
conn = sqlite3.connect(sys.argv[1], isolation_level=None)
conn.execute("BEGIN EXCLUSIVE")
print("locked", flush=True)
time.sleep(float(sys.argv[2]))
"""


@pytest.fixture
def locked_db(tmp_path: Path) -> Iterator[Path]:
    """A ready database that another process holds locked for ``HOLD`` s."""
    path = make_ready_file_db(tmp_path / "licenses.db")
    with subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(path), str(HOLD)],
        stdout=subprocess.PIPE,
        text=True,
    ) as proc:
        try:
            assert proc.stdout is not None
            assert proc.stdout.readline().strip() == "locked"
            yield path
        finally:
            proc.kill()


def test_a_handle_on_a_locked_ready_database_waits_for_the_lock(
    locked_db: Path,
) -> None:
    """R2-1 (was: refused after the 1 s probe with ``database is locked``): a
    current schema needs no write, so opening is as fail-open as a read, and
    SQLite's own wait applies."""
    started = time.monotonic()
    handle = LicenseDatabase(str(locked_db))
    assert time.monotonic() - started >= HOLD / 2  # it did wait
    assert handle.get_metadata()["license_list_version"]


def test_a_handle_that_must_write_to_a_locked_database_is_still_refused(
    tmp_path: Path,
) -> None:
    """Writing into a file that cannot be judged is not done: an older
    schema of a database somebody holds locked is refused, not written."""
    path = make_ready_file_db(tmp_path / "licenses.db")
    with sqlite3.connect(path) as conn:
        conn.execute("DROP INDEX idx_licenses_name")  # an older schema
    holder = sqlite3.connect(path, isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(DatabaseNotReadyError, match="database is locked"):
            LicenseDatabase(str(path))
    finally:
        holder.close()


@posix_only
def test_a_ready_database_by_vfs_uri_opens(tmp_path: Path) -> None:
    """R2-1 (was ``database: invalid``): a name only SQLite can resolve is
    not written to by a handle that finds the schema current."""
    path = make_ready_file_db(tmp_path / "licenses.db")
    handle = LicenseDatabase(f"{path.as_uri()}?mode=ro&vfs=unix")
    assert handle.get_metadata()["license_list_version"]


def test_a_failed_update_leaves_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R2-2 (was: ``typo.db`` made before the release was read, and
    ``resolve`` then said ``empty``)."""
    ship(monkeypatch, None)  # no packaged list: the update fails
    path = tmp_path / "typo.db"
    result = run("--db", str(path), "update", "--source", "packaged")
    assert result.exit_code == 1
    assert not path.exists()
    assert not path.with_name("typo.db-journal").exists()
    after = run("--db", str(path), "resolve", "MIT")
    assert after.stderr.startswith(f"ERROR: database: not found: {path}")


def test_an_update_into_a_missing_directory_fails_before_the_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is made, and the error is the one main gave (R3-2)."""
    ship(monkeypatch, release_bundle(VERSION))
    path = tmp_path / "nodir" / "licenses.db"
    result = run("--db", str(path), "update", "--source", "packaged")
    assert result.exit_code == 1
    assert result.stderr == (
        "ERROR: database: update failed: OperationalError: "
        "unable to open database file\n"
    )
    assert not path.parent.exists()


@posix_only
def test_a_dangling_symlink_is_not_made_at_open(tmp_path: Path) -> None:
    """R2-3 (was: the target made at open)."""
    target = tmp_path / "target.db"
    link = tmp_path / "link.db"
    link.symlink_to(target)
    handle = LicenseDatabase(str(link))
    assert not target.exists()
    with pytest.raises(DatabaseNotReadyError):
        handle.get_metadata()
    create_database(link)  # the first write makes it, through the link
    assert target.exists()
