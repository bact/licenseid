# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The core text and the same-text group of a licence (build 5): the rows
``build_records`` makes, the columns, the schema upgrade of an older file and
the read ``text_parts`` keeps."""
# pylint: disable=missing-function-docstring,protected-access

import json
import sqlite3
from pathlib import Path
from types import MappingProxyType

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import writer
from list_entries import lic_entry
from packaged_list import database_of

from licenseid.database import LicenseDatabase, text_parts
from licenseid.dbschema import schema_state
from licenseid.normalize import normalize_text
from licenseid.records import (
    BUILD_VERSION,
    LicenseInsertRecord,
    build_records,
    uneven_cores,
)
from licenseid.spdxdata import SpdxData, to_bundle
from licenseid.types import TextParts

FIXTURES = Path(__file__).parent / "fixtures"
BEGIN = "<<beginOptional>>"
END = "<<endOptional>>"
COLUMNS = ("core_text", "core_word_count", "same_text")


def words(count: int, start: int = 0) -> str:
    """*count* distinct lower-case words (letters only, kept by the
    normaliser as written)."""
    return " ".join(
        f"w{chr(97 + (start + i) % 26)}{chr(97 + (start + i) // 26)}"
        for i in range(count)
    )


def data_of(texts: dict[str, str], templates: dict[str, str] | None = None) -> SpdxData:
    return SpdxData(
        "9.99",
        None,
        tuple(lic_entry(license_id, f"Name {license_id}") for license_id in texts),
        (),
        MappingProxyType(texts),
        MappingProxyType(templates or {}),
    )


def row(data: SpdxData, license_id: str) -> LicenseInsertRecord:
    (found,) = [r for r in build_records(data, {}).licenses if r[0] == license_id]
    return found


def core_of(data: SpdxData, license_id: str) -> tuple[str | None, int | None]:
    record = row(data, license_id)
    return record[13], record[14]


def with_optional(kept: int, optional: int) -> SpdxData:
    """One licence: *kept* words that stay and *optional* that a copy may
    leave out."""
    template = f"{words(kept)} {BEGIN}{words(optional, kept)}{END}"
    return data_of({"A": words(kept + optional)}, {"A": template})


def test_the_build_carries_the_parts() -> None:
    assert BUILD_VERSION == "6"


@pytest.mark.parametrize(
    ("kept", "optional", "is_kept"),
    [
        (9, 1, True),
        (10, 1, True),
        (19, 2, True),  # 19 of 21 words: 0.905, once too many to keep
        (99, 1, True),  # one word fewer
        (10, 0, False),  # as long as the whole text
        (1, 9, True),
        (0, 5, False),  # nothing is left
    ],
)
def test_a_core_is_kept_when_it_has_fewer_words(
    kept: int, optional: int, is_kept: bool
) -> None:
    core, count = core_of(with_optional(kept, optional), "A")
    if is_kept:
        assert (core, count) == (words(kept), kept)
    else:
        assert (core, count) == (None, None)


def test_the_core_is_normalised_as_the_text_is() -> None:
    template = f"The   Licence,\tGRANTED. {BEGIN}Title line and more words here{END}"
    data = data_of(
        {"A": "The Licence, GRANTED. Title line and more words here"}, {"A": template}
    )
    core, count = core_of(data, "A")
    assert core == normalize_text("The Licence, GRANTED.")
    assert count == len(str(core).split())


def test_a_var_counts_as_its_original() -> None:
    var = '<<var;name="n";original="Copyright Holder";match=".*">>'
    template = f"{words(4)} {var} {BEGIN}{words(20, 4)}{END}"
    data = data_of(
        {"A": f"{words(4)} Copyright Holder {words(20, 4)}"}, {"A": template}
    )
    assert core_of(data, "A") == (normalize_text(f"{words(4)} Copyright Holder"), 6)


@pytest.mark.parametrize(
    "template",
    [None, f"{BEGIN}unclosed {words(30)}", f"{words(30)} {END}"],
    ids=["none", "unclosed", "stray-end"],
)
def test_no_core_without_a_usable_template(template: str | None) -> None:
    templates = {} if template is None else {"A": template}
    assert core_of(data_of({"A": words(60)}, templates), "A") == (None, None)


def test_a_licence_without_a_text_has_no_core() -> None:
    data = SpdxData(
        "9.99",
        None,
        (lic_entry("B", "B", deprecated=True),),
        (),
        MappingProxyType({}),
        MappingProxyType({"B": f"x {BEGIN}{words(60)}{END}"}),
    )
    assert row(data, "B")[13:] == (None, None, None)


def test_the_licences_with_one_text_are_a_group() -> None:
    same = words(30)
    data = data_of(
        {
            "B-1.0": same,
            "A-1.0": same.upper(),  # the normalised text is the same
            "C-1.0": f"{same} more",
            "D-1.0": words(31),
            "E-1.0": "",
            "F-1.0": "   ",
        }
    )
    got = {r[0]: r[15] for r in build_records(data, {}).licenses}
    assert got == {
        "A-1.0": "A-1.0 B-1.0",
        "B-1.0": "A-1.0 B-1.0",
        "C-1.0": None,
        "D-1.0": None,
        "E-1.0": None,  # no word, no evidence: two empty texts are no group
        "F-1.0": None,
    }


def test_a_group_may_hold_many_and_a_licence_is_in_one() -> None:
    data = data_of({f"X-{n}": words(20) for n in (3, 1, 2)} | {"Y": words(21)})
    got = {r[0]: r[15] for r in build_records(data, {}).licenses}
    assert got == {
        "X-1": "X-1 X-2 X-3",
        "X-2": "X-1 X-2 X-3",
        "X-3": "X-1 X-2 X-3",
        "Y": None,
    }


def test_a_deprecated_licence_with_text_is_in_a_group_too() -> None:
    data = SpdxData(
        "9.99",
        None,
        (lic_entry("New-1.0", "N"), lic_entry("Old-1.0", "O", deprecated=True)),
        (),
        MappingProxyType({"New-1.0": words(20), "Old-1.0": words(20)}),
    )
    got = {r[0]: r[15] for r in build_records(data, {}).licenses}
    assert got["New-1.0"] == got["Old-1.0"] == "New-1.0 Old-1.0"


def _twins(other: str | None) -> SpdxData:
    """A, B and C of one text, A and C with one template, B with *other*
    (none when None); D of another text with A's template."""
    template = f"{words(10)} {BEGIN}{words(5, 10)}{END}"
    templates = {"A": template, "C": template, "D": template}
    if other is not None:
        templates["B"] = other
    text = words(15)
    return data_of({"A": text, "B": text, "C": text, "D": f"{text} more"}, templates)


