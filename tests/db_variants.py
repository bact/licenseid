# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Database variants for the readiness-gate tests.

One registry, ``BUILDERS``, builds every ``--db`` argument the gate has to
handle: ready databases, each way of being not ready, and the odd paths and
URIs SQLite accepts. ``test_db_ready.py`` runs the contract against all of
them; ``test_cli_matrix``-style tools can reuse the builders.
"""

# pylint: disable=missing-function-docstring

import contextlib
import os
import sqlite3
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from conftest import insert_mit_license, make_ready_db_path

from licenseid.database import NORMALIZATION_VERSION, LicenseDatabase

MIT_TEXT = (
    "Permission is hereby granted, free of charge, to any person obtaining a copy"
)
LICENSE_LIST_VERSION = "3.30"

COMMANDS = ["match", "is-osi", "is-fsf", "is-open", "is-free", "is-spdx"]
INPUTS = ["arg_file", "arg_id", "text", "id", "stdin", "none", "blank", "blank_text"]

# Refusal kinds. REFUSED: refused, but the contract does not fix which of the
# three messages applies. LENIENT: a damaged file that may still be ready (a
# flipped byte often lands in free space), so only the safety invariants (no
# traceback, no stray exit code) are pinned.
NOT_FOUND = "not found"
EMPTY = "empty"
INVALID = "invalid"  # another program's tables, none of ours
UNREADABLE = "unreadable"
REFUSED = "refused"
READY = "ready"
LENIENT = "lenient"

IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


# Database builders


@dataclass
class Variant:
    """One ``--db`` argument plus what the contract says must happen."""

    name: str
    db_arg: str
    kind: str
    path: Path | None = None  # file-backed: side effects are checked
    keep_alive: sqlite3.Connection | None = None


Builder = Callable[[str, Path], Variant]
Offset = Callable[[int], int]  # byte offset, given the ready file's size

_LIC_TABLE = (
    "CREATE TABLE licenses (license_id TEXT PRIMARY KEY, name TEXT, "
    "is_spdx BOOLEAN, is_osi_approved BOOLEAN, is_fsf_libre BOOLEAN)"
)
_META_TABLE = "CREATE TABLE db_metadata (key TEXT PRIMARY KEY, value TEXT)"
_MIT_ROW = "INSERT INTO licenses (license_id, name) VALUES ('MIT', 'MIT License')"
_VER_ROW = (
    "INSERT INTO db_metadata (key, value) "
    f"VALUES ('license_list_version', '{LICENSE_LIST_VERSION}')"
)


@contextlib.contextmanager
def writer(path: Path) -> Iterator[sqlite3.Connection]:
    """Open, commit, close: ``Connection.__exit__`` does not close."""
    with contextlib.ExitStack() as stack:
        conn = stack.enter_context(contextlib.closing(sqlite3.connect(str(path))))
        stack.enter_context(conn)  # commit or roll back before the close
        yield conn


def _seed_metadata(conn: sqlite3.Connection) -> None:
    """The metadata a READY database must carry. A fresh last_check_datetime
    and the current normalisation version keep stderr empty for it (no
    staleness, no outdated warning)."""
    for key, value in (
        ("license_list_version", LICENSE_LIST_VERSION),
        ("normalization_version", NORMALIZATION_VERSION),
        ("last_check_datetime", datetime.now(timezone.utc).isoformat()),
    ):
        conn.execute("INSERT INTO db_metadata (key, value) VALUES (?, ?)", (key, value))


def _seed_ready(conn: sqlite3.Connection) -> None:
    """One license row plus the metadata a READY database must carry."""
    insert_mit_license(conn)
    _seed_metadata(conn)


def make_ready_file_db(path: Path) -> Path:
    """A ready on-disk database: real schema, one row, metadata."""
    LicenseDatabase(str(path))
    with writer(path) as conn:
        _seed_ready(conn)
    return path


def _bare_db(path: Path, statements: tuple[str, ...]) -> Path:
    """A database built from *statements* only -- no licenseid schema."""
    with writer(path) as conn:
        for statement in statements:
            conn.execute(statement)
    return path


def _db_path(db_dir: Path) -> Path:
    return db_dir / "licenses.db"


def raw_file(payload: bytes, kind: str) -> Builder:
    """A file that is not a database (or is an empty one)."""

    def build(name: str, db_dir: Path) -> Variant:
        path = _db_path(db_dir)
        path.write_bytes(payload)
        return Variant(name, str(path), kind, path)

    return build


def sql_db(statements: tuple[str, ...], kind: str) -> Builder:
    def build(name: str, db_dir: Path) -> Variant:
        path = _bare_db(_db_path(db_dir), statements)
        return Variant(name, str(path), kind, path)

    return build


def damaged_copy(
    kind: str, truncate: Offset | None = None, flip: Offset | None = None
) -> Builder:
    """A ready database copied and then truncated, or one byte flipped."""

    def build(name: str, db_dir: Path) -> Variant:
        data = bytearray(make_ready_file_db(db_dir / "source.db").read_bytes())
        assert len(data) > 8192, "ready fixture too small for these offsets"
        if truncate is not None:
            data = data[: truncate(len(data))]
        else:
            assert flip is not None
            data[flip(len(data))] ^= 0xFF
        path = _db_path(db_dir)
        path.write_bytes(bytes(data))
        return Variant(name, str(path), kind, path)

    return build


def odd_path(filename: str, kind: str) -> Builder:
    """A real path whose characters invite URI or option parsing bugs."""

    def build(name: str, db_dir: Path) -> Variant:
        path = db_dir / filename
        if kind == READY:
            make_ready_file_db(path)
        else:
            _bare_db(path, (_LIC_TABLE, _META_TABLE))
        return Variant(name, str(path), kind, path)

    return build


def memory_uri(kind: str, template: str) -> Builder:
    def build(name: str, db_dir: Path) -> Variant:
        del db_dir
        return Variant(name, template.format(uuid=uuid.uuid4().hex[:8]), kind)

    return build


def file_uri(suffix: str, kind: str, seed: bool) -> Builder:
    def build(name: str, db_dir: Path) -> Variant:
        path = _db_path(db_dir)
        if seed:
            make_ready_file_db(path)
        return Variant(name, f"file:{path}{suffix}", kind, path)

    return build


def symlink(make_target: Callable[[Path], Path], kind: str) -> Builder:
    """A symlink at the database path, pointing where *make_target* says."""

    def build(name: str, db_dir: Path) -> Variant:
        path = _db_path(db_dir)
        path.symlink_to(make_target(db_dir))
        return Variant(name, str(path), kind, path)

    return build


def _missing_target(db_dir: Path) -> Path:
    return db_dir / "no-such-target.db"


def _a_directory(db_dir: Path) -> Path:
    target = db_dir / "a-directory"
    target.mkdir()
    return target


def _ready_target(db_dir: Path) -> Path:
    return make_ready_file_db(db_dir / "real-licenses.db")


def build_missing(name: str, db_dir: Path) -> Variant:
    return Variant(name, str(_db_path(db_dir)), NOT_FOUND, _db_path(db_dir))


def build_directory(name: str, db_dir: Path) -> Variant:
    path = _db_path(db_dir)
    path.mkdir()
    (path / "inside.txt").write_text("not a database\n", encoding="utf-8")
    return Variant(name, str(path), UNREADABLE, path)


def build_no_permission(name: str, db_dir: Path) -> Variant:
    path = make_ready_file_db(_db_path(db_dir))
    path.chmod(0o000)
    return Variant(name, str(path), UNREADABLE, path)


def build_wal_copy_without_wal(name: str, db_dir: Path) -> Variant:
    """A WAL database's main file copied without its -wal: the committed rows
    and metadata are not in the copy."""
    source = db_dir / "wal-source.db"
    holder = sqlite3.connect(str(source))
    holder.execute("PRAGMA journal_mode=WAL")
    LicenseDatabase(str(source))
    wal_writer = sqlite3.connect(str(source))
    with wal_writer:
        _seed_ready(wal_writer)
    path = _db_path(db_dir)
    # Copy while the WAL still holds the data: closing a connection
    # checkpoints it back into the main file, which would defeat the point.
    path.write_bytes(source.read_bytes())
    wal_writer.close()
    holder.close()
    return Variant(name, str(path), EMPTY, path)


def ready_file_then(statement: str) -> Builder:
    """A ready database that *statement* then damages: not ready any more."""

    def build(name: str, db_dir: Path) -> Variant:
        path = make_ready_file_db(_db_path(db_dir))
        with writer(path) as conn:
            conn.execute(statement)
        return Variant(name, str(path), EMPTY, path)

    return build


def build_ready_file(name: str, db_dir: Path) -> Variant:
    path = make_ready_file_db(_db_path(db_dir))
    return Variant(name, str(path), READY, path)


def build_ready_memory_uri(name: str, db_dir: Path) -> Variant:
    del db_dir
    db_arg, keep_alive = make_ready_db_path("test_db_ready_adversarial")
    return Variant(name, db_arg, READY, None, keep_alive)


def build_ready_wal_with_wal(name: str, db_dir: Path) -> Variant:
    """Ready only because of its -wal: the main file has the schema and the
    metadata but no license row; the row was committed in WAL mode and is not
    checkpointed. Reading only the main file would call it empty."""
    path = _db_path(db_dir)
    LicenseDatabase(str(path))
    with writer(path) as conn:
        _seed_metadata(conn)
    keep_alive = sqlite3.connect(str(path))
    keep_alive.execute("PRAGMA journal_mode=WAL")
    insert_mit_license(keep_alive)
    keep_alive.commit()
    assert path.with_name(path.name + "-wal").exists(), "no -wal file was created"
    return Variant(name, str(path), READY, path, keep_alive)


def version_value(sql_value: str) -> Builder:
    """A database whose license_list_version is blank in some way."""
    return ready_file_then(
        f"UPDATE db_metadata SET value = {sql_value} WHERE key = 'license_list_version'"
    )


BUILDERS: dict[str, Builder] = {
    # Nothing there.
    "missing": build_missing,
    "dangling_symlink": symlink(_missing_target, NOT_FOUND),
    # Not a database at all. A file under 100 bytes reads as a brand-new
    # empty database, not as a corrupt one, hence EMPTY for the short ones.
    "zero_byte": raw_file(b"", EMPTY),
    "header_only": raw_file(b"SQLite format 3\x00", UNREADABLE),
    "text_with_sqlite_prefix": raw_file(
        b"SQLite format 3 is the file format used here.\n" * 4, UNREADABLE
    ),
    "plain_text": raw_file(
        b"This project is licensed under the MIT licence.\n" * 8, UNREADABLE
    ),
    "directory": build_directory,
    "symlink_to_directory": symlink(_a_directory, UNREADABLE),
    "no_permission": build_no_permission,
    # Damaged copies of a ready database.
    "truncated_1": damaged_copy(EMPTY, truncate=lambda size: 1),
    "truncated_100": damaged_copy(UNREADABLE, truncate=lambda size: 100),
    "truncated_4096": damaged_copy(UNREADABLE, truncate=lambda size: 4096),
    "truncated_half": damaged_copy(UNREADABLE, truncate=lambda size: size // 2),
    "flipped_header": damaged_copy(UNREADABLE, flip=lambda size: 3),
    # A flip in a later page often lands in free space, so the database can
    # stay perfectly ready: only the safety invariants are pinned.
    "flipped_mid_page": damaged_copy(LENIENT, flip=lambda size: size // 2 + 17),
    # Structurally incomplete databases.
    "only_licenses_table": sql_db((_LIC_TABLE, _MIT_ROW), EMPTY),
    "only_metadata_table": sql_db((_META_TABLE, _VER_ROW), EMPTY),
    "both_tables_empty": sql_db((_LIC_TABLE, _META_TABLE), EMPTY),
    "rows_without_metadata": sql_db((_LIC_TABLE, _MIT_ROW, _META_TABLE), EMPTY),
    "metadata_without_rows": sql_db((_LIC_TABLE, _META_TABLE, _VER_ROW), EMPTY),
    "version_empty": version_value("''"),
    "version_whitespace": version_value("' \t\n '"),
    "version_null": version_value("NULL"),
    # Views, not tables: a readiness check that queries sqlite_master without
    # filtering on type='table' (or that just runs SELECT) is fooled here.
    # Every required name exists, but as a view over one foreign table, with
    # all the required columns and a row. Only the type = 'table' filter in
    # the gate's sqlite_master query tells this apart from a real database.
    "views_not_tables": sql_db(
        (
            (
                "CREATE TABLE backing (license_id TEXT, name TEXT, "
                "is_spdx BOOLEAN, is_osi_approved BOOLEAN, is_fsf_libre BOOLEAN, "
                "key TEXT, value TEXT, search_text TEXT)"
            ),
            (
                "INSERT INTO backing VALUES ('MIT', 'MIT License', 1, 1, 1, "
                f"'license_list_version', '{LICENSE_LIST_VERSION}', 'mit')"
            ),
            (
                "CREATE VIEW licenses AS SELECT license_id, name, is_spdx, "
                "is_osi_approved, is_fsf_libre FROM backing"
            ),
            "CREATE VIEW db_metadata AS SELECT key, value FROM backing",
            "CREATE VIEW license_index AS SELECT license_id, search_text FROM backing",
        ),
        INVALID,
    ),
    # Somebody else's populated database: "update" would write into it.
    "foreign_table_only": sql_db(
        ("CREATE TABLE history (url TEXT)", "INSERT INTO history VALUES ('x')"),
        INVALID,
    ),
    # A foreign table beside a partial licenseid schema: not ours to write to.
    "foreign_table_beside_partial": sql_db(
        ("CREATE TABLE history (url TEXT)", _LIC_TABLE, _MIT_ROW), INVALID
    ),
    # Only SQLite's own bookkeeping left: nothing foreign, so "empty".
    "only_sqlite_sequence": sql_db(
        (
            "CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT)",
            "INSERT INTO t DEFAULT VALUES",
            "DROP TABLE t",
        ),
        EMPTY,
    ),
    # Tables, version and a row, but not the columns every answer reads.
    "wrong_columns": sql_db(
        (
            "CREATE TABLE licenses (spdx_id TEXT, title TEXT)",
            "INSERT INTO licenses VALUES ('MIT', 'MIT License')",
            "CREATE VIRTUAL TABLE license_index USING fts5(license_id, search_text)",
            "INSERT INTO license_index VALUES ('MIT', 'x')",
            _META_TABLE,
            _VER_ROW,
        ),
        INVALID,
    ),
    # SQLite matches column names without case; the code looks them up with it.
    "column_name_case_flipped": sql_db(
        (
            _LIC_TABLE.replace("is_fsf_libre", "is_fsf_librE"),
            _MIT_ROW,
            "CREATE VIRTUAL TABLE license_index USING fts5(license_id, search_text)",
            "INSERT INTO license_index VALUES ('MIT', 'x')",
            _META_TABLE,
            _VER_ROW,
        ),
        INVALID,
    ),
    "wal_copy_without_wal": build_wal_copy_without_wal,
    # The search index is what match reads: without rows it answers "no".
    # SQLite lets a TEXT key hold NULL or a blob; normalising one raises.
    "null_license_id": ready_file_then("UPDATE licenses SET license_id = NULL"),
    "blob_license_id": ready_file_then("UPDATE licenses SET license_id = X'4D4954'"),
    "index_dropped": ready_file_then("DROP TABLE license_index"),
    "index_emptied": ready_file_then("DELETE FROM license_index"),
    # Real paths that must never be parsed as URIs or as options.
    "path_with_spaces": odd_path("a licence db.db", EMPTY),
    "path_leading_dash": odd_path("-licenses.db", EMPTY),
    "path_non_ascii": odd_path("licences-授权-ünïcödé.db", EMPTY),
    "path_question_mark": odd_path("licenses?mode=memory&cache=shared.db", EMPTY),
    "path_hash": odd_path("licenses#1.db", EMPTY),
    "path_percent": odd_path("licenses%2Fdir%00.db", EMPTY),
    "ready_path_with_spaces": odd_path("a licence db.db", READY),
    "ready_path_leading_dash": odd_path("-licenses.db", READY),
    "ready_path_non_ascii": odd_path("licences-授权-ünïcödé.db", READY),
    "ready_path_question_mark": odd_path("licenses?mode=memory&cache=shared.db", READY),
    "ready_path_hash": odd_path("licenses#1.db", READY),
    "ready_path_percent": odd_path("licenses%2Fdir%00.db", READY),
    # URIs. A fresh in-memory database has no tables, so it is "empty".
    "memory_uri": memory_uri(EMPTY, ":memory:"),
    "file_colon_memory": memory_uri(EMPTY, "file::memory:"),
    "file_mode_memory": memory_uri(
        EMPTY, "file:adversarial_{uuid}?mode=memory&cache=shared"
    ),
    # A file: URI naming a missing file is "not found", like a plain path.
    "file_uri_missing": file_uri("", NOT_FOUND, seed=False),
    "file_uri_mode_ro_missing": file_uri("?mode=ro", NOT_FOUND, seed=False),
    "ready_file_uri": file_uri("", READY, seed=True),
    "ready_file_uri_mode_ro": file_uri("?mode=ro", READY, seed=True),
    "ready_file": build_ready_file,
    "ready_symlink": symlink(_ready_target, READY),
    "ready_memory_uri": build_ready_memory_uri,
    "ready_wal_with_wal": build_ready_wal_with_wal,
}


def build_variant(name: str, tmp_path: Path) -> Variant:
    """Build the ``--db`` argument named *name* under *tmp_path*."""
    db_dir = tmp_path / "db"
    db_dir.mkdir(exist_ok=True)
    return BUILDERS[name](name, db_dir)


# The registry is the single source of truth: "ready_*" is ready, LENIENT_NAMES
# are ready-but-open-ended, everything else must be refused.
LENIENT_NAMES = ["flipped_mid_page"]
READY_NAMES = [name for name in BUILDERS if name.startswith("ready_")]


def _param(name: str) -> Any:
    """Permission bits mean nothing to root, so that one variant is skipped."""
    if name == "no_permission":
        return pytest.param(
            name,
            marks=pytest.mark.skipif(IS_ROOT, reason="root ignores file permissions"),
        )
    return name


NOT_READY_NAMES = [
    _param(name)
    for name in BUILDERS
    if name not in READY_NAMES and name not in LENIENT_NAMES
]
