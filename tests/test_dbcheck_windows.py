# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""How ``check_database_ready`` builds and reads URIs for Windows paths.

Checked as strings (``PureWindowsPath``), so they run on every OS; the last
test opens a real database and is the one that catches the bug on Windows.
"""

# pylint: disable=protected-access,missing-function-docstring

import os
import sqlite3
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import quote

import pytest
from db_variants import make_ready_file_db

from licenseid import AggregatedLicenseMatcher, dbcheck
from licenseid.dbcheck import (
    _drop_drive_slash,
    _path_uri_part,
    _plain_path_uri,
    _read_only_uri,
    check_database_ready,
)
from licenseid.errors import DatabaseNotReadyError

# Windows paths, checked as strings so they run on every OS


@pytest.mark.parametrize(
    ("path", "uri"),
    [
        (r"C:\Users\x\licenses.db", "file:///C:/Users/x/licenses.db?mode=ro"),
        (r"C:\Users\a b\l.db", "file:///C:/Users/a%20b/l.db?mode=ro"),
        (r"\\invalid.\share\l.db", "file:////invalid./share/l.db?mode=ro"),
    ],
)
def test_a_windows_path_has_an_empty_authority(path: str, uri: str) -> None:
    assert _plain_path_uri(PureWindowsPath(path)) == uri
    assert uri.startswith("file:///")
    if path.startswith("\\\\") and sys.platform == "win32":
        return  # opening a UNC path on Windows looks the host up on the network
    # "unable to open", not "invalid uri authority": the URI parsed.
    with pytest.raises(sqlite3.OperationalError) as info:
        sqlite3.connect(uri, uri=True)
    assert "invalid uri authority" not in str(info.value)


def test_the_old_windows_uri_was_refused_by_sqlite() -> None:
    """Pins the bug: the drive letter was read as the authority."""
    old = "file://" + quote(os.fsencode(str(PureWindowsPath(r"C:\x\l.db"))))
    with pytest.raises(sqlite3.OperationalError, match="invalid uri authority"):
        sqlite3.connect(f"{old}?mode=ro", uri=True)


def test_a_posix_double_slash_path_keeps_an_empty_authority() -> None:
    posix = os.fsencode(PurePosixPath("//x/y.db").as_posix())
    assert _path_uri_part(posix) == b"//x/y.db"


@pytest.mark.parametrize(
    ("path", "kept"),
    [
        ("/C:", "C:"),
        ("xC:/a", "xC:/a"),
        ("/C:/a/b.db", "C:/a/b.db"),
        ("/c:/a", "c:/a"),
        ("/a/b.db", "/a/b.db"),
        ("/C", "/C"),
        ("/\u00e9:/x", "/\u00e9:/x"),
    ],
)
def test_the_slash_before_a_drive_is_dropped(path: str, kept: str) -> None:
    assert _drop_drive_slash(path) == kept


def test_the_windows_gate_follows_the_os() -> None:
    assert dbcheck._IS_WINDOWS is (os.name == "nt")


def test_a_file_uri_with_a_byte_windows_cannot_decode_names_no_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows decodes names as UTF-8, so %FF is no file name there: the guard
    says "cannot tell", not a traceback."""

    def refuse(_name: bytes) -> str:
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(os, "fsdecode", refuse)
    assert dbcheck._uri_file_path("file:///C:/t/lic%FF.db") is None


def test_a_file_uri_drive_path_keeps_its_drive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dbcheck, "_IS_WINDOWS", True)
    path = dbcheck._uri_file_path("file:///C:/a/b.db")
    assert path is not None
    assert PureWindowsPath(path).drive == "C:"
    monkeypatch.setattr(dbcheck, "_IS_WINDOWS", False)
    assert dbcheck._uri_file_path("file:///C:/a/b.db") == "/C:/a/b.db"


def test_a_ready_database_opens_and_matches(tmp_path: Path) -> None:
    """The real-OS check: on Windows this failed with 'unreadable'."""
    path = make_ready_file_db(tmp_path / "real.db")
    check_database_ready(str(path))
    check_database_ready(path.as_uri())
    uri_matcher = AggregatedLicenseMatcher(db_path=path.as_uri())
    assert uri_matcher.match(license_id="MIT")
    with pytest.raises(DatabaseNotReadyError, match="database: not found: "):
        check_database_ready((tmp_path / "none.db").as_uri())
    assert _read_only_uri(str(path)).startswith("file:///")
    matcher = AggregatedLicenseMatcher(db_path=str(path))
    assert matcher.match(license_id="MIT")
