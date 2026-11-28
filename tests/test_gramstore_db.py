# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The postings ``update`` stores (build 8) and a lookup reads
(``database.gram_scores``): written in the transaction of the rows, used
only when they are those of the rows, else built in memory from the texts,
never written back. Units: ``test_gramstore``."""
# pylint: disable=missing-function-docstring,protected-access

import contextlib
import hashlib
import shutil
import sqlite3
import threading
from collections.abc import Callable, Generator, Iterable
from pathlib import Path
from types import MappingProxyType

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import writer
from list_entries import lic_entry
from packaged_list import database_of, synthetic_bundle
from texts_db import texts_database

from licenseid import gramstore
from licenseid.database import LicenseDatabase, gram_scores
from licenseid.errors import DatabaseNotReadyError, LicenseIdError
from licenseid.gramstore import (
    STAMP_KEY,
    STAMP_UPDATE_KEY,
    StoredPostings,
    build_index,
    read_texts,
)
from licenseid.spdxdata import SpdxData, to_bundle
from licenseid.textgrams import GramScore, input_grams, score_rows
from licenseid.warning import LicenseIdWarning

BODY = " ".join(f"clause{n} of the licence" for n in range(30))
TEXTS = {
    "A-1.0": f"{BODY} and an appendix of five more words",
    "B-1.0": f"you may not copy this {BODY}",
    "C-1.0": "MIT",  # no gram
    "D-1.0": "permission is hereby granted free of charge to any person",
    "J-1.0": "本ソフトウェアは無保証で提供されます。許諾書の条項に従う",
}
# Release 9.98, then another (9.99): A-1.0 has D-1.0's text, E-1.0 A-1.0's.
RAW = to_bundle(
    SpdxData(
        "9.98",
        None,
        tuple(lic_entry(key, f"Name {key}") for key in TEXTS),
        (),
        MappingProxyType(TEXTS),
    )
)
OTHER = synthetic_bundle(
    (lic_entry(key, f"Name {key}") for key in ("A-1.0", "E-1.0")),
    {"A-1.0": TEXTS["D-1.0"], "E-1.0": TEXTS["A-1.0"]},
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(path: Path) -> list[str]:
    """Each stored text, a fragment of one, and an input of no List word."""
    with contextlib.closing(sqlite3.connect(path)) as conn:
        texts = [
            text for (text,) in conn.execute("SELECT search_text FROM license_texts")
        ]
    return [*texts, " ".join(BODY.split()[40:90]), "nothing in here is a list word"]


def _references(
    path: Path, texts: list[str] | None = None
) -> list[tuple[GramScore, ...]]:
    """The tables of *texts* (default: :func:`_inputs`) from the index built
    from the file's texts, read apart from licenseid's connections."""
    with contextlib.closing(
        sqlite3.connect(path, uri=path.as_posix().startswith("file:"))
    ) as conn:
        index = build_index(read_texts(conn))
        tables = []
        for text in _inputs(path) if texts is None else texts:
            grams = input_grams(text)
            shared = index.shared(conn, grams)
            tables.append(score_rows(shared, len(grams), index.ids, index.sizes))
    return tables


def _tables(path: Path) -> list[tuple[GramScore, ...]]:
    database = LicenseDatabase(str(path), create=False)
    return [gram_scores(database, text).rows for text in _inputs(path)]


class Calls:
    """The calls of a function of ``gramstore`` while a test runs."""

    def __init__(self) -> None:
        self.count = 0


def _counted(monkeypatch: pytest.MonkeyPatch, name: str) -> Calls:
    seen = Calls()
    real = getattr(gramstore, name)

    def counting(*args: object) -> object:
        seen.count += 1
        return real(*args)

    monkeypatch.setattr(gramstore, name, counting)
    return seen


@pytest.fixture(name="builds")
def _builds(monkeypatch: pytest.MonkeyPatch) -> Calls:
    """The index built in memory."""
    return _counted(monkeypatch, "build_index")


@pytest.fixture(name="fresh", scope="module")
def _fresh(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return database_of(RAW, tmp_path_factory.mktemp("fresh") / "licenses.db").db_path


@pytest.fixture(name="built")
def _built(fresh: Path, tmp_path: Path) -> Path:
    path = tmp_path / "licenses.db"
    shutil.copyfile(fresh, path)
    return path


def _rows(path: Path, query: str) -> list[tuple[object, ...]]:
    with writer(path) as conn:
        return conn.execute(query).fetchall()


def test_update_stores_the_postings_and_their_stamp(built: Path) -> None:
    stamp = '{"gram":3,"grams":%d,"hash":"blake2b-64","texts":4,"tokens":1,"width":2}'
    (grams,) = _rows(built, "SELECT count(*) FROM text_postings")[0]
    meta = {row[0]: row[1] for row in _rows(built, "SELECT * FROM db_metadata")}
    assert meta[STAMP_KEY] == stamp % grams
    assert meta[STAMP_UPDATE_KEY] == meta["last_update_datetime"]
    assert _rows(built, "SELECT k, id FROM text_posting_ids") == [
        (0, "A-1.0"),
        (1, "B-1.0"),
        (2, "D-1.0"),
        (3, "J-1.0"),  # C-1.0 has no gram
    ]


def test_the_stored_postings_are_read_and_give_what_the_texts_give(
    built: Path, builds: Calls
) -> None:
    assert _tables(built) == _references(built)
    assert builds.count == 0
    assert _tables(built)[-1] == ()  # no List word: no row
    assert [row.license_id for row in _tables(built)[4]] == ["J-1.0"]


@pytest.mark.parametrize("fail_at", ["write_postings", "to_blob"])
def test_a_failed_write_leaves_the_file_as_it_was(
    built: Path, monkeypatch: pytest.MonkeyPatch, fail_at: str
) -> None:
    """The postings are written in the transaction of the rows: a failure
    after them, or among them, leaves the old file whole."""
    real = getattr(gramstore, fail_at)

    def fail(*args: object) -> object:
        real(*args)
        raise sqlite3.OperationalError("disk full")

    target = (
        "licenseid.database" if fail_at == "write_postings" else "licenseid.gramstore"
    )
    monkeypatch.setattr(f"{target}.{fail_at}", fail)
    before = _digest(built)
    with pytest.raises(LicenseIdError, match="^database: update failed: disk full"):
        database_of(OTHER, built)
    assert _digest(built) == before


STAMP = f"UPDATE db_metadata SET value = {{}} WHERE key = '{STAMP_KEY}'"
IDS = "UPDATE text_posting_ids SET {} WHERE k = 1"
DAMAGE: dict[str, str] = {
    "no-stamp": f"DELETE FROM db_metadata WHERE key = '{STAMP_KEY}'",
    "no-stamp-copy": f"DELETE FROM db_metadata WHERE key = '{STAMP_UPDATE_KEY}'",
    "rows-rebuilt-since": (
        "UPDATE db_metadata SET value = 'later' WHERE key = 'last_update_datetime'"
    ),
    "texts-changed-since": (
        "UPDATE license_texts SET search_text = 'permission is hereby granted"
        " to any person' WHERE license_id = 'A-1.0';"
        " UPDATE db_metadata SET value = 'later' WHERE key = 'last_update_datetime'"
    ),
    "copy-not-text": (
        f"UPDATE db_metadata SET value = x'31' WHERE key = '{STAMP_UPDATE_KEY}';"
        " UPDATE db_metadata SET value = x'31' WHERE key = 'last_update_datetime'"
    ),
    "gram-size": STAMP.format("replace(value, '\"gram\":3', '\"gram\":4')"),
    "hash-name": STAMP.format("replace(value, 'blake2b-64', 'md5')"),
    "token-rule": STAMP.format("replace(value, '\"tokens\":1', '\"tokens\":2')"),
    "width": STAMP.format("replace(value, '\"width\":2', '\"width\":4')"),
    "texts": STAMP.format("replace(value, '\"texts\":4', '\"texts\":5')"),
    "texts-true": STAMP.format("replace(value, '\"texts\":4', '\"texts\":true')"),
    "grams": STAMP.format("replace(value, '\"grams\":', '\"grams\":1')"),
    "extra-key": STAMP.format("replace(value, '{', '{\"more\":1,')"),
    "not-json": STAMP.format("'not json'"),
    "json-list": STAMP.format("'[3]'"),
    "too-deep": STAMP.format("printf('%.100000c', '[')"),
    "stamp-blob": STAMP.format("x'7b7d'"),
    "blob-short": "UPDATE text_postings SET ids = substr(ids, 1, length(ids) - 1)",
    "blob-number-out-of-range": "UPDATE text_postings SET ids = x'0400'",
    # || joins as text: the cast gives the bytes back.
    "blob-number-twice": "UPDATE text_postings SET ids = CAST(ids || ids AS BLOB)",
    "blob-text": "UPDATE text_postings SET ids = hex(ids)",
    "blob-null": "UPDATE text_postings SET ids = NULL",
    "postings-emptied": "DELETE FROM text_postings",
    "one-posting-gone": (
        "DELETE FROM text_postings WHERE h = (SELECT min(h) FROM text_postings)"
    ),
    "ids-emptied": "DELETE FROM text_posting_ids",
    "ids-gap": "UPDATE text_posting_ids SET k = 9 WHERE k = 3",
    "size-null": IDS.format("size = NULL"),
    "size-text": IDS.format("size = 'nine'"),  # '9' would be stored as 9
    "size-zero": IDS.format("size = 0"),
    "id-null": IDS.format("id = NULL"),
}


@pytest.mark.parametrize("name", sorted(DAMAGE))
def test_postings_that_are_not_those_of_the_rows_are_built_in_memory(
    built: Path, name: str, builds: Calls, connects: list[bool]
) -> None:
    """Each table equals the index built from the file's texts; nothing is
    written, and no write connection is opened."""
    original = _tables(built)
    with writer(built) as conn:
        conn.executescript(DAMAGE[name])
    before = _digest(built)
    connects.clear()
    builds.count = 0
    found = _tables(built)
    assert builds.count == 1
    with contextlib.closing(sqlite3.connect(built)) as conn:
        loaded = gramstore.load(conn)
    # A blob is checked as it is read; everything else when loaded.
    assert isinstance(loaded, StoredPostings) is name.startswith("blob-")
    assert found == _references(built)
    if "since" not in name:
        assert found == original
    assert _digest(built) == before
    assert not any(connects), "a lookup opened a connection to write"


def test_a_blob_found_damaged_switches_the_database_for_good(
    built: Path, builds: Calls
) -> None:
    """The stored index is loaded; the first blob read fails it; that call
    and every later one read the index built in memory, built once."""
    database = LicenseDatabase(str(built), create=False)
    assert gram_scores(database, "nothing in here is a list word").rows == ()
    with writer(built) as conn:
        conn.execute("UPDATE text_postings SET ids = x'0900'")
    expected = _references(built)
    builds.count = 0
    assert [gram_scores(database, text).rows for text in _inputs(built)] == expected
    assert builds.count == 1


def test_a_row_sqlite_cannot_read_is_an_unreadable_database(built: Path) -> None:
    with writer(built) as conn:
        conn.execute("UPDATE text_postings SET ids = CAST(x'41ff42' AS TEXT)")
    with pytest.raises(DatabaseNotReadyError, match="^database: unreadable"):
        _tables(built)


@pytest.fixture(name="seeded")
def _seeded() -> Generator[str, None, None]:
    yield from texts_database("test_gramstore_db")


def test_a_database_a_script_filled_is_read_through_memory(
    seeded: str, builds: Calls
) -> None:
    """Tables made by the builder, rows by SQL: no postings, no stamp."""
    database = LicenseDatabase(seeded, create=False)
    with contextlib.closing(sqlite3.connect(seeded, uri=True)) as conn:
        texts = [text for _, text in read_texts(conn)]
        index = build_index(read_texts(conn))
        for text in texts:
            grams = input_grams(text)
            shared = index.shared(conn, grams)
            expected = score_rows(shared, len(grams), index.ids, index.sizes)
            assert gram_scores(database, text).rows == expected
    assert len(texts) == 4
    assert builds.count == 1  # the lookup's index, built once


def test_an_update_drops_the_postings_of_the_old_rows(built: Path) -> None:
    """A handle that read the old postings reads the new rows' after an
    update by another handle, and the handle of the update too."""
    reader = LicenseDatabase(str(built), create=False)
    before = gram_scores(reader, TEXTS["D-1.0"]).rows
    assert before[0].license_id == "D-1.0"
    database_of(OTHER, built)
    assert gram_scores(reader, TEXTS["D-1.0"]).rows[0].license_id == "A-1.0"
    assert gram_scores(reader, TEXTS["A-1.0"]).rows[0].license_id == "E-1.0"


def test_the_handle_of_an_update_reads_the_new_postings(built: Path) -> None:
    database = LicenseDatabase(str(built))
    assert gram_scores(database, TEXTS["D-1.0"]).rows[0].license_id == "D-1.0"
    _update_in_place(database, OTHER)
    assert gram_scores(database, TEXTS["D-1.0"]).rows[0].license_id == "A-1.0"


def _update_in_place(database: LicenseDatabase, raw: bytes) -> None:
    from release_fakes import ship  # pylint: disable=import-outside-toplevel

    with pytest.MonkeyPatch.context() as patch:
        ship(patch, raw)
        with pytest.warns(LicenseIdWarning, match="^popularity.csv: missing$"):
            database.update_from_remote(source="packaged", use_cache=False)


def _at_once(count: int, call: Callable[[], object]) -> list[object]:
    start = threading.Barrier(count)
    found: list[object] = []

    def run() -> None:
        start.wait()
        found.append(call())

    threads = [threading.Thread(target=run) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    return found


@pytest.mark.parametrize("stored", [True, False], ids=["stored", "memory"])
def test_eight_threads_first_call_get_one_complete_index(
    built: Path, monkeypatch: pytest.MonkeyPatch, stored: bool
) -> None:
    if not stored:
        with writer(built) as conn:
            conn.execute(f"DELETE FROM db_metadata WHERE key = '{STAMP_KEY}'")
    loads = _counted(monkeypatch, "load")
    database = LicenseDatabase(str(built), create=False)
    text = TEXTS["A-1.0"]
    found = _at_once(8, lambda: gram_scores(database, text).rows)
    assert found == _references(built, [text]) * 8
    assert loads.count == 1


def _count_queries(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from licenseid.dbconnection import Connections  # pylint: disable=C0415

    seen: list[str] = []
    real = Connections.connect

    def traced(self: Connections, write: bool = False) -> sqlite3.Connection:
        conn = real(self, write)
        conn.set_trace_callback(seen.append)
        return conn

    monkeypatch.setattr(Connections, "connect", traced)
    return seen


@pytest.mark.parametrize(("words", "queries"), [(903, 2), (1802, 2), (1803, 3)])
def test_a_long_input_is_looked_up_900_grams_a_query(
    built: Path, monkeypatch: pytest.MonkeyPatch, words: int, queries: int
) -> None:
    """901, 1,800 and 1,801 grams, read in one transaction; D-1.0's grams
    last, across the end of a query's 900."""
    database = LicenseDatabase(str(built), create=False)
    text = " ".join([*(f"w{n}" for n in range(words - 10)), TEXTS["D-1.0"]])
    seen = _count_queries(monkeypatch)
    table = gram_scores(database, text)
    assert table.grams == words - 2
    assert sum("FROM text_postings WHERE" in s for s in seen) == queries
    assert seen.count("BEGIN") == 1
    assert [table.rows] == _references(built, [text])
    assert table.rows[0][:3] == ("D-1.0", 8, 8)


def _ids(rows: Iterable[GramScore]) -> list[str]:
    return [row.license_id for row in rows]


def test_a_bounded_lookup_reads_the_first_grams(built: Path) -> None:
    database = LicenseDatabase(str(built), create=False)
    text = TEXTS["D-1.0"] + " " + TEXTS["A-1.0"]
    table = gram_scores(database, text, limit=8)
    assert (table.grams, table.bounded) == (8, True)
    assert _ids(table.rows) == ["D-1.0"]
