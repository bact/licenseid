# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for LicenseDatabase._connection()'s close-on-exit guarantee."""
# pylint: disable=redefined-outer-name,missing-function-docstring,protected-access

import io
import sqlite3
import tarfile
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from conftest import assert_cached_tarball_removed, is_closed

from licenseid.database import NORMALIZATION_VERSION, LicenseDatabase
from licenseid.errors import LicenseIdError
from licenseid.records import BUILD_VERSION


@pytest.fixture()
def db(tmp_path: Path) -> Generator[LicenseDatabase, None, None]:
    db_path = str(tmp_path / f"test_{uuid.uuid4().hex[:8]}.db")
    yield LicenseDatabase(db_path)


def test_connection_closes_after_successful_query(
    db: LicenseDatabase, opened: list[sqlite3.Connection]
) -> None:
    """A query method must close its connection, not just commit it."""
    db.get_metadata()

    assert opened and all(is_closed(conn) for conn in opened)


def test_connection_closes_even_when_the_query_raises(db: LicenseDatabase) -> None:
    """The connection must be closed on the exception path too, not leaked."""
    with pytest.raises(RuntimeError, match="boom"), db._connection() as conn:
        raise RuntimeError("boom")

    assert is_closed(conn)


def test_connection_commits_before_closing(db: LicenseDatabase) -> None:
    """Data written inside the context manager must survive past its exit."""
    with db._connection(write=True) as conn:
        conn.execute(
            "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
            ("test_key", "test_value"),
        )

    with db._connection() as conn:
        row = conn.execute(
            "SELECT value FROM db_metadata WHERE key = ?", ("test_key",)
        ).fetchone()
    assert row == ("test_value",)


def _write_tarball(path: Path, truncate_to: int | None = None) -> None:
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w:gz") as tar:
        data = b"x" * 5000
        info = tarfile.TarInfo("root/json/licenses.json")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    blob = payload.getvalue()
    path.write_bytes(blob if truncate_to is None else blob[:truncate_to])


@pytest.mark.parametrize(
    "corrupt",
    [b"not a tarball at all", None],
    ids=["not_gzip", "truncated_gzip"],
)
def test_corrupt_cached_tarball_is_removed(
    db: LicenseDatabase,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    corrupt: bytes | None,
) -> None:
    """A corrupt/truncated cached tarball fails once with a clear message and
    is deleted so the next run re-downloads it instead of failing forever."""
    tar_path = tmp_path / "spdx-data-v9.99.tar.gz"
    if corrupt is None:
        _write_tarball(tar_path, truncate_to=60)
    else:
        tar_path.write_bytes(corrupt)

    assert_cached_tarball_removed(db, tar_path, capsys)


def test_a_corrupt_tarball_another_process_holds_is_not_called_removed(
    db: LicenseDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows refuses to delete a file that is open elsewhere: the message
    must not say "removed" for a file that is still there."""
    tar_path = tmp_path / "spdx-data-v9.99.tar.gz"
    tar_path.write_bytes(b"not a tarball at all")

    def held(self: Path, missing_ok: bool = False) -> None:
        raise PermissionError(13, "in use")

    monkeypatch.setattr(Path, "unlink", held)
    with pytest.raises(LicenseIdError) as info:
        db.update_from_remote(version="9.99", source="upstream")
    assert str(info.value).startswith("spdx-data-v9.99.tar.gz: cache unusable: ")
    assert str(info.value).endswith("; remove it and run 'licenseid update' again")
    assert tar_path.exists()


CURRENT = {
    "normalization_version": NORMALIZATION_VERSION,
    "build_version": BUILD_VERSION,
}
NORM_OLD = (
    f"WARNING: database: normalization v1 outdated: current v{NORMALIZATION_VERSION}"
    "; run 'licenseid update'"
)
BUILD_OLD = (
    f"WARNING: database: build v1 outdated: current v{BUILD_VERSION}"
    "; run 'licenseid update'"
)


@pytest.mark.parametrize(
    ("stamps", "expected"),
    [
        (CURRENT, []),
        ({**CURRENT, "normalization_version": "1"}, [NORM_OLD]),
        ({**CURRENT, "build_version": "1"}, [BUILD_OLD]),
        ({}, [NORM_OLD, BUILD_OLD]),  # a database from before either stamp
        ({"normalization_version": "1", "build_version": "1"}, [NORM_OLD, BUILD_OLD]),
    ],
    ids=["current", "normalization", "build", "unstamped", "both"],
)
def test_older_build_rules_warn_on_stderr(
    db: LicenseDatabase,
    capsys: pytest.CaptureFixture[str],
    stamps: dict[str, str],
    expected: list[str],
) -> None:
    with db._connection(write=True) as conn:
        conn.execute(
            "DELETE FROM db_metadata"
            " WHERE key IN ('normalization_version', 'build_version')"
        )
        conn.executemany(
            "INSERT OR REPLACE INTO db_metadata (key, value) VALUES (?, ?)",
            [("license_list_version", "9.99"), *stamps.items()],
        )
        conn.commit()
    capsys.readouterr()

    LicenseDatabase(str(db.db_path))

    captured = capsys.readouterr()
    assert captured.err.splitlines() == expected
    assert captured.out == ""


def test_an_empty_database_has_no_build_rules_to_warn_about(
    db: LicenseDatabase, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    LicenseDatabase(str(db.db_path))
    assert capsys.readouterr().err == ""
