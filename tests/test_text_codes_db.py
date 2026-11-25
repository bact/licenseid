# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The coded List texts of build 6 (``text_codes``): ``update`` stores them,
a read restores the corpus from them instead of coding every text again, and
a database without them, or with a damaged table, is coded in memory and never
written (a lookup never writes). The corpus read from the table is the one
``TextCorpus.build`` gives."""
# pylint: disable=missing-function-docstring,protected-access

import hashlib
import os
import stat
from collections.abc import Generator, Iterable
from pathlib import Path
from types import MappingProxyType

import pytest
from conftest import GivenWarnings, posix_only
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import writer
from list_entries import lic_entry
from packaged_list import database_of
from texts_db import texts_database

from licenseid.database import LicenseDatabase, text_corpus
from licenseid.dbconnection import Connections
from licenseid.dbschema import schema_state
from licenseid.errors import DatabaseNotReadyError
from licenseid.records import BUILD_VERSION, Records
from licenseid.spdxdata import SpdxData, to_bundle
from licenseid.textcorpus import CHECK, CORE, TEXT, WORDS, TextCorpus, TextRow

BEGIN, END = "<<beginOptional>>", "<<endOptional>>"
BODY = " ".join(f"clause{i} of the licence" for i in range(12))
TEXTS = {
    "A-1.0": f"{BODY} and an appendix of five more words",
    "B-1.0": "you may not copy this " + BODY,
    "C-1.0": "you may not copy this " + BODY,  # B-1.0 by text
    "J-1.0": "許諾 書 neither this nor that",
}
TEMPLATES = {
    "A-1.0": f"{BODY} {BEGIN}and an appendix of five more words{END}",
}
RAW = to_bundle(
    SpdxData(
        "9.99",
        None,
        tuple(lic_entry(license_id, f"Name {license_id}") for license_id in TEXTS),
        (),
        MappingProxyType(TEXTS),
        MappingProxyType(TEMPLATES),
    )
)
OUTDATED = "build v5 outdated"


def _kinds(path: Path) -> list[tuple[str, str]]:
    with writer(path) as conn:
        return conn.execute(
            "SELECT kind, owner_id FROM text_codes ORDER BY kind, owner_id"
        ).fetchall()


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _corpus(path: Path) -> TextCorpus:
    """The corpus of a database opened as a lookup opens it."""
    return text_corpus(LicenseDatabase(str(path), create=False))


class Builds:
    """The calls of ``TextCorpus.build`` while a test runs."""

    def __init__(self) -> None:
        self.count = 0


@pytest.fixture(name="builds")
def _builds(monkeypatch: pytest.MonkeyPatch) -> Builds:
    seen = Builds()
    real = TextCorpus.build  # bound to the class: taken before the patch

    def counting(rows: Iterable[TextRow]) -> TextCorpus:
        seen.count += 1
        return real(rows)

    monkeypatch.setattr(TextCorpus, "build", staticmethod(counting))
    return seen


@pytest.fixture(name="build_6")
def _build_6(tmp_path: Path) -> Path:
    path = tmp_path / "licenses.db"
    database_of(RAW, path)
    return path


@pytest.fixture(name="build_5")
def _build_5(build_6: Path) -> Path:
    """A database as build 5 left it: no ``text_codes``, stamped 5."""
    with writer(build_6) as conn:
        conn.execute("DROP TABLE text_codes")
        conn.execute("UPDATE db_metadata SET value = '5' WHERE key = 'build_version'")
    return build_6


def test_the_build_is_6() -> None:
    assert BUILD_VERSION == "6"


def test_update_stores_the_vocabulary_and_each_text_and_core(build_6: Path) -> None:
    assert _kinds(build_6) == [
        (CHECK, ""),
        (CORE, "A-1.0"),
        (TEXT, "A-1.0"),
        (TEXT, "B-1.0"),  # C-1.0 has the same text: one row for the group
        (TEXT, "J-1.0"),
        (WORDS, ""),
    ]


def test_the_corpus_is_read_from_the_table_not_coded(
    build_6: Path, builds: Builds
) -> None:
    corpus = _corpus(build_6)
    assert builds.count == 0
    assert [e.text.row_id for e in corpus.entries] == ["A-1.0", "B-1.0", "J-1.0"]
    assert corpus.entries[0].core is not None
    assert corpus.representative("C-1.0") == "B-1.0"


def test_the_corpus_read_is_the_corpus_built(
    build_6: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    read = _corpus(build_6)
    monkeypatch.setattr(TextCorpus, "restore", classmethod(lambda *_: None))
    assert _corpus(build_6) == read


def test_the_rows_of_the_build_are_those_of_the_corpus(build_6: Path) -> None:
    with writer(build_6) as conn:
        stored = conn.execute("SELECT kind, owner_id, body FROM text_codes").fetchall()
    assert sorted(stored) == sorted(_corpus(build_6).stored_rows())


def test_a_database_of_build_5_is_current_and_codes_in_memory(
    build_5: Path, builds: Builds, given: GivenWarnings
) -> None:
    location = str(build_5)
    assert schema_state(Connections(location, False, location, False)) == "current"
    before = _digest(build_5)
    corpus = _corpus(build_5)
    assert builds.count == 1
    assert given.conditions() == {OUTDATED}
    assert _digest(build_5) == before  # a lookup never writes
    assert len(corpus.entries) == 3 and corpus.entries[0].core is not None
    with writer(build_5) as conn:
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    assert "text_codes" not in names


@posix_only
def test_a_read_only_database_of_build_5_gives_its_corpus(
    build_5: Path, builds: Builds, given: GivenWarnings
) -> None:
    build_5.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    try:
        if os.access(build_5, os.W_OK):  # root writes whatever the mode says
            pytest.skip("this user writes to a mode-444 file")
        before = _digest(build_5)
        assert len(_corpus(build_5).entries) == 3
        assert builds.count == 1
        assert _digest(build_5) == before
        assert given.conditions() == {OUTDATED}
    finally:
        build_5.chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_a_database_of_build_5_corpus_is_the_one_of_build_6(
    build_6: Path, tmp_path: Path
) -> None:
    stored = _corpus(build_6)
    older = tmp_path / "older.db"
    older.write_bytes(build_6.read_bytes())
    with writer(older) as conn:
        conn.execute("DROP TABLE text_codes")
    assert _corpus(older) == stored


def test_update_gives_a_database_of_build_5_its_table(
    build_5: Path, builds: Builds
) -> None:
    database = database_of(RAW, build_5)
    assert database.get_metadata()["build_version"] == BUILD_VERSION
    assert len(_kinds(build_5)) == 6
    assert builds.count == 1  # the build of the rows to store
    builds.count = 0
    assert len(text_corpus(database).entries) == 3
    assert builds.count == 0


def _delete(owner: str, kind: str) -> str:
    return f"DELETE FROM text_codes WHERE kind = '{kind}' AND owner_id = '{owner}'"


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM text_codes",
        f"DELETE FROM text_codes WHERE kind = '{WORDS}'",
        _delete("B-1.0", TEXT),
        _delete("A-1.0", CORE),
        f"UPDATE text_codes SET body = '' WHERE kind = '{TEXT}'",
        f"UPDATE text_codes SET body = 'not json' WHERE kind = '{WORDS}'",
        f"UPDATE text_codes SET body = '[1, 2]' WHERE kind = '{WORDS}'",
        f"INSERT INTO text_codes VALUES ('{TEXT}', 'Z-1.0', 'x')",
        f"INSERT INTO text_codes VALUES ('{CORE}', 'B-1.0', 'x')",
        "INSERT INTO text_codes VALUES ('other', 'A-1.0', 'x')",
        f"DELETE FROM text_codes WHERE kind = '{CHECK}'",
        f"UPDATE text_codes SET body = '{'0' * 64}' WHERE kind = '{CHECK}'",
        f"UPDATE text_codes SET body = x'4142' WHERE kind = '{TEXT}'",  # a BLOB
        f"UPDATE text_codes SET body = x'5b5d' WHERE kind = '{WORDS}'",
        f"UPDATE text_codes SET body = x'4142' WHERE kind = '{CHECK}'",
        f"UPDATE text_codes SET kind = x'74657874' WHERE kind = '{TEXT}'",
        "UPDATE text_codes SET owner_id = x'4231' WHERE owner_id = 'B-1.0'",
        f"UPDATE text_codes SET body = body || char(1, 2) WHERE kind = '{TEXT}'",
        (
            "UPDATE text_codes SET body = (SELECT group_concat(body, '')"
            f" FROM text_codes WHERE kind IN ('{TEXT}', '{CORE}'))"
            f" WHERE kind = '{TEXT}'"
        ),
        (
            "UPDATE text_codes SET body = CASE owner_id WHEN 'A-1.0' THEN"
            f" (SELECT body FROM text_codes WHERE kind = '{TEXT}'"
            " AND owner_id = 'J-1.0')"
            f" ELSE (SELECT body FROM text_codes WHERE kind = '{TEXT}'"
            " AND owner_id = 'A-1.0') END"
            f" WHERE kind = '{TEXT}' AND owner_id IN ('A-1.0', 'J-1.0')"
        ),
    ],
    ids=[
        "empty",
        "no-words",
        "no-text",
        "no-core",
        "empty-codes",
        "not-json",
        "not-strings",
        "unknown-text",
        "unneeded-core",
        "unknown-kind",
        "no-check",
        "other-check",
        "blob-text",
        "blob-words",
        "blob-check",
        "blob-kind",
        "blob-owner",
        "codes-more",
        "huge",
        "swapped",
    ],
)
def test_a_damaged_table_is_coded_in_memory_and_left_as_it_is(
    build_6: Path, builds: Builds, statement: str
) -> None:
    expected = _corpus(build_6)
    with writer(build_6) as conn:
        conn.execute(statement)
    before = _digest(build_6)
    builds.count = 0
    assert _corpus(build_6) == expected
    assert builds.count == 1
    assert _digest(build_6) == before


def test_a_text_read_as_bytes_gives_no_error(build_6: Path, builds: Builds) -> None:
    """A BLOB in ``body`` comes back as bytes; the corpus is coded instead of
    ``detect()`` failing on a count of bytes."""
    with writer(build_6) as conn:
        conn.execute(f"UPDATE text_codes SET body = x'4142' WHERE kind = '{TEXT}'")
    builds.count = 0
    assert len(_corpus(build_6).entries) == 3
    assert builds.count == 1


@pytest.mark.parametrize(
    "statement",
    [
        f"UPDATE text_codes SET body = CAST(x'41ff42' AS TEXT) WHERE kind = '{TEXT}'",
        (
            "UPDATE text_codes SET body = CAST(x'5b22ff225d' AS TEXT)"
            f" WHERE kind = '{WORDS}'"
        ),
    ],
    ids=["codes", "words"],
)
def test_a_row_sqlite_cannot_read_as_text_is_an_unreadable_database(
    build_6: Path, statement: str
) -> None:
    """Not swallowed per method (AGENTS.md): as any read SQLite fails."""
    with writer(build_6) as conn:
        conn.execute(statement)
    with pytest.raises(DatabaseNotReadyError, match="^database: unreadable"):
        _corpus(build_6)


def _stale_corpus(
    path: Path, statement: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[TextCorpus, TextCorpus]:
    """The corpus read after *statement* changed the rows the codes were
    made of, and the corpus ``build`` gives for them."""
    with writer(path) as conn:
        conn.execute(statement)
    read = _corpus(path)
    monkeypatch.setattr(TextCorpus, "restore", classmethod(lambda *_: None))
    return read, _corpus(path)


@pytest.mark.parametrize(
    "statement",
    [
        (
            "UPDATE license_index SET search_text = search_text || ' and more'"
            " WHERE license_id = 'A-1.0'"
        ),
        (
            "UPDATE license_index SET search_text = 'one two three four'"
            " WHERE license_id = 'B-1.0'"
        ),
        "UPDATE licenses SET core_text = 'clause0 of' WHERE license_id = 'A-1.0'",
        "UPDATE licenses SET core_text = NULL WHERE license_id = 'A-1.0'",
    ],
    ids=["text", "other-text", "core", "no-core"],
)
def test_codes_left_by_a_program_that_rewrote_the_rows_are_not_read(
    build_6: Path, statement: str, builds: Builds, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 0.9.2 case: ``update`` of a program that knows no ``text_codes``
    rewrites ``license_index`` and the cores, keeps the table and the names."""
    old = _corpus(build_6)
    builds.count = 0
    read, built = _stale_corpus(build_6, statement, monkeypatch)
    assert read == built
    assert read != old
    assert builds.count == 2  # the read, then the build the test asks for


