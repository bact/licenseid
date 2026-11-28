# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The coded List texts of build 9 (``text_codes`` and ``text_code_checks``):
``update`` stores them with a check of the head and of each entry; a lookup
reads the entries of its candidates only, each checked, instead of coding
every text again; a head or an entry that fails its check is coded in memory
and never written (a lookup never writes). The corpus read is the one
``TextCorpus.build`` gives."""
# pylint: disable=missing-function-docstring,protected-access

import hashlib
from collections.abc import Generator
from pathlib import Path
from types import MappingProxyType

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import writer
from list_entries import lic_entry
from packaged_list import database_of
from stored_texts import Counts, all_texts, counting, no_stored_codes
from texts_db import texts_database

from licenseid.database import LicenseDatabase
from licenseid.dbschema import BUILD_VERSION
from licenseid.errors import DatabaseNotReadyError
from licenseid.records import Records
from licenseid.spdxdata import SpdxData, to_bundle
from licenseid.textcorpus import TextCorpus
from licenseid.textstore import CORE, CORE_GRAMS, PATTERNS, TEXT, WORDS, stored_rows

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
NAMES = ["A-1.0", "B-1.0", "J-1.0"]


def _kinds(path: Path) -> list[tuple[str, str]]:
    with writer(path) as conn:
        return conn.execute(
            "SELECT kind, owner_id FROM text_codes ORDER BY kind, owner_id"
        ).fetchall()


def _owners(path: Path) -> list[str]:
    with writer(path) as conn:
        return [
            owner
            for (owner,) in conn.execute(
                "SELECT owner_id FROM text_code_checks ORDER BY owner_id"
            )
        ]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _db(path: Path) -> LicenseDatabase:
    """A database opened as a lookup opens it."""
    return LicenseDatabase(str(path), create=False)


def _corpus(path: Path, ids: list[str] | None = None) -> TextCorpus:
    return all_texts(_db(path), ids)


@pytest.fixture(name="counts")
def _counts(monkeypatch: pytest.MonkeyPatch) -> Counts:
    return counting(monkeypatch)


@pytest.fixture(name="build_now")
def _build_now(tmp_path: Path) -> Path:
    path = tmp_path / "licenses.db"
    database_of(RAW, path)
    return path


@pytest.fixture(name="built")
def _built(build_now: Path, monkeypatch: pytest.MonkeyPatch) -> TextCorpus:
    """The corpus a lookup of *build_now* builds in memory."""
    with monkeypatch.context() as patch:
        no_stored_codes(patch)
        corpus = _corpus(build_now)
    return corpus


def test_the_build_is_9() -> None:
    assert BUILD_VERSION == "9"


def test_update_stores_the_head_each_text_and_core_and_their_checks(
    build_now: Path,
) -> None:
    assert _kinds(build_now) == [
        (CORE, "A-1.0"),
        (CORE_GRAMS, ""),
        (PATTERNS, ""),
        (TEXT, "A-1.0"),
        (TEXT, "B-1.0"),  # C-1.0 has the same text: one row for the group
        (TEXT, "J-1.0"),
        (WORDS, ""),
    ]
    assert _owners(build_now) == ["", *NAMES]  # the head, then each entry


def test_the_corpus_is_read_from_the_table_not_coded(
    build_now: Path, counts: Counts
) -> None:
    corpus = _corpus(build_now)
    assert counts.builds == 0
    assert [e.text.row_id for e in corpus.entries] == NAMES
    assert corpus.entries[0].core is not None
    assert corpus.representative("C-1.0") == "B-1.0"


def test_the_corpus_read_is_the_corpus_built(
    build_now: Path, built: TextCorpus
) -> None:
    assert _corpus(build_now) == built


def test_the_rows_of_the_build_are_those_of_the_corpus(build_now: Path) -> None:
    with writer(build_now) as conn:
        stored = conn.execute("SELECT kind, owner_id, body FROM text_codes").fetchall()
    assert sorted(stored) == sorted(stored_rows(_corpus(build_now)))


def test_a_call_reads_the_entries_of_its_texts_only(
    build_now: Path, counts: Counts
) -> None:
    database = _db(build_now)
    corpus = all_texts(database, ["C-1.0"])
    assert [e.text.row_id for e in corpus.entries] == ["B-1.0"]
    assert counts.read == ["B-1.0"]
    assert all_texts(database, ["B-1.0", "A-1.0"]).entries[1] == corpus.entries[0]
    assert counts.read == ["B-1.0", "A-1.0"]  # B-1.0 kept
    assert not all_texts(database, ["Z-1.0"]).entries  # no text: nothing read
    assert counts.read == ["B-1.0", "A-1.0"] and counts.builds == 0


def _delete(owner: str, kind: str) -> str:
    return f"DELETE FROM text_codes WHERE kind = '{kind}' AND owner_id = '{owner}'"


def _check(owner: str, digest: str = "0" * 64) -> str:
    return f"UPDATE text_code_checks SET digest = '{digest}' WHERE owner_id = '{owner}'"


# Each breaks the head or the entry of B-1.0 (C-1.0 asks for it).
DAMAGE = {
    "empty": "DELETE FROM text_codes",
    "no-words": f"DELETE FROM text_codes WHERE kind = '{WORDS}'",
    "no-core-grams": f"DELETE FROM text_codes WHERE kind = '{CORE_GRAMS}'",
    "no-text": _delete("B-1.0", TEXT),
    "empty-codes": f"UPDATE text_codes SET body = '' WHERE kind = '{TEXT}'",
    "not-json": f"UPDATE text_codes SET body = 'not json' WHERE kind = '{WORDS}'",
    "not-strings": f"UPDATE text_codes SET body = '[1, 2]' WHERE kind = '{WORDS}'",
    "unneeded-core": f"INSERT INTO text_codes VALUES ('{CORE}', 'B-1.0', 'x')",
    "core-vars-only": "INSERT INTO text_codes VALUES ('corevars', 'B-1.0', '[]')",
    "no-head-check": "DELETE FROM text_code_checks WHERE owner_id = ''",
    "other-head-check": _check(""),
    "no-entry-check": "DELETE FROM text_code_checks WHERE owner_id = 'B-1.0'",
    "other-entry-check": _check("B-1.0"),
    "no-checks": "DELETE FROM text_code_checks",
    "blob-check": "UPDATE text_code_checks SET digest = CAST(digest AS BLOB)",
    "blob-text": f"UPDATE text_codes SET body = x'4142' WHERE kind = '{TEXT}'",
    "blob-words": f"UPDATE text_codes SET body = x'5b5d' WHERE kind = '{WORDS}'",
    "blob-kind": f"UPDATE text_codes SET kind = x'74657874' WHERE kind = '{TEXT}'",
    "blob-owner": "UPDATE text_codes SET owner_id = x'4231' WHERE owner_id = 'B-1.0'",
    "codes-more": (
        f"UPDATE text_codes SET body = body || char(1, 2) WHERE kind = '{TEXT}'"
    ),
    "codes-cut": (
        "UPDATE text_codes SET body = CAST(substr(CAST(body AS BLOB), 1,"
        f" length(CAST(body AS BLOB)) - 1) AS BLOB) WHERE kind = '{TEXT}'"
    ),
    "others-codes": (
        "UPDATE text_codes SET body = (SELECT body FROM text_codes"
        f" WHERE kind = '{TEXT}' AND owner_id = 'A-1.0')"
        f" WHERE kind = '{TEXT}' AND owner_id = 'B-1.0'"
    ),
    "checks-swapped": (
        "UPDATE text_code_checks SET digest = (SELECT digest FROM"
        " text_code_checks WHERE owner_id = 'A-1.0') WHERE owner_id = 'B-1.0'"
    ),
}


@pytest.mark.parametrize("statement", list(DAMAGE.values()), ids=list(DAMAGE))
def test_a_damaged_table_is_coded_in_memory_and_left_as_it_is(
    build_now: Path, built: TextCorpus, counts: Counts, statement: str
) -> None:
    with writer(build_now) as conn:
        conn.execute(statement)
    before = _digest(build_now)
    counts.builds = 0
    assert _corpus(build_now, ["C-1.0"]) == built.cut(["C-1.0"])
    assert counts.builds == 1
    assert _digest(build_now) == before


def test_damage_to_an_entry_no_call_reads_is_not_seen(
    build_now: Path, built: TextCorpus, counts: Counts
) -> None:
    """The check is per entry: the damage of J-1.0 drops the stored codes
    when a call reads J-1.0, not before."""
    with writer(build_now) as conn:
        conn.execute(_check("J-1.0"))
    database = _db(build_now)
    counts.builds = 0
    stored = all_texts(database, ["A-1.0"])
    assert stored.entries[0].text.row_id == "A-1.0" and counts.builds == 0
    assert all_texts(database, ["J-1.0"]) == built.cut(["J-1.0"])
    assert counts.builds == 1
    assert all_texts(database, ["A-1.0"]) == built.cut(["A-1.0"])  # built since
    assert counts.builds == 1


@pytest.mark.parametrize(
    "statement",
    [
        f"UPDATE text_codes SET body = CAST(x'41ff42' AS TEXT) WHERE kind = '{TEXT}'",
        (
            "UPDATE text_codes SET body = CAST(x'5b22ff225d' AS TEXT)"
            f" WHERE kind = '{WORDS}'"
        ),
        "UPDATE text_code_checks SET digest = CAST(x'41ff42' AS TEXT)",
    ],
    ids=["codes", "words", "check"],
)
def test_a_row_sqlite_cannot_read_as_text_is_an_unreadable_database(
    build_now: Path, statement: str
) -> None:
    """Not swallowed per method (AGENTS.md): as any read SQLite fails."""
    with writer(build_now) as conn:
        conn.execute(statement)
    with pytest.raises(DatabaseNotReadyError, match="^database: unreadable"):
        _corpus(build_now)


EDITS = {
    "text": (
        "UPDATE license_index SET search_text = search_text || ' and more'"
        " WHERE license_id = 'A-1.0'"
    ),
    "shorter-text": (
        "UPDATE license_index SET search_text = 'one two three four'"
        " WHERE license_id = 'B-1.0'"
    ),
    "empty-text": (
        "UPDATE license_index SET search_text = '' WHERE license_id = 'A-1.0'"
    ),
    "core": "UPDATE licenses SET core_text = 'clause0 of' WHERE license_id = 'A-1.0'",
    "no-core": "UPDATE licenses SET core_text = NULL WHERE license_id = 'A-1.0'",
}
STAMP = "UPDATE db_metadata SET value = 'later' WHERE key = 'last_update_datetime'"


@pytest.mark.parametrize("statement", list(EDITS.values()), ids=list(EDITS))
@pytest.mark.parametrize("stamped", [False, True], ids=["same-time", "new-time"])
def test_codes_of_rows_edited_since_are_not_read(
    build_now: Path,
    statement: str,
    stamped: bool,
    counts: Counts,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rows edited by hand, with or without a new ``last_update_datetime``:
    the entry's check fails when it is read (the head's at once with a new
    time), and the corpus is coded from the rows as they are now; a region
    past the end of a shorter text never raises."""
    old = _corpus(build_now)
    with writer(build_now) as conn:
        conn.execute(statement)
        if stamped:
            conn.execute(STAMP)
    counts.builds = 0
    read = _corpus(build_now, NAMES)
    assert counts.builds == 1
    no_stored_codes(monkeypatch)
    assert read == _corpus(build_now, NAMES)
    assert read != old


