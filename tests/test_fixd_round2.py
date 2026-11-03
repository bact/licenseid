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
from db_variants import make_ready_file_db
from release_fakes import ship

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
    proc = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(path), str(HOLD)],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "locked"
        yield path
    finally:
        proc.kill()
        proc.wait()
        if proc.stdout:
            proc.stdout.close()


def test_pin_a_handle_on_a_locked_ready_database_is_refused(locked_db: Path) -> None:
    started = time.monotonic()
    with pytest.raises(DatabaseNotReadyError, match="database is locked"):  # BUG
        LicenseDatabase(str(locked_db))
    assert time.monotonic() - started < HOLD  # refused, not waited for


@posix_only
def test_pin_a_ready_database_by_vfs_uri_is_refused(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "licenses.db")
    with pytest.raises(DatabaseNotReadyError, match="^database: invalid: "):  # BUG
        LicenseDatabase(f"{path.as_uri()}?mode=ro&vfs=unix")


def test_pin_a_failed_update_leaves_the_mistyped_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ship(monkeypatch, None)  # no packaged list: the update fails
    path = tmp_path / "typo.db"
    result = run("--db", str(path), "update", "--source", "packaged")
    assert result.exit_code == 1
    assert path.exists()  # BUG: made before the release was read


@posix_only
def test_pin_a_dangling_symlink_is_made_at_open(tmp_path: Path) -> None:
    target = tmp_path / "target.db"
    link = tmp_path / "link.db"
    link.symlink_to(target)
    LicenseDatabase(str(link))
    assert target.exists()  # BUG: opening made the target