def test_a_group_with_one_core_keeps_it() -> None:
    data = _twins(f"{words(10)} {BEGIN}{words(5, 10)}{END}")
    assert {core_of(data, i) for i in "ABCD"} == {(words(10), 10)}


@pytest.mark.parametrize(
    "other",
    [
        None,
        f"{words(9)} {BEGIN}{words(6, 9)}{END}",  # a core of other words
        words(15),  # no core: it would be the whole text
        f"{words(10)} {BEGIN}{words(5, 10)}",  # malformed: no core
    ],
    ids=["no-template", "another-core", "whole-text", "malformed"],
)
def test_a_group_with_uneven_cores_keeps_none(other: str | None) -> None:
    """OFL-1.1-no-RFN had a core and its twins none: a copy of their text
    without its title read as OFL-1.1-no-RFN."""
    data = _twins(other)
    assert [core_of(data, i) for i in "ABC"] == [(None, None)] * 3
    assert core_of(data, "D") == (words(10), 10)  # not of the group
    assert row(data, "A")[15] == "A B C"


@pytest.mark.parametrize(
    ("cores", "dropped"),
    [
        ({"A": "x", "B": "x"}, set()),
        ({"A": "x", "B": "y"}, {"A", "B"}),
        ({"A": "x", "B": None}, {"A", "B"}),
        ({"A": None, "B": None}, set()),
        ({"A": "x"}, {"A", "B"}),  # B has no row: no core
        ({"A": "x", "B": "x", "C": "y", "D": "y"}, set()),
    ],
    ids=["same", "other", "one-none", "none", "missing", "two-groups"],
)
def test_uneven_cores(cores: dict[str, str | None], dropped: set[str]) -> None:
    groups = {"A": "A B", "B": "A B"}
    if "C" in cores:
        groups |= {"C": "C D", "D": "C D"}
    assert uneven_cores(groups, cores) == dropped


