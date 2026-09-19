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
from conftest import assert_cached_tarball_removed

from licenseid.database import NORMALIZATION_VERSION, LicenseDatabase


@pytest.fixture()
def db(tmp_path: Path) -> Generator[LicenseDatabase, None, None]:
    db_path = str(tmp_path / f"test_{uuid.uuid4().hex[:8]}.db")
    yield LicenseDatabase(db_path)


def _assert_closed(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        conn.execute("SELECT 1")


def test_connection_closes_after_successful_query(db: LicenseDatabase) -> None:
    """A query method must close its connection, not just commit it."""
    opened: list[sqlite3.Connection] = []
    real_connect = db._connect

    def tracking_connect() -> sqlite3.Connection:
        conn = real_connect()
        opened.append(conn)
        return conn

    db._connect = tracking_connect  # type: ignore[method-assign]

    db.get_metadata()

    assert opened
    for conn in opened:
        _assert_closed(conn)


def test_connection_closes_even_when_the_query_raises(db: LicenseDatabase) -> None:
    """The connection must be closed on the exception path too, not leaked."""
    with pytest.raises(RuntimeError, match="boom"), db._connection() as conn:
        raise RuntimeError("boom")

    _assert_closed(conn)


def test_connection_commits_before_closing(db: LicenseDatabase) -> None:
    """Data written inside the context manager must survive past its exit."""
    with db._connection() as conn:
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
    db: LicenseDatabase, tmp_path: Path, corrupt: bytes | None
) -> None:
    """A corrupt/truncated cached tarball fails once with a clear message and
    is deleted so the next run re-downloads it instead of failing forever."""
    tar_path = tmp_path / "spdx-data-v9.99.tar.gz"
    if corrupt is None:
        _write_tarball(tar_path, truncate_to=60)
    else:
        tar_path.write_bytes(corrupt)

    assert_cached_tarball_removed(db, tar_path)


def test_older_normalization_version_warns_on_stderr(
    db: LicenseDatabase, capsys: pytest.CaptureFixture[str]
) -> None:
    with db._connection() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO db_metadata (key, value) VALUES (?, ?)",
            [("license_list_version", "9.99"), ("normalization_version", "1")],
        )
        conn.commit()
    capsys.readouterr()

    LicenseDatabase(str(db.db_path))

    captured = capsys.readouterr()
    assert captured.err == (
        f"WARNING: database: normalization v1 outdated: "
        f"current v{NORMALIZATION_VERSION}; run 'licenseid update --force'\n"
    )
    assert captured.out == ""


def test_current_normalization_version_does_not_warn(
    db: LicenseDatabase, capsys: pytest.CaptureFixture[str]
) -> None:
    with db._connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO db_metadata (key, value) VALUES (?, ?)",
            ("license_list_version", "9.99"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO db_metadata (key, value) VALUES (?, ?)",
            ("normalization_version", NORMALIZATION_VERSION),
        )
        conn.commit()
    capsys.readouterr()

    LicenseDatabase(str(db.db_path))

    assert capsys.readouterr().err == ""