def test_a_new_stamp_reads_the_table_again(build_6: Path, builds: Builds) -> None:
    database = LicenseDatabase(str(build_6), create=False)
    assert text_corpus(database) is text_corpus(database)  # kept
    with writer(build_6) as conn:
        conn.execute("DELETE FROM text_codes")
        conn.execute(
            "UPDATE db_metadata SET value = 'later' WHERE key = 'last_update_datetime'"
        )
    builds.count = 0
    assert len(text_corpus(database).entries) == 3  # coded: the table is empty
    assert builds.count == 1


def test_records_carry_no_texts_unless_built() -> None:
    assert Records([], [], [], []).texts == ()


@pytest.fixture(name="seeded")
def _seeded() -> Generator[str, None, None]:
    yield from texts_database("test_text_codes_db")


def test_a_database_with_the_table_and_no_rows_is_coded(
    seeded: str, builds: Builds
) -> None:
    """A database a script filled (``text_codes`` empty): coded in memory."""
    corpus = text_corpus(LicenseDatabase(seeded, create=False))
    assert [e.text.row_id for e in corpus.entries] == ["A-1.0", "B-1.0", "GPL-3.0-only"]
    assert builds.count == 1


def test_a_new_database_has_the_table_before_any_update(tmp_path: Path) -> None:
    path = tmp_path / "licenses.db"
    LicenseDatabase(str(path))._ensure_schema()
    assert _kinds(path) == []
