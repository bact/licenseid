# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The pages of the List (``seeAlso``) in the database: the rows ``update``
builds, the ``license_urls`` table, and the reads ``get_ids_by_url`` keeps.
``tests/test_listindex.py`` holds the index in memory to the same answers."""
# pylint: disable=missing-function-docstring,protected-access

import contextlib
import sqlite3
from datetime import datetime, tzinfo
from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import stamp_rebuild, writer
from list_entries import exc_entry, lic_entry
from packaged_list import database_of, synthetic_bundle

from licenseid import database as database_module
from licenseid.database import LicenseDatabase
from licenseid.dbschema import SCHEMA_OBJECTS
from licenseid.listlookup import ListedUrl, UrlRow, index_urls
from licenseid.listrules import listed_urls
from licenseid.records import BUILD_VERSION, Records, build_records
from licenseid.spdxdata import SpdxData
from licenseid.types import SpdxExceptionEntry, SpdxLicenseEntry

MIT = "https://opensource.org/license/mit/"
APACHE = "https://www.apache.org/licenses/LICENSE-2.0"
CLASSPATH = "https://www.gnu.org/software/classpath/license.html"
LICENSES = (
    lic_entry("MIT", "MIT License", see_also=[MIT]),
    lic_entry("Apache-2.0", "Apache License 2.0", see_also=[APACHE, APACHE + ".txt"]),
    lic_entry("NoText-1.0", "No Text License", see_also=["https://example.org/nt"]),
)
TEXTS = {"MIT": "Text of MIT.", "Apache-2.0": "Text of Apache-2.0."}
EXCEPTIONS = (
    exc_entry(
        "Classpath-exception-2.0", "Classpath exception 2.0", see_also=[CLASSPATH]
    ),
)
# The kept licences' pages in list order, then the exceptions'; NoText-1.0
# has no text and is in use, so it is not kept, and neither are its pages.
ROWS = [
    ("MIT", False, MIT),
    ("Apache-2.0", False, APACHE),
    ("Apache-2.0", False, APACHE + ".txt"),
    ("Classpath-exception-2.0", True, CLASSPATH),
]


def lic(owner: str) -> ListedUrl:
    return {"id": owner, "is_exception": False}


def exc(owner: str) -> ListedUrl:
    return {"id": owner, "is_exception": True}


def no_suffix(url: str) -> str | None:
    """A key that reads a page with and without ``.txt`` as one."""
    return url.lower().removesuffix(".txt")


def host(url: str) -> str | None:
    return url.split("/")[2]


@pytest.fixture(name="db")
def _db(tmp_path: Path) -> LicenseDatabase:
    raw = synthetic_bundle(LICENSES, TEXTS, EXCEPTIONS)
    return database_of(raw, tmp_path / "licenses.db")


def test_the_build_and_the_schema_carry_the_pages() -> None:
    """Build 4 adds the table: a database of build 3 is rebuilt by update
    (``tests/test_license_urls_build3.py``)."""
    assert BUILD_VERSION == "4"
    assert "license_urls" in SCHEMA_OBJECTS


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        (lic_entry("A"), []),
        (lic_entry("A", see_also="https://a.example/"), []),
        (lic_entry("A", see_also={"url": "https://a.example/"}), []),
        (
            lic_entry("A", see_also=[1, None, ["x"], "https://a/", "https://a/"]),
            ["https://a/", "https://a/"],  # as written: the index drops repeats
        ),
        (exc_entry("E", "E", see_also=["https://e/", b"x"]), ["https://e/"]),
    ],
    ids=["missing", "string", "object", "items", "exception"],
)
def test_the_pages_of_an_entry(
    entry: SpdxLicenseEntry | SpdxExceptionEntry, expected: list[str]
) -> None:
    assert listed_urls(entry) == expected


def _key(url: str) -> str | None:
    return None if url == "skip" else url.lower()


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([("A", 0, "u"), ("A", 0, "U"), ("A", False, "u")], {"u": [lic("A")]}),
        ([("A", 0, "u"), ("A", 1, "u")], {"u": [lic("A"), exc("A")]}),
        ([("B", 0, "u"), ("A", 0, "u")], {"u": [lic("B"), lic("A")]}),
        ([(b"A", 0, "u"), (None, 0, "u"), (5, 0, "u")], {}),
        ([("A", 0, None), ("A", 0, b"u"), ("A", 0, 5)], {}),
        ([("A", 0, "skip"), ("A", 0, "v")], {"v": [lic("A")]}),
    ],
    ids=["repeat", "licence-and-exception", "row-order", "owner", "url", "no-key"],
)
def test_the_owners_by_key(
    rows: list[UrlRow], expected: dict[str, list[ListedUrl]]
) -> None:
    assert index_urls(rows, _key) == expected


def test_the_rows_update_builds() -> None:
    data = SpdxData("9.99", None, LICENSES, EXCEPTIONS, TEXTS)
    assert build_records(data, {}).urls == ROWS


def test_the_database_holds_the_pages(db: LicenseDatabase) -> None:
    assert db.get_ids_by_url(no_suffix) == {
        MIT: [lic("MIT")],
        APACHE.lower(): [lic("Apache-2.0")],
        CLASSPATH: [exc("Classpath-exception-2.0")],
    }


def test_the_index_follows_the_key(db: LicenseDatabase) -> None:
    first = db.get_ids_by_url(no_suffix)
    assert db.get_ids_by_url(no_suffix) is first  # built once
    assert db.get_ids_by_url(host)["www.apache.org"] == [lic("Apache-2.0")]
    assert db.get_ids_by_url(no_suffix) is not first  # one key kept
    assert db.get_ids_by_url(no_suffix) == first


def test_the_table_is_read_once_per_rebuild(
    db: LicenseDatabase, opened: list[sqlite3.Connection]
) -> None:
    """Outside a block each lookup checks the stamp on a connection of its
    own; only the first reads the table, another key reads the same rows."""
    opened.clear()
    db.get_ids_by_url(no_suffix)
    assert len(opened) == 2  # the stamp, the table
    opened.clear()
    db.get_ids_by_url(host)
    db.get_ids_by_url(no_suffix)
    assert len(opened) == 2  # the stamp, twice
    opened.clear()
    with db.reading():
        db.get_ids_by_url(host)
    assert len(opened) == 1


class _Same(datetime):
    """``datetime`` whose ``now`` is the stamp a database already has."""

    stamp = ""

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> "_Same":
        del tz  # the stamp has its own
        return cls.fromisoformat(cls.stamp)


def test_an_update_drops_the_pages_read(
    db: LicenseDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even when the rebuild keeps the stamp: the write clears the reads."""
    assert db.get_ids_by_url(no_suffix)
    _Same.stamp = db.get_metadata()["last_update_datetime"]
    monkeypatch.setattr(database_module, "datetime", _Same)
    db._write_db_records(Records([], [], [], [("X-1.0", False, "https://x/")]), None)
    assert db.get_metadata()["last_update_datetime"] == _Same.stamp
    assert db.get_ids_by_url(no_suffix) == {"https://x/": [lic("X-1.0")]}