# The database


def _database(path: Path, data: SpdxData) -> LicenseDatabase:
    return database_of(to_bundle(data), path)


def _real() -> SpdxData:
    """Apache-2.0 and LGPL-3.0-only with their real texts and templates, and
    MIT with a text and none."""
    texts: dict[str, str] = {}
    templates: dict[str, str] = {}
    for license_id in ("Apache-2.0", "LGPL-3.0-only"):
        raw = (FIXTURES / "license-text-long" / f"{license_id}.json").read_text(
            encoding="utf-8"
        )
        texts[license_id] = json.loads(raw)["license_text"]
        templates[license_id] = (
            FIXTURES / "license-template" / f"{license_id}.template.txt"
        ).read_text(encoding="utf-8")
    texts["MIT"] = "Permission is hereby granted, free of charge, to any person."
    return data_of(texts, templates)


def test_the_database_holds_the_core_of_a_real_licence(tmp_path: Path) -> None:
    db = _database(tmp_path / "licenses.db", _real())
    parts = text_parts(db)
    assert set(parts) == {"Apache-2.0", "LGPL-3.0-only"}
    assert (
        parts["Apache-2.0"].core_word_count,
        parts["LGPL-3.0-only"].core_word_count,
    ) == (
        1393,
        1211,
    )
    core = parts["Apache-2.0"].core
    assert core is not None
    assert len(core.split()) == 1393
    assert parts["Apache-2.0"].same_text == ()
    assert db.get_metadata()["build_version"] == BUILD_VERSION


def test_the_database_holds_the_group_of_a_text(tmp_path: Path) -> None:
    same = words(40)
    data = data_of({"MPL-2.0": same, "MPL-2.0-no-copyleft-exception": same, "X": "x"})
    parts = text_parts(_database(tmp_path / "licenses.db", data))
    twins = ("MPL-2.0", "MPL-2.0-no-copyleft-exception")
    assert parts == {
        "MPL-2.0": TextParts(None, None, twins),
        "MPL-2.0-no-copyleft-exception": TextParts(None, None, twins),
    }


def test_the_columns_are_in_the_table_and_the_schema(tmp_path: Path) -> None:
    path = tmp_path / "licenses.db"
    _database(path, _real())
    with writer(path) as conn:
        found = {r[1]: r[2] for r in conn.execute("PRAGMA table_info(licenses)")}
        stored = conn.execute(
            "SELECT core_text, core_word_count, same_text FROM licenses"
            " WHERE license_id = 'Apache-2.0'"
        ).fetchone()
    assert [found[c] for c in COLUMNS] == ["TEXT", "INTEGER", "TEXT"]
    assert stored[1] == 1393
    assert stored[0].startswith("definitions license shall mean")
    assert stored[2] is None


def _build_4_file(path: Path) -> None:
    """A database of build 4: the build-5 columns are gone."""
    _database(path, _real())
    with writer(path) as conn:
        for name in COLUMNS:
            conn.execute(f"ALTER TABLE licenses DROP COLUMN {name}")
        conn.execute("UPDATE db_metadata SET value = '4' WHERE key = 'build_version'")


def _columns_of(path: Path) -> set[str]:
    with writer(path) as conn:
        return {r[1] for r in conn.execute("PRAGMA table_info(licenses)")}