def test_a_new_time_drops_the_codes_of_texts_no_call_reads(
    build_now: Path, counts: Counts
) -> None:
    """With a new ``last_update_datetime`` the head fails its check: an
    edit to J-1.0 is not served as stored for A-1.0 either."""
    with writer(build_now) as conn:
        conn.execute(STAMP)
    counts.builds = 0
    _corpus(build_now, ["A-1.0"])
    assert counts.builds == 1 and not counts.read


def test_an_update_in_another_process_reads_the_table_again(
    build_now: Path, tmp_path: Path, counts: Counts
) -> None:
    database = _db(build_now)
    assert all_texts(database, ["A-1.0"]).entries[0].text.row_id == "A-1.0"
    other = tmp_path / "other.db"
    database_of(RAW, other)  # another time, with its own checks
    build_now.write_bytes(other.read_bytes())
    counts.read.clear()
    counts.builds = 0
    assert len(all_texts(database, ["A-1.0"]).entries) == 1
    assert counts.read == ["A-1.0"] and counts.builds == 0


#: Another build: a licence before A-1.0 (its rows move) and A-1.0 edited.
MOVED = {"0-1.0": "a licence of its own " + BODY, **TEXTS, "A-1.0": BODY + " edited"}


def test_an_update_inside_a_reading_block_is_seen_by_the_next_call(
    build_now: Path, counts: Counts
) -> None:
    """The stamp is read again in each call's transaction: the IDs and rows
    kept from before an update are dropped, so the entries read are those of
    the new rows, as stored."""
    database = _db(build_now)
    raw = to_bundle(
        SpdxData(
            "10.0",
            None,
            tuple(lic_entry(i, f"Name {i}") for i in MOVED),
            (),
            MappingProxyType(MOVED),
            MappingProxyType({}),
        )
    )
    with database.reading():
        assert all_texts(database, ["A-1.0"]).entries[0].text.text.endswith("words")
        database_of(raw, build_now)  # update writes through a connection of its own
        counts.builds = 0
        corpus = all_texts(database, ["A-1.0"])
    assert corpus.entries[0].text.text.endswith("edited")
    assert counts.builds == 0


def test_records_carry_no_texts_unless_built() -> None:
    assert Records([], [], [], []).texts == ()


@pytest.fixture(name="seeded")
def _seeded() -> Generator[str, None, None]:
    yield from texts_database("test_text_codes_db")


def test_a_database_with_the_tables_and_no_rows_is_coded(
    seeded: str, counts: Counts
) -> None:
    """A database a script filled (``text_codes`` empty): coded in memory."""
    corpus = all_texts(LicenseDatabase(seeded, create=False))
    assert [e.text.row_id for e in corpus.entries] == ["A-1.0", "B-1.0", "GPL-3.0-only"]
    assert counts.builds == 1


def test_a_new_database_has_the_tables_before_any_update(tmp_path: Path) -> None:
    path = tmp_path / "licenses.db"
    LicenseDatabase(str(path))._ensure_schema()
    assert _kinds(path) == [] and _owners(path) == []