@pytest.mark.parametrize("in_block", [True, False], ids=["next-match", "api-call"])
def test_a_rebuild_by_another_process_is_seen(
    db: LicenseDatabase, in_block: bool
) -> None:
    assert MIT in db.get_ids_by_url(no_suffix)
    with writer(db.db_path) as conn:
        conn.execute("DELETE FROM license_urls")
        conn.execute("INSERT INTO license_urls VALUES ('Zlib', 0, 'https://z/')")
        stamp_rebuild(conn, "2030-01-01T00:00:00")
    with db.reading() if in_block else contextlib.nullcontext():
        assert db.get_ids_by_url(no_suffix) == {"https://z/": [lic("Zlib")]}


def test_a_hand_filled_row_that_is_no_text_is_skipped(db: LicenseDatabase) -> None:
    with writer(db.db_path) as conn:
        conn.execute("DELETE FROM license_urls")
        conn.executemany(
            "INSERT INTO license_urls VALUES (?, ?, ?)",
            [(b"MIT", 0, "https://a/"), ("MIT", 0, b"https://a/"), ("ISC", 1, MIT)],
        )
        stamp_rebuild(conn, "2030-01-01T00:00:00")
    assert db.get_ids_by_url(no_suffix) == {MIT: [exc("ISC")]}
