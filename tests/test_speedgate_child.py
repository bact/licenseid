# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The speed gate's processes and files: a child bound to its side by
``PYTHONPATH``, a database built from cached files, damaged copies, a List
tarball. POSIX only: the tool uses ``resource`` and ``os.getloadavg``."""

import json
import sqlite3
import sys
import tarfile
from pathlib import Path
from typing import Any

import pytest
from conftest import posix_only

from benchmarks.speedgate import damage, runner, sets_roadmap, sidedb
from benchmarks.speedgate.runner import Job, Side

pytestmark = posix_only

# pylint: disable=missing-function-docstring

FAKE_DETECTOR = """
class LicenseDetector:
    def __init__(self, db):
        self.db = db

    def detect(self, text, **options):
        if text == "boom":
            raise ValueError("boom")
        return [{"expression": "MIT", "score": 1.0, "method": "text",
                 "exact": True, "texts": ["MIT"], "options": sorted(options)}]

    def texts(self, text, **options):
        return ["MIT"]
"""


def _fake_side(tmp_path: Path) -> Side:
    package = tmp_path / "side" / "src" / "licenseid"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('__version__ = "9.9.9"\n')
    (package / "detector.py").write_text(FAKE_DETECTOR)
    home = tmp_path / "home"
    home.mkdir()
    return Side(tmp_path / "side", tmp_path / "db.sqlite", home, sys.executable)


def _job(tmp_path: Path, cases: list[dict[str, Any]]) -> Job:
    inputs = tmp_path / "inputs.json"
    inputs.write_text(json.dumps({"digest": "d", "sets": {"core": cases}}))
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    return Job(inputs, scratch)


def test_a_child_imports_its_own_side_and_says_so(tmp_path: Path) -> None:
    side = _fake_side(tmp_path)
    cases: list[dict[str, Any]] = [
        {"key": "a", "text": "x", "options": {"exclude": ["ISC"]}, "texts_call": True},
        {"key": "b", "text": "boom"},
    ]
    out = runner.run_child(side, _job(tmp_path, cases), ["detect", "--set", "core"])
    assert out["from_side"] is True
    assert out["licenseid_file"] == str(
        side.path.resolve() / "src/licenseid/__init__.py"
    )
    assert out["licenseid_version"] == "9.9.9"
    assert out["cases"]["a"]["rows"] == [["MIT", 1.0, "text", True]]
    assert out["cases"]["a"]["texts"] == ["MIT"] and out["cases"]["a"]["cpu_ms"] >= 0
    assert out["cases"]["b"]["error"] == "ValueError: boom"


def test_a_child_names_one_case_and_a_slow_one_is_cut(tmp_path: Path) -> None:
    side = _fake_side(tmp_path)
    job = _job(tmp_path, [{"key": "a", "text": "x"}, {"key": "b", "text": "y"}])
    out = runner.run_child(side, job, ["detect", "--set", "core", "--only", "b"])
    assert list(out["cases"]) == ["b"]
    assert runner.run_child(side, job, ["detect", "--set", "none"])["error"].startswith(
        "exit"
    )


def test_the_environment_of_a_child_is_its_side_and_a_scratch_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYTHONHOME", "/elsewhere")
    env = _fake_side(tmp_path).env()
    assert env["PYTHONPATH"] == str(tmp_path / "side" / "src")
    assert env["HOME"] == str(tmp_path / "home") and "PYTHONHOME" not in env


@pytest.mark.parametrize(
    ("start", "end", "loaded"),
    [
        ([2.0, 0, 0], [2.0, 0, 0], False),
        ([2.1, 0, 0], [0.1, 0, 0], True),
        ([0.1, 0, 0], [3.0, 0, 0], True),
    ],
)
def test_a_busy_machine_at_either_end_flags_a_run(
    start: list[float], end: list[float], loaded: bool
) -> None:
    assert runner.is_loaded(start, end) is loaded


# The table of the texts of each build: plain from build 10, FTS5 before.
TEXT_TABLES = {
    "license_texts": (
        "CREATE TABLE license_texts"
        " (text_id INTEGER PRIMARY KEY, license_id TEXT, search_text TEXT)"
    ),
    "license_index": (
        "CREATE VIRTUAL TABLE license_index USING fts5(license_id, search_text)"
    ),
}


def _database(path: Path, table: str = "license_texts") -> None:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE text_codes (kind TEXT, owner_id TEXT, body TEXT)")
    con.execute(TEXT_TABLES[table])
    rows = [
        ("text", "MIT", "abcd"),
        ("words", "", '["permission","warranty"]'),
        ("textvars", "MIT", "[[1,5]]"),
        ("patterns", "", "aaa"),
        ("check", "", "c"),
    ]
    con.executemany("INSERT INTO text_codes VALUES (?, ?, ?)", rows)
    con.execute("INSERT INTO text_codes VALUES ('text', 'Apache-2.0', 'zz')")
    con.executemany(
        f"INSERT INTO {table} (license_id, search_text) VALUES (?, ?)",
        [("MIT", "permission is granted"), ("ISC", "isc"), ("X", "x")],
    )
    con.commit()
    con.close()


def test_each_damage_changes_one_thing_and_the_intact_copy_nothing(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src.db"
    _database(source)
    copies = damage.make_copies(source, tmp_path / "out")
    for kind in CHECKS_KINDS:
        assert copies[kind] is None
    edited = "text of MIT edited, new update time, codes kept"
    assert copies[edited] is None and edited + damage.REFERENCE not in copies

    def body(name: str, kind: str, owner: str) -> str:
        path = copies[name]
        assert path is not None
        got = (
            sqlite3.connect(path)
            .execute(
                "SELECT body FROM text_codes WHERE kind = ? AND owner_id = ?",
                (kind, owner),
            )
            .fetchone()
        )
        return str(got[0]) if got else "<gone>"

    assert body(damage.INTACT, "text", "MIT") == "abcd"
    assert body("codes of MIT changed", "text", "MIT") == "bacd"
    assert body("codes of Apache-2.0 deleted", "text", "Apache-2.0") == "<gone>"
    assert (
        body("two words of the vocabulary swapped", "words", "")
        == '["warranty","permission"]'
    )
    assert body("regions of one text changed", "textvars", "MIT") == "[[1,8]]"
    assert body("patterns changed", "patterns", "") == "baa"
    assert body("check of the whole corpus changed", "check", "") == "x"
    reference = "text of MIT changed, codes kept" + damage.REFERENCE
    assert body(reference, "text", "MIT") == "<gone>"
    kept = copies["text of MIT changed, codes kept"]
    assert (
        kept is not None
        and body("text of MIT changed, codes kept", "text", "MIT") == "abcd"
    )


CHECKS_KINDS = [
    "check of BSD-3-Clause changed",
    "no checks table",
    "checks table misshaped",
    "check of the head changed",
    "check of MIT missing",
    "codes of MIT a blob one byte short",
]


def _with_checks(path: Path) -> None:
    _database(path)
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE text_code_checks (owner_id TEXT PRIMARY KEY, digest TEXT)"
        " WITHOUT ROWID"
    )
    con.executemany(
        "INSERT INTO text_code_checks VALUES (?, ?)",
        [("", "h"), ("MIT", "m"), ("BSD-3-Clause", "b")],
    )
    con.execute("CREATE TABLE db_metadata (key TEXT, value TEXT)")
    con.execute("INSERT INTO db_metadata VALUES ('last_update_datetime', 't')")
    con.commit()
    con.close()


def _rows_of(path: Path | None, sql: str) -> list[Any]:
    assert path is not None
    con = sqlite3.connect(path)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_each_damage_of_the_checks_changes_what_it_names(tmp_path: Path) -> None:
    source = tmp_path / "src.db"
    _with_checks(source)
    copies = damage.make_copies(source, tmp_path / "out")
    checks = "SELECT owner_id, digest FROM text_code_checks ORDER BY owner_id"
    intact = [("", "h"), ("BSD-3-Clause", "b"), ("MIT", "m")]
    assert _rows_of(copies[damage.INTACT], checks) == intact
    assert _rows_of(copies["check of the head changed"], checks)[0] == ("", "x")
    assert _rows_of(copies["check of MIT missing"], checks) == intact[:2]
    assert _rows_of(copies["check of BSD-3-Clause changed"], checks)[1][1] == "x"
    tables = "SELECT name, sql FROM sqlite_master WHERE name = 'text_code_checks'"
    assert not _rows_of(copies["no checks table"], tables)
    (shape,) = _rows_of(copies["checks table misshaped"], tables)
    assert "WITHOUT ROWID" not in shape[1]
    assert _rows_of(copies["checks table misshaped"], checks) == intact
    codes = "SELECT body, typeof(body) FROM text_codes WHERE owner_id = 'MIT'"
    assert _rows_of(copies["codes of MIT a blob one byte short"], codes)[0] == (
        b"abc",
        "blob",
    )
    edited = "text of MIT edited, new update time, codes kept"
    text = "SELECT search_text FROM license_texts WHERE license_id = 'MIT'"
    stamp = "SELECT value FROM db_metadata"
    assert _rows_of(copies[edited], text) == [("permission",)]
    assert _rows_of(copies[edited], stamp) == [("2099-01-01 00:00:00",)]
    assert _rows_of(copies[edited], codes)[0] == ("abcd", "text")
    reference = copies[edited + damage.REFERENCE]
    assert _rows_of(reference, text) == [("permission",)]
    assert not _rows_of(reference, codes)
    assert damage.NOT_READY == {
        "no checks table",
        "checks table misshaped",
        "no texts table",
        "texts table misshaped",
    }


def test_a_database_is_built_from_cached_files_or_not_at_all(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    with pytest.raises(sidedb.BuildError, match="no spdx-data tarball"):
        sidedb.copy_cache(cache, tmp_path / "dest")
    for name in ("latest.json", "licenses.json", "spdx-data-v3.29.0.tar.gz", "other"):
        (cache / name).write_text("x")
    assert sidedb.copy_cache(cache, tmp_path / "dest") == "3.29.0"
    assert sorted(p.name for p in (tmp_path / "dest").iterdir()) == [
        "latest.json",
        "licenses.json",
        "spdx-data-v3.29.0.tar.gz",
    ]


def test_a_list_text_is_read_from_the_tarball(tmp_path: Path) -> None:
    source = tmp_path / "ISC.txt"
    source.write_text("ISC License\nPermission to use")
    tarball = tmp_path / "list.tar.gz"
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(source, arcname="license-list-data-3.29.0/text/ISC.txt")
    assert sets_roadmap.list_text(tarball, "ISC").startswith("ISC License")
    with pytest.raises(KeyError):
        sets_roadmap.list_text(tarball, "MIT")
    assert sets_roadmap.without_title("ISC License\n\nPermission") == "\nPermission"


POSTINGS_KINDS = [
    "postings stale against the texts",
    "postings without a stamp",
    "postings stamp: another gram size",
    "postings stamp: another width",
    "postings blob one byte short",
    "postings number out of range",
    "postings table emptied",
    "posting ids table emptied",
]
STAMP = {"gram": 3, "grams": 2, "hash": "h", "texts": 2, "width": 2}


def _with_postings(path: Path) -> None:
    _database(path)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE db_metadata (key TEXT, value TEXT)")
    con.execute("CREATE TABLE text_postings (h INTEGER, ids BLOB)")
    con.execute("CREATE TABLE text_posting_ids (k INTEGER, id TEXT, size INTEGER)")
    con.executemany(
        "INSERT INTO db_metadata VALUES (?, ?)",
        [
            ("text_postings", json.dumps(STAMP, sort_keys=True)),
            ("text_postings_update", "2026-11-01 00:00:00"),
            ("last_update_datetime", "2026-11-01 00:00:00"),
        ],
    )
    con.executemany(
        "INSERT INTO text_postings VALUES (?, ?)",
        [(1, b"\x00\x00\x01\x00"), (2, b"\x01\x00")],
    )
    con.executemany(
        "INSERT INTO text_posting_ids VALUES (?, ?, ?)", [(0, "A", 1), (1, "B", 2)]
    )
    con.commit()
    con.close()


def _dump(path: Path | None) -> list[Any]:
    assert path is not None
    con = sqlite3.connect(path)
    try:
        return [
            con.execute(f"SELECT * FROM {t} ORDER BY 1, 2").fetchall()
            for t in ("db_metadata", "text_postings", "text_posting_ids")
        ]
    finally:
        con.close()


@pytest.mark.parametrize("kind", POSTINGS_KINDS)
def test_each_postings_damage_changes_the_postings_and_nothing_else(
    tmp_path: Path, kind: str
) -> None:
    source = tmp_path / "src.db"
    _with_postings(source)
    copies = damage.make_copies(source, tmp_path / "out")
    assert _dump(copies[damage.INTACT]) == _dump(source)
    assert _dump(copies[kind]) != _dump(source)
    assert damage.has_postings(source)


@pytest.mark.parametrize("kind", POSTINGS_KINDS)
def test_a_side_without_the_postings_tables_has_no_such_kind(
    tmp_path: Path, kind: str
) -> None:
    source = tmp_path / "src.db"
    _database(source)
    assert damage.make_copies(source, tmp_path / "out")[kind] is None
    assert not damage.has_postings(source)


@pytest.mark.parametrize("table", sorted(TEXT_TABLES))
def test_each_damage_of_the_texts_changes_what_it_names(
    tmp_path: Path, table: str
) -> None:
    """On the table of the side's build: plain (build 10) or FTS5 (before)."""
    source = tmp_path / "src.db"
    _database(source, table)
    copies = damage.make_copies(source, tmp_path / "out")
    texts = f"SELECT license_id, search_text FROM {table}"
    shape = f"SELECT sql FROM sqlite_master WHERE name = '{table}'"
    assert _rows_of(copies[damage.INTACT], texts) == [
        ("MIT", "permission is granted"),
        ("ISC", "isc"),
        ("X", "x"),
    ]
    assert _rows_of(copies["text of MIT changed, codes kept"], texts)[0] == (
        "MIT",
        "permision is granted",
    )
    assert not _rows_of(copies["no texts table"], shape)
    ((sql,),) = _rows_of(copies["texts table misshaped"], shape)
    assert sql.startswith((f'CREATE TABLE "{table}"', f"CREATE TABLE {table}"))
    assert "text_id" not in sql and "fts5" not in sql
    assert _rows_of(copies["texts table misshaped"], texts) == _rows_of(
        copies[damage.INTACT], texts
    )
    removed = "texts of MIT and ISC removed, codes kept"
    assert _rows_of(copies[removed], texts) == [("X", "x")]
    assert _rows_of(copies[removed], "SELECT count(*) FROM text_codes") == [(6,)]
    assert _rows_of(
        copies[removed + damage.REFERENCE], "SELECT count(*) FROM text_codes"
    ) == [(0,)]
