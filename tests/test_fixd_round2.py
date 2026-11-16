# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Where the database handle writes.

The handle refused a database that another process held locked (and a
read-only ``vfs=`` URI), because it judged the file at every open; a failed
``update`` left the mistyped file behind; a dangling symlink was created.
"""

# pylint: disable=missing-function-docstring,redefined-outer-name

import sqlite3
import subprocess
import sys
import threading
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
from timing import slack

from licenseid import DatabaseNotReadyError, LicenseDatabase

_PROBE_WAIT = 1.0  # dbcheck._BUSY_WAIT: the old refusal came after this

_HOLDER = """
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1], isolation_level=None)
conn.execute("BEGIN EXCLUSIVE")
print("locked", flush=True)
sys.stdin.readline()
"""


@pytest.fixture
def locked_db(tmp_path: Path) -> Iterator[tuple[Path, subprocess.Popen[str]]]:
    """A ready database that another process holds locked until it is told
    (a line on its standard input) to let go."""
    path = make_ready_file_db(tmp_path / "licenses.db")
    with subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    ) as proc:
        try:
            assert proc.stdout is not None
            assert proc.stdout.readline().strip() == "locked"
            yield path, proc
        finally:
            proc.kill()


def test_a_handle_on_a_locked_ready_database_waits_for_the_lock(
    locked_db: tuple[Path, subprocess.Popen[str]],
) -> None:
    """Was: refused after the 1 s probe with ``database is locked``; now a
    current schema needs no write, so opening is as fail-open as a read, and
    SQLite's own wait applies. Event-driven: no wall-clock bound."""
    path, proc = locked_db
    started = threading.Event()
    released = threading.Event()
    outcome: dict[str, object] = {}

    def open_it() -> None:
        started.set()
        try:
            outcome["handle"] = LicenseDatabase(str(path))
            outcome["after_release"] = released.is_set()
        except Exception as error:  # pylint: disable=broad-exception-caught
            outcome["error"] = error

    worker = threading.Thread(target=open_it)
    worker.start()
    try:
        assert started.wait(slack(10))
        worker.join(timeout=_PROBE_WAIT + 0.5)
        # still waiting for the lock after the probe's own 1 s wait ran out
        assert worker.is_alive()
        released.set()
        assert proc.stdin is not None
        proc.stdin.write("\n")
        proc.stdin.flush()
        worker.join(slack(10))
        assert not worker.is_alive()
    finally:
        proc.kill()
        worker.join(slack(10))
    assert "error" not in outcome
    assert outcome["after_release"] is True
    handle = outcome["handle"]
    assert isinstance(handle, LicenseDatabase)
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
    """Was: ``database: invalid``; now a name only SQLite can resolve is
    not written to by a handle that finds the schema current."""
    path = make_ready_file_db(tmp_path / "licenses.db")
    handle = LicenseDatabase(f"{path.as_uri()}?mode=ro&vfs=unix")
    assert handle.get_metadata()["license_list_version"]


def test_a_failed_update_leaves_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Was: ``typo.db`` made before the release was read, and
    ``resolve`` then said ``empty``."""
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
    """Nothing is made, and the error is the one main gave."""
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
    """Was: the target made at open."""
    target = tmp_path / "target.db"
    link = tmp_path / "link.db"
    link.symlink_to(target)
    handle = LicenseDatabase(str(link))
    assert not target.exists()
    with pytest.raises(DatabaseNotReadyError):
        handle.get_metadata()
    create_database(link)  # the first write makes it, through the link
    assert target.exists()