@pytest.mark.parametrize("column", COLUMNS)
def test_a_file_without_a_column_reads_no_parts_and_is_not_written(
    tmp_path: Path, column: str, given: GivenWarnings
) -> None:
    """Build 4 had none of the columns: a lookup never adds them."""
    if sqlite3.sqlite_version_info < (3, 35):
        pytest.skip("ALTER TABLE DROP COLUMN needs SQLite 3.35")
    path = tmp_path / "licenses.db"
    _build_4_file(path)
    before = path.read_bytes()
    given.take()
    db = LicenseDatabase(str(path), create=False)
    assert given.conditions() == {"build v4 outdated"}
    assert text_parts(db) == {}  # NULL: no core and no twin until update
    assert column not in _columns_of(path)
    assert path.read_bytes() == before


def test_a_write_adds_the_columns_of_an_older_file(
    tmp_path: Path, given: GivenWarnings
) -> None:
    if sqlite3.sqlite_version_info < (3, 35):
        pytest.skip("ALTER TABLE DROP COLUMN needs SQLite 3.35")
    path = tmp_path / "licenses.db"
    _build_4_file(path)
    given.take()
    db = LicenseDatabase(str(path), create=False)
    assert text_parts(db) == {}
    db._write_db_records(build_records(_real(), {}), None)
    assert set(COLUMNS) <= _columns_of(path)
    db._tables.clear()
    assert set(text_parts(db)) == {"Apache-2.0", "LGPL-3.0-only"}


def test_a_lookup_reads_a_file_whose_columns_are_gone(tmp_path: Path) -> None:
    """Dropped under an open handle: a missing column is no error."""
    if sqlite3.sqlite_version_info < (3, 35):
        pytest.skip("ALTER TABLE DROP COLUMN needs SQLite 3.35")
    path = tmp_path / "licenses.db"
    db = _database(path, _real())
    assert text_parts(db)
    with writer(path) as conn:
        for name in COLUMNS:
            conn.execute(f"ALTER TABLE licenses DROP COLUMN {name}")
    db._tables.clear()
    assert text_parts(db) == {}


def test_a_file_without_the_build_columns_is_still_current(tmp_path: Path) -> None:
    """The columns of build 5 are no reason to write on a lookup."""
    if sqlite3.sqlite_version_info < (3, 35):
        pytest.skip("ALTER TABLE DROP COLUMN needs SQLite 3.35")
    path = tmp_path / "licenses.db"
    db = _database(path, _real())
    assert schema_state(db._connections) == "current"
    with writer(path) as conn:
        conn.execute("ALTER TABLE licenses DROP COLUMN same_text")
    assert schema_state(db._connections) == "current"
    with writer(path) as conn:
        conn.execute("ALTER TABLE licenses DROP COLUMN norm_name")
    assert schema_state(db._connections) == "older"


def test_the_parts_are_read_once_and_follow_a_rebuild(tmp_path: Path) -> None:
    path = tmp_path / "licenses.db"
    db = _database(path, _real())
    first = text_parts(db)
    assert text_parts(db) is first  # read once
    same = words(40)
    db._write_db_records(build_records(data_of({"A": same, "B": same}), {}), None)
    assert text_parts(db) == {
        "A": TextParts(None, None, ("A", "B")),
        "B": TextParts(None, None, ("A", "B")),
    }


def test_a_row_with_a_null_core_or_a_zero_count_has_no_core(tmp_path: Path) -> None:
    path = tmp_path / "licenses.db"
    db = _database(path, _real())
    with writer(path) as conn:
        conn.execute(
            "UPDATE licenses SET core_text = 'x', core_word_count = 0"
            " WHERE license_id = 'MIT'"
        )
        conn.execute(
            "UPDATE licenses SET core_text = NULL WHERE license_id = 'Apache-2.0'"
        )
        conn.execute("UPDATE licenses SET same_text = 'MIT X' WHERE license_id = 'MIT'")
    db._tables.clear()
    parts = text_parts(db)
    assert parts["MIT"] == TextParts(None, None, ("MIT", "X"))
    assert "Apache-2.0" not in parts  # no core, no twin: no entry
