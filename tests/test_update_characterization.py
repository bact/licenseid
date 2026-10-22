# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Characterization tests for the ``update`` store path: what a small
synthetic release becomes in the database. They pin today's behaviour
(quirks included) so that a refactor of ``database.py`` changes none of it
by accident."""
# pylint: disable=missing-function-docstring

import contextlib
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from release_fakes import tarball
from test_database_update import _serve

from licenseid.database import LicenseDatabase
from licenseid.errors import LicenseIdError

_ROOT = "license-list-data-9.99"
_TEXT = "Permission is hereby granted, free of charge, to any person."
_XML = '<?xml version="1.0"?><SPDXLicenseCollection><license/></SPDXLicenseCollection>'


def _lic(license_id: str, deprecated: bool = False) -> dict[str, object]:
    return {
        "licenseId": license_id,
        "name": f"{license_id} name",
        "isOsiApproved": False,
        "isFsfLibre": False,
        "isDeprecatedLicenseId": deprecated,
    }


def _exc(exc_id: str, name: str, deprecated: bool = False) -> dict[str, object]:
    return {
        "licenseExceptionId": exc_id,
        "name": name,
        "isDeprecatedLicenseId": deprecated,
    }


_OPEN: list[sqlite3.Connection] = []


@pytest.fixture(autouse=True)
def _close_connections() -> Iterator[None]:
    """Close the connections ``_update`` hands out: an open handle blocks the
    removal of the temporary directory on Windows."""
    yield
    while _OPEN:
        _OPEN.pop().close()


def _update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    licenses: list[dict[str, object]],
    files: dict[str, bytes] | None = None,
    release_date: str | None = "2031-02-03",
) -> sqlite3.Connection:
    """Build a database from a synthetic release; return a connection to it."""
    listing: dict[str, object] = {
        "licenseListVersion": "9.99",
        "licenses": licenses,
    }
    if release_date is not None:
        listing["releaseDate"] = release_date
    members = {
        f"{_ROOT}/json/licenses.json": json.dumps(listing).encode(),
        f"{_ROOT}/json/exceptions.json": b'{"exceptions": []}',
    }
    members.update({f"{_ROOT}/{k}": v for k, v in (files or {}).items()})
    _serve(monkeypatch, tarball(members))
    path = tmp_path / "licenses.db"
    assert LicenseDatabase(str(path)).update_from_remote()
    conn = sqlite3.connect(path)
    _OPEN.append(conn)
    return conn


def _rows(conn: sqlite3.Connection, sql: str) -> list[tuple[object, ...]]:
    return conn.execute(sql).fetchall()


def test_non_deprecated_license_without_text_is_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # BUG: dropped silently; it should probably warn.
    conn = _update(
        tmp_path,
        monkeypatch,
        [_lic("A-1"), _lic("B-1")],
        {"text/A-1.txt": _TEXT.encode()},
    )
    assert _rows(conn, "SELECT license_id FROM licenses") == [("A-1",)]
    assert _rows(conn, "SELECT license_id FROM license_index") == [("A-1",)]


def test_deprecated_license_without_text_keeps_a_metadata_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = _update(
        tmp_path,
        monkeypatch,
        [_lic("GPL-2.0-or-later"), _lic("GPL-2.0+", True), _lic("Old-1", True)],
        {"text/GPL-2.0-or-later.txt": _TEXT.encode()},
    )
    rows = _rows(
        conn,
        "SELECT license_id, name, xml_template, is_spdx, is_osi_approved, "
        "is_fsf_libre, is_high_usage, is_deprecated, superseded_by, pop_score, "
        "word_count, norm_license_id, norm_name FROM licenses "
        "WHERE is_deprecated ORDER BY license_id",
    )
    assert rows == [
        ("GPL-2.0+", "GPL-2.0+ name", None, 1, 0, 0, 0, 1, "GPL-2.0-or-later",
         1, 0, "gpl 2 0", "gpl 2 0 name"),
        ("Old-1", "Old-1 name", None, 1, 0, 0, 0, 1, None,
         1, 0, "old 1", "old 1 name"),
    ]  # fmt: skip
    assert _rows(conn, "SELECT license_id FROM license_index") == [
        ("GPL-2.0-or-later",)
    ]


def test_crlf_text_is_read_with_lf_line_endings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Text-mode reading turns CRLF into LF; a reader of bytes must match.
    crlf = b"Permission is hereby\r\ngranted, free of\r\ncharge to any person."
    conn = _update(tmp_path, monkeypatch, [_lic("A-1")], {"text/A-1.txt": crlf})
    assert _rows(conn, "SELECT search_text FROM license_index") == [
        ("permission is hereby granted free of charge to any person",)
    ]
    assert _rows(conn, "SELECT word_count FROM licenses") == [(10,)]


def test_release_date_of_the_tarball_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The fake version lookup says 2030-01-01; licenses.json says 2031-02-03.
    conn = _update(tmp_path, monkeypatch, [_lic("A-1")])
    meta = dict(_rows(conn, "SELECT key, value FROM db_metadata"))  # type: ignore
    assert meta["release_date"] == "2031-02-03"


def test_release_date_falls_back_to_the_version_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = _update(tmp_path, monkeypatch, [_lic("A-1")], release_date=None)
    meta = dict(_rows(conn, "SELECT key, value FROM db_metadata"))  # type: ignore
    assert meta["release_date"] == "2030-01-01"


def test_xml_template_is_null_even_when_the_xml_file_is_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Deliberate change: nothing reads the license-list-XML, so it is no
    # longer stored (it was 6.6 MB of a 24.6 MB database).
    conn = _update(
        tmp_path,
        monkeypatch,
        [_lic("A-1"), _lic("B-1")],
        {
            "text/A-1.txt": _TEXT.encode(),
            "text/B-1.txt": _TEXT.encode(),
            "license-list-XML/A-1.xml": _XML.encode(),
        },
    )
    assert _rows(conn, "SELECT license_id, xml_template FROM licenses ORDER BY 1") == [
        ("A-1", None),
        ("B-1", None),
    ]


def test_a_tarball_without_licenselistversion_is_unusable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Before, such an update stored a NULL version (and so was never skipped).
    listing = json.dumps({"licenses": [_lic("A-1")]}).encode()
    _serve(monkeypatch, tarball({f"{_ROOT}/json/licenses.json": listing}))
    path = tmp_path / "licenses.db"
    with pytest.raises(
        LicenseIdError,
        match=r"^spdx-data-v9\.99\.tar\.gz: download unusable: ReadError: "
        r"licenseListVersion is missing or invalid$",
    ):
        LicenseDatabase(str(path)).update_from_remote()


def test_update_vacuums_the_xml_of_an_older_database_away(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "licenses.db"
    db = LicenseDatabase(str(path))
    big = "x" * 2_000_000
    with db._connection(write=True) as conn:  # pylint: disable=protected-access
        conn.execute(
            "INSERT INTO licenses (license_id, name, xml_template, is_spdx) "
            "VALUES ('Old-1', 'Old', ?, 1)",
            (big,),
        )
    before = path.stat().st_size
    assert before > 2_000_000
    _serve(
        monkeypatch,
        tarball(
            {
                f"{_ROOT}/json/licenses.json": json.dumps(
                    {"licenseListVersion": "9.99", "licenses": [_lic("A-1")]}
                ).encode(),
                f"{_ROOT}/text/A-1.txt": _TEXT.encode(),
            }
        ),
    )
    assert db.update_from_remote()
    assert path.stat().st_size < before // 10
    with sqlite3.connect(path) as conn:
        assert _rows(conn, "SELECT license_id, xml_template FROM licenses") == [
            ("A-1", None)
        ]
        assert _rows(conn, "PRAGMA freelist_count") == [(0,)]


def test_exceptions_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exceptions = [
        _exc("Exc-1.0", "Some Exception"),
        _exc("Exc-0.9", "some exception", True),
        _exc("Gone-1", "No Successor", True),
    ]
    conn = _update(
        tmp_path,
        monkeypatch,
        [_lic("A-1")],
        {"json/exceptions.json": json.dumps({"exceptions": exceptions}).encode()},
    )
    assert _rows(
        conn,
        "SELECT exception_id, name, is_deprecated, superseded_by "
        "FROM exceptions ORDER BY exception_id",
    ) == [
        ("Exc-0.9", "some exception", 1, "Exc-1.0"),
        ("Exc-1.0", "Some Exception", 0, None),
        ("Gone-1", "No Successor", 1, None),
    ]


def test_metadata_keys_after_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = _update(tmp_path, monkeypatch, [_lic("A-1")])
    meta = dict(_rows(conn, "SELECT key, value FROM db_metadata"))  # type: ignore
    assert meta["license_list_version"] == "9.99"
    assert meta["normalization_version"]
    assert {
        "release_date",
        "license_list_version",
        "normalization_version",
        "last_check_datetime",
        "last_update_datetime",
    } <= set(meta)


def test_a_failed_insert_rolls_back_and_names_the_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "licenses.db"
    LicenseDatabase(str(path))  # creates the schema
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.execute(
            "CREATE TRIGGER no_exceptions BEFORE INSERT ON exceptions "
            "BEGIN SELECT RAISE(ABORT, 'boom'); END"
        )
    with pytest.raises(LicenseIdError, match=r"^database: update failed: boom"):
        _update(
            tmp_path,
            monkeypatch,
            [_lic("A-1")],
            {
                "text/A-1.txt": _TEXT.encode(),
                "json/exceptions.json": json.dumps(
                    {"exceptions": [_exc("E-1", "e")]}
                ).encode(),
            },
        )
    with contextlib.closing(sqlite3.connect(path)) as conn:
        assert _rows(conn, "SELECT license_id FROM licenses") == []


def test_a_failed_vacuum_is_a_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    @contextlib.contextmanager
    def failing(write: bool = False) -> Iterator[mock.Mock]:  # pylint: disable=W0613
        conn = mock.Mock(spec=sqlite3.Connection)
        conn.execute.side_effect = sqlite3.OperationalError("database is locked")
        yield conn

    db = LicenseDatabase(str(tmp_path / "licenses.db"))
    monkeypatch.setattr(db, "_connection", failing)
    db._compact()  # pylint: disable=protected-access
    assert capsys.readouterr().err == (
        "WARNING: database: compact failed: OperationalError: database is locked\n"
    )
